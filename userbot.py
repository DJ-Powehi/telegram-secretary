"""
Telethon userbot for capturing all incoming Telegram messages.
Logs into the client's Telegram account and monitors all chats.
"""

import logging
from datetime import datetime
from typing import Optional, Set

from telegram.constants import ParseMode
from telethon import TelegramClient, events
from telethon.tl.types import User, Chat, Channel

from config import get_config
from database import get_session
from models import Message, HighPriorityUser
from utils import (
    calculate_priority_score,
    detect_mention,
    detect_question,
    generate_topic_summary,
    get_chat_type,
    sanitize_for_logging,
    truncate_text,
)

logger = logging.getLogger(__name__)

# Global client instance
_userbot_client: Optional[TelegramClient] = None

# Cache of high priority user IDs (refreshed periodically)
_high_priority_users: Set[int] = set()


def _get_bot_user_id() -> int:
    """Extract bot user ID from bot token (format: BOT_ID:SECRET)."""
    config = get_config()
    return int(config.telegram.bot_token.split(":")[0])


async def get_userbot_client() -> TelegramClient:
    """Get or create the Telethon userbot client."""
    global _userbot_client
    
    if _userbot_client is None:
        import os
        import base64
        
        config = get_config()
        session_name = "secretary_session"
        
        # Support SESSION_DATA environment variable (base64-encoded session file)
        # This makes Railway deployment easier - can store session as env var
        session_data_env = os.getenv("SESSION_DATA")
        if session_data_env:
            try:
                # Decode base64 session data and write to file
                session_bytes = base64.b64decode(session_data_env)
                with open(f"{session_name}.session", "wb") as f:
                    f.write(session_bytes)
                logger.info("Session file created from SESSION_DATA environment variable")
            except Exception as e:
                logger.warning(f"Failed to decode SESSION_DATA: {e}. Will use file-based session.")
        
        _userbot_client = TelegramClient(
            session_name,  # Session file name
            config.telegram.api_id,
            config.telegram.api_hash,
        )
    
    return _userbot_client


async def send_warning_for_message(
    message_id: int,
    message_text: Optional[str],
    user_name: Optional[str],
    chat_title: Optional[str],
    chat_type: str,
    priority_score: int,
    has_mention: bool,
    is_question: bool,
    topic_summary: Optional[str],
) -> None:
    """
    Send a real-time warning to the client for high-priority messages.
    
    This sends an immediate alert when a message meets the warning threshold.
    """
    try:
        from bot import send_simple_message, create_priority_keyboard, get_bot_app
        from datetime import datetime
        from sqlalchemy import update as sql_update
        
        bot_app = get_bot_app()
        if not bot_app:
            logger.warning("Bot app not available, cannot send warning")
            return
        
        config = get_config()
        bot = bot_app.bot
        chat_id = config.telegram.client_user_id
        
        # Format chat info
        if chat_type == "private":
            chat_info = "💬 Private chat"
        else:
            chat_info = f"💬 {chat_title or 'Unknown Group'}"
        
        sender = user_name or "Unknown User"
        text_preview = truncate_text(message_text, 200)
        
        # Build indicators
        indicators = []
        if has_mention:
            indicators.append("📢 Mention")
        if is_question:
            indicators.append("❓ Question")
        
        indicator_line = f"\n📌 {' | '.join(indicators)}" if indicators else ""
        topic_line = f"\n🏷️ Topic: {topic_summary}" if topic_summary else ""
        
        # Create warning message
        warning_text = f"""
🚨 *IMPORTANT MESSAGE ALERT*

👤 *{sender}*
{chat_info}{topic_line}
📝 "{text_preview}"
{indicator_line}
📈 Priority Score: {priority_score}
⏰ {datetime.utcnow().strftime('%H:%M - %d/%m')}

*Please classify this message:*
        """.strip()
        
        # Send warning with classification buttons
        keyboard = create_priority_keyboard(message_id)
        await bot.send_message(
            chat_id=chat_id,
            text=warning_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard,
        )
        
        # Mark warning as sent in database
        async with get_session() as session:
            await session.execute(
                sql_update(Message)
                .where(Message.id == message_id)
                .values(
                    warning_sent=True,
                    warning_sent_at=datetime.utcnow()
                )
            )
        
        logger.info(f"Warning sent for message {message_id} (score: {priority_score})")
        
    except Exception as e:
        logger.error(f"Failed to send warning for message {message_id}: {e}", exc_info=True)


async def refresh_high_priority_users() -> None:
    """Refresh the cache of high priority user IDs."""
    global _high_priority_users
    
    from sqlalchemy import select
    
    try:
        async with get_session() as session:
            result = await session.execute(
                select(HighPriorityUser.user_id)
            )
            _high_priority_users = {row[0] for row in result.fetchall()}
        
        logger.info(f"Refreshed high priority users cache: {len(_high_priority_users)} users")
    except Exception as e:
        logger.error(f"Failed to refresh high priority users: {e}")


async def save_message(
    telegram_message_id: int,
    chat_id: int,
    chat_title: Optional[str],
    chat_type: str,
    user_id: int,
    user_name: Optional[str],
    message_text: Optional[str],
    timestamp: datetime,
    client_username: Optional[str] = None,
) -> None:
    """
    Save a captured message to the database.
    
    Extracts metadata, calculates priority score, and stores.
    """
    try:
        # Detect metadata
        has_mention = detect_mention(message_text, client_username)
        is_question = detect_question(message_text)
        message_length = len(message_text) if message_text else 0
        is_high_priority = user_id in _high_priority_users
        
        # Calculate priority score
        priority_score = calculate_priority_score(
            message_text=message_text,
            has_mention=has_mention,
            is_question=is_question,
            is_high_priority_user=is_high_priority,
        )
        
        # Generate AI topic summary (non-blocking, with fallback)
        topic_summary = await generate_topic_summary(message_text)
        
        # Create message record
        message = Message(
            telegram_message_id=telegram_message_id,
            chat_id=chat_id,
            chat_title=chat_title,
            chat_type=chat_type,
            user_id=user_id,
            user_name=user_name,
            message_text=message_text,
            timestamp=timestamp,
            has_mention=has_mention,
            is_question=is_question,
            message_length=message_length,
            priority_score=priority_score,
            topic_summary=topic_summary,
        )
        
        async with get_session() as session:
            session.add(message)
            await session.flush()  # Flush to get the message ID
            message_id = message.id
            # Commit happens automatically via context manager
        
        # Check if we should send a real-time warning
        config = get_config()
        if priority_score >= config.scheduler.warning_threshold_score:
            await send_warning_for_message(
                message_id=message_id,
                message_text=message_text,
                user_name=user_name,
                chat_title=chat_title,
                chat_type=chat_type,
                priority_score=priority_score,
                has_mention=has_mention,
                is_question=is_question,
                topic_summary=topic_summary,
            )
        
        # Log safely (no message content!)
        logger.debug(
            f"Saved message {telegram_message_id} from chat {chat_id}, "
            f"user {user_id}, score={priority_score}, "
            f"text={sanitize_for_logging(message_text)}"
        )
        
    except Exception as e:
        logger.error(
            f"Failed to save message {telegram_message_id}: {e}",
            exc_info=True
        )


async def start_userbot() -> None:
    """
    Start the userbot client and begin monitoring messages.
    
    This will:
    1. Connect to Telegram (may require phone code on first run)
    2. Register message handler
    3. Start receiving events
    """
    config = get_config()
    client = await get_userbot_client()
    
    # Get the client's own user info for mention detection
    client_username: Optional[str] = None
    client_user_id: Optional[int] = None
    
    @client.on(events.NewMessage(incoming=True))
    async def handle_new_message(event):
        """Handle incoming messages from all chats."""
        try:
            message = event.message
            chat = await event.get_chat()
            sender = await event.get_sender()
            
            # Skip messages from ourselves
            if sender and sender.id == client_user_id:
                return
            
            # Skip messages from our own bot
            bot_user_id = _get_bot_user_id()
            if sender and sender.id == bot_user_id:
                return
            
            # Skip messages without text (media-only, etc.)
            # Future: could extract captions from media
            if not message.text:
                return
            
            # Get sender info
            if isinstance(sender, User):
                user_name = sender.first_name
                if sender.last_name:
                    user_name += f" {sender.last_name}"
                user_id = sender.id
            else:
                user_name = None
                user_id = sender.id if sender else 0
            
            # Get chat info
            chat_title = None
            if isinstance(chat, (Chat, Channel)):
                chat_title = chat.title
            elif isinstance(chat, User):
                chat_title = f"{chat.first_name} {chat.last_name or ''}".strip()
            
            # Save to database
            await save_message(
                telegram_message_id=message.id,
                chat_id=event.chat_id,
                chat_title=chat_title,
                chat_type=get_chat_type(chat),
                user_id=user_id,
                user_name=user_name,
                message_text=message.text,
                timestamp=message.date.replace(tzinfo=None),  # Store as naive UTC
                client_username=client_username,
            )
            
        except Exception as e:
            logger.error(f"Error handling message: {e}", exc_info=True)
    
    # Start the client
    logger.info("Starting userbot client...")
    
    await client.start(phone=config.telegram.phone)
    
    # Get client info after connecting
    me = await client.get_me()
    client_username = me.username
    client_user_id = me.id
    
    logger.info(f"Userbot connected as @{client_username} (ID: {client_user_id})")
    
    # Refresh high priority users cache
    await refresh_high_priority_users()
    
    # Keep running - this is handled by the main event loop
    logger.info("Userbot is now monitoring messages...")


async def stop_userbot() -> None:
    """Stop the userbot client gracefully."""
    global _userbot_client
    
    if _userbot_client:
        logger.info("Stopping userbot client...")
        await _userbot_client.disconnect()
        _userbot_client = None
        logger.info("Userbot client stopped")


async def run_userbot_standalone() -> None:
    """
    Run userbot as standalone (for testing).
    
    Usage:
        python userbot.py
    """
    from database import init_database, create_tables
    
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    # Initialize database
    await init_database()
    await create_tables()
    
    # Start userbot
    client = await get_userbot_client()
    await start_userbot()
    
    # Run until disconnected
    await client.run_until_disconnected()


if __name__ == "__main__":
    import asyncio
    asyncio.run(run_userbot_standalone())

