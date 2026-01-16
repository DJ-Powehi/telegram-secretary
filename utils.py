"""
Utility functions for Telegram Secretary Bot.
Includes scoring system, message formatting, and helper functions.
"""

import logging
import re
from datetime import datetime
from typing import Optional

from models import Message

logger = logging.getLogger(__name__)


# Priority score weights
SCORE_MENTION = 3
SCORE_QUESTION = 2
SCORE_LONG_MESSAGE = 1  # > 100 chars
SCORE_HIGH_PRIORITY_USER = 2
MIN_LONG_MESSAGE_LENGTH = 100


def calculate_priority_score(
    message_text: Optional[str],
    has_mention: bool,
    is_question: bool,
    is_high_priority_user: bool = False
) -> int:
    """
    Calculate priority score for a message based on simple rules.
    
    Scoring:
        - Has @mention: +3 points
        - Is a question (ends with ?): +2 points
        - Text length > 100 chars: +1 point
        - Sender is marked high priority: +2 points
    
    Returns:
        Integer priority score
    """
    score = 0
    
    if has_mention:
        score += SCORE_MENTION
    
    if is_question:
        score += SCORE_QUESTION
    
    if message_text and len(message_text) > MIN_LONG_MESSAGE_LENGTH:
        score += SCORE_LONG_MESSAGE
    
    if is_high_priority_user:
        score += SCORE_HIGH_PRIORITY_USER
    
    return score


def detect_mention(text: Optional[str], username: Optional[str] = None) -> bool:
    """
    Detect if message contains an @mention.
    
    Args:
        text: Message text
        username: Optional specific username to check for
    
    Returns:
        True if mention detected
    """
    if not text:
        return False
    
    # General @mention pattern
    mention_pattern = r"@\w+"
    
    if username:
        # Check for specific username mention
        return f"@{username}" in text.lower() or bool(re.search(mention_pattern, text))
    
    return bool(re.search(mention_pattern, text))


def detect_question(text: Optional[str]) -> bool:
    """
    Detect if message is a question.
    
    Checks for:
        - Ends with ?
        - Contains question words (optional enhancement)
    
    Returns:
        True if message appears to be a question
    """
    if not text:
        return False
    
    text = text.strip()
    
    # Primary check: ends with question mark
    if text.endswith("?"):
        return True
    
    # Secondary check: starts with common question words
    question_starters = [
        "what", "when", "where", "why", "how", "who", "which",
        "is ", "are ", "do ", "does ", "can ", "could ", "would ", "will ",
        "should ", "have ", "has ", "did ",
        # Portuguese question words
        "que ", "qual ", "quem ", "quando ", "onde ", "como ", "por que",
        "você ", "vocês ",
    ]
    
    text_lower = text.lower()
    for starter in question_starters:
        if text_lower.startswith(starter):
            return True
    
    return False


def truncate_text(text: Optional[str], max_length: int = 200) -> str:
    """Truncate text to max length with ellipsis."""
    if not text:
        return "[No text]"
    
    if len(text) <= max_length:
        return text
    
    return text[:max_length - 3] + "..."


def get_priority_emoji(label: Optional[str]) -> str:
    """Get emoji for priority label."""
    return {
        "high": "🔴",
        "medium": "🟡",
        "low": "🟢",
    }.get(label, "⚪")


def get_priority_from_score(score: int) -> str:
    """Suggest initial priority based on score."""
    if score >= 5:
        return "high"
    elif score >= 3:
        return "medium"
    else:
        return "low"


def format_summary_header(
    total_messages: int,
    total_chats: int,
    time_range_hours: int
) -> str:
    """Format the header for a summary message."""
    return (
        f"📊 *Summary of last {time_range_hours} hours*\n"
        f"You received *{total_messages}* messages in *{total_chats}* conversations.\n"
        f"━━━━━━━━━━━━━━━━━━━━"
    )


def format_message_card(
    message: Message,
    index: int,
    suggested_priority: Optional[str] = None
) -> str:
    """
    Format a single message for the summary.
    
    Returns:
        Formatted message card string
    """
    # Determine chat type display
    if message.chat_type == "private":
        chat_info = "💬 Private chat"
    else:
        chat_info = f"💬 Group: {message.chat_title or 'Unknown'}"
    
    # Format sender name
    sender = message.user_name or f"User {message.user_id}"
    
    # Truncate message text
    text = truncate_text(message.message_text, 150)
    
    # Build indicators
    indicators = []
    if message.has_mention:
        indicators.append("📢 Mention")
    if message.is_question:
        indicators.append("❓ Question")
    
    indicator_str = " | ".join(indicators) if indicators else ""
    
    # Suggested priority based on score
    if suggested_priority:
        priority_indicator = f"{get_priority_emoji(suggested_priority)} Suggested: {suggested_priority.title()}"
    else:
        priority_indicator = ""
    
    # Build card
    lines = [
        f"\n*{index}.* 👤 *{sender}*",
        chat_info,
        f"📝 \"{text}\"",
    ]
    
    if indicator_str:
        lines.append(f"📌 {indicator_str}")
    
    if priority_indicator:
        lines.append(priority_indicator)
    
    lines.append(f"⏰ {message.timestamp.strftime('%H:%M')}")
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    
    return "\n".join(lines)


def format_summary_footer(labeled_count: int, pending_count: int) -> str:
    """Format the footer for a summary message."""
    if pending_count > 0:
        return f"\n⏳ {pending_count} messages waiting for your review"
    else:
        return f"\n✅ All {labeled_count} messages have been labeled!"


def format_labeling_confirmation(label: str, message_preview: str) -> str:
    """Format confirmation message after labeling."""
    emoji = get_priority_emoji(label)
    return f"{emoji} Marked as *{label.title()}* Priority\n\n_{truncate_text(message_preview, 50)}_"


def get_chat_type(chat) -> str:
    """
    Determine chat type from Telethon chat object.
    
    Returns one of: 'private', 'group', 'supergroup', 'channel'
    """
    from telethon.tl.types import (
        Channel,
        Chat,
        User,
    )
    
    if isinstance(chat, User):
        return "private"
    elif isinstance(chat, Chat):
        return "group"
    elif isinstance(chat, Channel):
        if chat.megagroup:
            return "supergroup"
        return "channel"
    
    return "unknown"


def sanitize_for_logging(text: Optional[str]) -> str:
    """
    Sanitize message text for logging.
    Returns a safe representation without actual content.
    
    SECURITY: Never log actual message content.
    """
    if not text:
        return "[empty]"
    return f"[{len(text)} chars]"


def escape_markdown(text: str) -> str:
    """Escape special characters for Telegram MarkdownV2."""
    special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for char in special_chars:
        text = text.replace(char, f'\\{char}')
    return text


async def generate_topic_summary(text: Optional[str]) -> Optional[str]:
    """
    Generate a 3-word topic summary using local Ollama LLM.
    
    Args:
        text: Message text to summarize
    
    Returns:
        3-word topic summary or None if Ollama unavailable
    """
    if not text or len(text) < 10:
        return None
    
    try:
        import ollama
        import asyncio
        import os
        
        # SECURITY: Explicitly use localhost to ensure no external data transmission
        # Only process locally - never send to remote Ollama instances
        ollama_host = os.getenv('OLLAMA_HOST', 'http://localhost:11434')
        if not ollama_host.startswith(('http://localhost', 'http://127.0.0.1')):
            logger.warning(f"OLLAMA_HOST is set to {ollama_host} - this may send data externally! Using localhost instead.")
            ollama_host = 'http://localhost:11434'
        
        # Truncate very long messages to avoid slow processing
        truncated = text[:500] if len(text) > 500 else text
        
        prompt = f"""Summarize this message in EXACTLY 3 words. Be specific about the topic.

Message: "{truncated}"

Reply with ONLY 3 words, nothing else. Example: "Meeting schedule request" or "Christmas party invitation" or "Project deadline reminder"

3-word summary:"""
        
        # Run in thread to not block async loop
        def call_ollama():
            # Use explicit localhost client to ensure privacy
            client = ollama.Client(host=ollama_host)
            response = client.chat(
                model='llama3.2:3b',
                messages=[{'role': 'user', 'content': prompt}],
                options={'num_predict': 20, 'temperature': 0.3}
            )
            return response['message']['content'].strip()
        
        # Run with timeout
        loop = asyncio.get_event_loop()
        result = await asyncio.wait_for(
            loop.run_in_executor(None, call_ollama),
            timeout=5.0  # 5 second timeout
        )
        
        # Clean up result - take only first 3-5 words
        words = result.split()[:5]
        return ' '.join(words)
        
    except ImportError:
        # Ollama not installed
        return None
    except asyncio.TimeoutError:
        # Ollama too slow
        return None
    except Exception:
        # Ollama not running or other error
        return None

