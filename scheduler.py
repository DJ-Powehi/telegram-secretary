"""
APScheduler-based scheduler for periodic summary generation.
Runs every N hours (configurable) to create and send message summaries.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import func, select, update as sql_update

from config import get_config
from database import get_session
from models import Message

logger = logging.getLogger(__name__)

# Global scheduler instance
_scheduler: Optional[AsyncIOScheduler] = None


async def get_unlabeled_messages(hours: int, limit: int) -> list[Message]:
    """
    Get unlabeled messages from the last N hours, sorted by priority score.
    
    Args:
        hours: Number of hours to look back
        limit: Maximum number of messages to return
    
    Returns:
        List of Message objects sorted by priority_score DESC
    """
    config = get_config()
    cutoff_time = datetime.utcnow() - timedelta(hours=hours)
    
    async with get_session() as session:
        result = await session.execute(
            select(Message)
            .where(
                Message.timestamp >= cutoff_time,
                Message.label.is_(None),
                Message.included_in_summary == False,
                Message.priority_score >= config.scheduler.min_priority_score,
            )
            .order_by(Message.priority_score.desc(), Message.timestamp.desc())
            .limit(limit)
        )
        messages = result.scalars().all()
        
        # Mark these messages as included in summary
        if messages:
            message_ids = [m.id for m in messages]
            await session.execute(
                sql_update(Message)
                .where(Message.id.in_(message_ids))
                .values(
                    included_in_summary=True,
                    summary_sent_at=datetime.utcnow()
                )
            )
    
    return list(messages)


async def get_message_stats(hours: int) -> tuple[int, int]:
    """
    Get statistics about messages in the time range.
    
    Returns:
        Tuple of (total_messages, unique_chats)
    """
    cutoff_time = datetime.utcnow() - timedelta(hours=hours)
    
    async with get_session() as session:
        # Total messages
        total_result = await session.execute(
            select(func.count(Message.id))
            .where(Message.timestamp >= cutoff_time)
        )
        total_messages = total_result.scalar() or 0
        
        # Unique chats
        chats_result = await session.execute(
            select(func.count(func.distinct(Message.chat_id)))
            .where(Message.timestamp >= cutoff_time)
        )
        unique_chats = chats_result.scalar() or 0
    
    return total_messages, unique_chats


async def generate_and_send_summary() -> None:
    """
    Generate and send a summary of recent messages.
    
    This is the main scheduled job that runs every N hours.
    """
    from bot import send_summary, send_simple_message
    
    config = get_config()
    hours = config.scheduler.summary_interval_hours
    max_messages = config.scheduler.max_messages_per_summary
    
    logger.info(f"Generating summary for last {hours} hours...")
    
    try:
        # Get statistics
        total_messages, unique_chats = await get_message_stats(hours)
        
        if total_messages == 0:
            logger.info("No messages in time range, skipping summary")
            await send_simple_message(
                f"📊 *Summary of last {hours} hours*\n\n"
                "No new messages received. Enjoy the quiet! 🧘"
            )
            return
        
        # Get top messages
        messages = await get_unlabeled_messages(hours, max_messages)
        
        if not messages:
            logger.info("No unlabeled messages to summarize")
            await send_simple_message(
                f"📊 *Summary of last {hours} hours*\n\n"
                f"You received *{total_messages}* messages, "
                "but none need your attention right now. ✅"
            )
            return
        
        # Send summary
        await send_summary(
            messages=messages,
            total_messages=total_messages,
            total_chats=unique_chats,
            time_range_hours=hours,
        )
        
        logger.info(
            f"Summary sent: {len(messages)} messages from {total_messages} total"
        )
        
    except Exception as e:
        logger.error(f"Error generating summary: {e}", exc_info=True)
        try:
            await send_simple_message(
                f"❌ Error generating summary: {str(e)}\n\n"
                "Please check the logs for details."
            )
        except Exception:
            pass


def is_quiet_hours() -> bool:
    """
    Check if current time is within quiet hours.
    
    Returns True if summaries should be suppressed.
    """
    # TODO: Implement quiet hours check from user preferences
    # For now, always return False (no quiet hours)
    return False


async def scheduled_summary_job() -> None:
    """
    Scheduled job wrapper that checks conditions before generating summary.
    """
    if is_quiet_hours():
        logger.info("Quiet hours active, skipping summary")
        return
    
    await generate_and_send_summary()


def get_scheduler() -> Optional[AsyncIOScheduler]:
    """Get the scheduler instance."""
    return _scheduler


async def start_scheduler() -> AsyncIOScheduler:
    """
    Initialize and start the APScheduler.
    
    Schedules the summary job to run at configured intervals.
    """
    global _scheduler
    
    config = get_config()
    
    # Create scheduler with timezone
    timezone = pytz.timezone(config.scheduler.timezone)
    _scheduler = AsyncIOScheduler(timezone=timezone)
    
    # Add the summary job
    _scheduler.add_job(
        scheduled_summary_job,
        trigger=IntervalTrigger(hours=config.scheduler.summary_interval_hours),
        id="summary_job",
        name="Generate and send message summary",
        replace_existing=True,
        # Run first summary after startup delay
        next_run_time=datetime.now(timezone) + timedelta(minutes=5),
    )
    
    # Start the scheduler
    _scheduler.start()
    
    logger.info(
        f"Scheduler started. Summary job runs every "
        f"{config.scheduler.summary_interval_hours} hours. "
        f"First run in 5 minutes."
    )
    
    return _scheduler


async def stop_scheduler() -> None:
    """Stop the scheduler gracefully."""
    global _scheduler
    
    if _scheduler:
        logger.info("Stopping scheduler...")
        _scheduler.shutdown(wait=True)
        _scheduler = None
        logger.info("Scheduler stopped")


async def trigger_summary_now() -> None:
    """
    Manually trigger a summary immediately.
    
    Useful for testing or on-demand summaries.
    """
    logger.info("Manual summary triggered")
    await generate_and_send_summary()


async def run_scheduler_standalone() -> None:
    """
    Run scheduler as standalone (for testing).
    
    Usage:
        python scheduler.py
    """
    from database import init_database, create_tables
    from bot import start_bot
    
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    # Initialize database
    await init_database()
    await create_tables()
    
    # Start bot (needed for sending summaries)
    await start_bot()
    
    # Start scheduler
    await start_scheduler()
    
    # Run until stopped
    logger.info("Scheduler running. Press Ctrl+C to stop.")
    
    try:
        import asyncio
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        await stop_scheduler()


if __name__ == "__main__":
    import asyncio
    asyncio.run(run_scheduler_standalone())

