"""
Telegram Bot API interface for client communication.
Sends summaries and handles labeling interactions via inline keyboards.
"""

import logging
from typing import Optional

from telegram import (
    Bot,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
)
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
)
from telegram.constants import ParseMode

from config import get_config
from database import get_session
from models import Message
from utils import (
    format_labeling_confirmation,
    get_priority_emoji,
    truncate_text,
)

logger = logging.getLogger(__name__)

# Global bot application
_bot_app: Optional[Application] = None


def create_priority_keyboard(message_id: int) -> InlineKeyboardMarkup:
    """
    Create inline keyboard with priority buttons for a message.
    
    Layout: [🔴 High] [🟡 Medium] [🟢 Low]
    """
    keyboard = [
        [
            InlineKeyboardButton(
                "🔴 High",
                callback_data=f"label:{message_id}:high"
            ),
            InlineKeyboardButton(
                "🟡 Medium",
                callback_data=f"label:{message_id}:medium"
            ),
            InlineKeyboardButton(
                "🟢 Low",
                callback_data=f"label:{message_id}:low"
            ),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


async def handle_label_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle callback when user clicks a priority button.
    
    Callback data format: "label:{message_id}:{priority}"
    """
    query = update.callback_query
    await query.answer()  # Acknowledge the callback
    
    try:
        # Parse callback data
        parts = query.data.split(":")
        if len(parts) != 3 or parts[0] != "label":
            logger.warning(f"Invalid callback data: {query.data}")
            return
        
        _, message_id_str, label = parts
        message_id = int(message_id_str)
        
        if label not in ("high", "medium", "low"):
            logger.warning(f"Invalid label: {label}")
            return
        
        # Update database
        from sqlalchemy import select, update as sql_update
        from datetime import datetime
        
        async with get_session() as session:
            # Get the message
            result = await session.execute(
                select(Message).where(Message.id == message_id)
            )
            message = result.scalar_one_or_none()
            
            if not message:
                await query.edit_message_text("❌ Message not found in database")
                return
            
            # Update the label
            await session.execute(
                sql_update(Message)
                .where(Message.id == message_id)
                .values(
                    label=label,
                    labeled_at=datetime.utcnow()
                )
            )
            
            message_preview = message.message_text
        
        # Update the message to show confirmation
        emoji = get_priority_emoji(label)
        confirmation = f"{emoji} Marked as *{label.title()}* Priority"
        
        # Edit to remove buttons and show confirmation
        await query.edit_message_text(
            f"{query.message.text}\n\n{confirmation}",
            parse_mode=ParseMode.MARKDOWN,
        )
        
        logger.info(f"Message {message_id} labeled as {label}")
        
    except Exception as e:
        logger.error(f"Error handling label callback: {e}", exc_info=True)
        await query.edit_message_text(
            f"❌ Error processing label: {str(e)}"
        )


async def handle_start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command."""
    config = get_config()
    
    # Only respond to the authorized client
    if update.effective_user.id != config.telegram.client_user_id:
        await update.message.reply_text(
            "⛔ Sorry, this bot is private and only responds to its owner."
        )
        return
    
    welcome_message = """
🤖 *Telegram Secretary Bot*

I'm your personal message assistant! Here's what I do:

📥 *Capture* all your incoming messages
🚨 *Warn* you immediately about important messages
📊 *Analyze* and prioritize them
📝 *Summarize* messages every few hours
🏷️ *Learn* from your classifications to improve over time

*Available Commands:*
/start - Show this message
/summary - Get a summary now
/stats - View message statistics
/settings - View current settings

*How it works:*
• I'll send you real-time alerts for high-priority messages
• You can classify each message as: 🔴 Important, 🟡 Semi, or 🟢 Non-Important
• I'll send periodic summaries every {hours} hours
• Your classifications help me learn what's important to you
    """.format(hours=config.scheduler.summary_interval_hours)
    
    await update.message.reply_text(
        welcome_message,
        parse_mode=ParseMode.MARKDOWN
    )


async def handle_summary_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /summary command - trigger manual summary."""
    config = get_config()
    
    # Only respond to the authorized client
    if update.effective_user.id != config.telegram.client_user_id:
        return
    
    await update.message.reply_text("⏳ Generating summary...")
    
    # Import here to avoid circular imports
    from scheduler import generate_and_send_summary
    await generate_and_send_summary()


async def handle_stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /stats command - show message statistics."""
    config = get_config()
    
    # Only respond to the authorized client
    if update.effective_user.id != config.telegram.client_user_id:
        return
    
    from sqlalchemy import func, select
    from datetime import datetime, timedelta
    
    try:
        async with get_session() as session:
            # Total messages
            total_result = await session.execute(
                select(func.count(Message.id))
            )
            total = total_result.scalar()
            
            # Messages in last 24 hours
            day_ago = datetime.utcnow() - timedelta(hours=24)
            recent_result = await session.execute(
                select(func.count(Message.id))
                .where(Message.timestamp >= day_ago)
            )
            recent = recent_result.scalar()
            
            # Labeled messages
            labeled_result = await session.execute(
                select(func.count(Message.id))
                .where(Message.label.isnot(None))
            )
            labeled = labeled_result.scalar()
            
            # Label breakdown
            high_count = (await session.execute(
                select(func.count(Message.id)).where(Message.label == "high")
            )).scalar()
            
            medium_count = (await session.execute(
                select(func.count(Message.id)).where(Message.label == "medium")
            )).scalar()
            
            low_count = (await session.execute(
                select(func.count(Message.id)).where(Message.label == "low")
            )).scalar()
        
        stats_message = f"""
📊 *Message Statistics*

*Total Messages:* {total}
*Last 24 Hours:* {recent}
*Labeled:* {labeled}

*Label Breakdown:*
🔴 High: {high_count}
🟡 Medium: {medium_count}
🟢 Low: {low_count}
⚪ Unlabeled: {total - labeled}
        """
        
        await update.message.reply_text(
            stats_message,
            parse_mode=ParseMode.MARKDOWN
        )
        
    except Exception as e:
        logger.error(f"Error generating stats: {e}", exc_info=True)
        await update.message.reply_text(
            f"❌ Error generating statistics: {str(e)}"
        )


async def handle_settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /settings command - show current settings."""
    config = get_config()
    
    # Only respond to the authorized client
    if update.effective_user.id != config.telegram.client_user_id:
        return
    
    settings_message = f"""
⚙️ *Current Settings*

*Summary Interval:* Every {config.scheduler.summary_interval_hours} hours
*Max Messages per Summary:* {config.scheduler.max_messages_per_summary}
*Minimum Priority Score:* {config.scheduler.min_priority_score}
*Warning Threshold Score:* {config.scheduler.warning_threshold_score}
*Timezone:* {config.scheduler.timezone}

_Settings can be changed via environment variables._
    """
    
    await update.message.reply_text(
        settings_message,
        parse_mode=ParseMode.MARKDOWN
    )


async def send_message_card(
    bot: Bot,
    chat_id: int,
    message: Message,
    index: int,
) -> None:
    """
    Send a single message card with inline keyboard.
    
    This is sent as a separate message so each has its own buttons.
    """
    # Determine chat type display
    if message.chat_type == "private":
        chat_info = "💬 Private chat"
    else:
        chat_info = f"💬 {message.chat_title or 'Unknown Group'}"
    
    sender = message.user_name or f"User {message.user_id}"
    text_preview = truncate_text(message.message_text, 150)
    
    # Topic summary from AI (if available)
    topic_line = f"\n🏷️ Topic: {message.topic_summary}" if message.topic_summary else ""
    
    # Build indicators
    indicators = []
    if message.has_mention:
        indicators.append("📢 Mention")
    if message.is_question:
        indicators.append("❓ Question")
    
    indicator_line = f"\n📌 {' | '.join(indicators)}" if indicators else ""
    
    # Score indicator
    score_line = f"📈 Score: {message.priority_score}"
    
    card_text = f"""
*{index}.* 👤 *{sender}*
{chat_info}{topic_line}
📝 "{text_preview}"
{indicator_line}
{score_line}
⏰ {message.timestamp.strftime('%H:%M - %d/%m')}
    """.strip()
    
    keyboard = create_priority_keyboard(message.id)
    
    await bot.send_message(
        chat_id=chat_id,
        text=card_text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=keyboard,
    )


async def send_summary(
    messages: list[Message],
    total_messages: int,
    total_chats: int,
    time_range_hours: int,
) -> None:
    """
    Send a complete summary to the client.
    
    Sends header, then each message as separate card with buttons.
    """
    config = get_config()
    bot = _bot_app.bot
    chat_id = config.telegram.client_user_id
    
    # Send header
    header = f"""
📊 *Summary of last {time_range_hours} hours*

You received *{total_messages}* messages in *{total_chats}* conversations.
Top *{len(messages)}* messages by priority score:

━━━━━━━━━━━━━━━━━━━━
    """.strip()
    
    await bot.send_message(
        chat_id=chat_id,
        text=header,
        parse_mode=ParseMode.MARKDOWN,
    )
    
    # Send each message as a card
    for i, message in enumerate(messages, 1):
        await send_message_card(bot, chat_id, message, i)
    
    # Send footer
    footer = f"""
━━━━━━━━━━━━━━━━━━━━

🏷️ *Label Guide:*
🔴 High - Needs immediate attention
🟡 Medium - Moderate importance
🟢 Low - Can wait or ignore

Tap the buttons above to classify each message.
    """.strip()
    
    await bot.send_message(
        chat_id=chat_id,
        text=footer,
        parse_mode=ParseMode.MARKDOWN,
    )


async def send_simple_message(text: str) -> None:
    """Send a simple text message to the client."""
    config = get_config()
    
    if _bot_app:
        await _bot_app.bot.send_message(
            chat_id=config.telegram.client_user_id,
            text=text,
            parse_mode=ParseMode.MARKDOWN,
        )


def get_bot_app() -> Optional[Application]:
    """Get the bot application instance."""
    return _bot_app


async def start_bot() -> Application:
    """
    Initialize and start the Telegram bot.
    
    Returns the Application instance (doesn't block).
    """
    global _bot_app
    
    config = get_config()
    
    # Create application
    _bot_app = (
        Application.builder()
        .token(config.telegram.bot_token)
        .build()
    )
    
    # Register handlers
    _bot_app.add_handler(CommandHandler("start", handle_start_command))
    _bot_app.add_handler(CommandHandler("summary", handle_summary_command))
    _bot_app.add_handler(CommandHandler("stats", handle_stats_command))
    _bot_app.add_handler(CommandHandler("settings", handle_settings_command))
    _bot_app.add_handler(CallbackQueryHandler(handle_label_callback))
    
    # Initialize the application
    await _bot_app.initialize()
    await _bot_app.start()
    
    # Start polling in background
    await _bot_app.updater.start_polling(drop_pending_updates=True)
    
    logger.info("Bot started and polling for updates")
    
    return _bot_app


async def stop_bot() -> None:
    """Stop the bot gracefully."""
    global _bot_app
    
    if _bot_app:
        logger.info("Stopping bot...")
        await _bot_app.updater.stop()
        await _bot_app.stop()
        await _bot_app.shutdown()
        _bot_app = None
        logger.info("Bot stopped")


async def run_bot_standalone() -> None:
    """
    Run bot as standalone (for testing).
    
    Usage:
        python bot.py
    """
    from database import init_database, create_tables
    
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    # Initialize database
    await init_database()
    await create_tables()
    
    # Start bot
    app = await start_bot()
    
    # Run until stopped
    logger.info("Bot running. Press Ctrl+C to stop.")
    
    try:
        # Keep running
        import asyncio
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        await stop_bot()


if __name__ == "__main__":
    import asyncio
    asyncio.run(run_bot_standalone())

