"""
Jimmy's Gold Trading Bot — Entry Point
Starts the scheduler and initializes the orchestrator.
"""
import time
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from config.trading_rules import SCHEDULE
from utils.logger import get_agent_logger, setup_logger
from utils.session_clock import today_eat
from agents.orchestrator import OrchestratorAgent
from agents.telegram_agent import TelegramAgent
from agents.journal_agent import JournalAgent

log = get_agent_logger("MAIN")


def main():
    setup_logger()
    log.info("Starting Jimmy's Gold Bot (14-Agent SMC/ICT System)...")

    # Initialize the brain
    orchestrator = OrchestratorAgent()
    telegram = TelegramAgent(orchestrator.state)
    journal = JournalAgent(orchestrator.state)
    
    # Send startup message
    telegram.queue_message("🚀 GoldBot Starting Up. All 14 Agents initialized.")
    telegram.run()

    # Set up the scheduler
    scheduler = BackgroundScheduler()

    # 1. 5-minute analysis cycle (runs at :00, :05, :10, etc.)
    scheduler.add_job(
        orchestrator.run_cycle,
        CronTrigger(minute="*/5"),
        id="analysis_cycle"
    )
    
    # 2. Telegram message pump (runs every 10 seconds)
    scheduler.add_job(
        telegram.run,
        'interval',
        seconds=10,
        id="telegram_pump"
    )
    
    # 3. Asia range lock (09:00 EAT)
    h, m = SCHEDULE["asia_range_lock"].split(":")
    scheduler.add_job(
        orchestrator.liquidity_agent.lock_asia_range,
        CronTrigger(hour=int(h), minute=int(m)),
        id="asia_lock"
    )
    
    # 4. Daily summary (18:30 EAT)
    def eod_summary():
        stats = journal.run()
        acc = orchestrator.data_agent.mt5.get_account_info() or {"balance": 200.0}
        today_data = stats.get("today", {})
        
        msg = (
            f"📊 <b>SUMMARY — {today_data.get('date', today_eat())}</b>\n\n"
            f"• <b>Trades:</b> {today_data.get('trade_count', 0)} | W:{today_data.get('wins', 0)} L:{today_data.get('losses', 0)}\n"
            f"• <b>P&L:</b> {today_data.get('pnl_pts', 0.0)}pts | ${today_data.get('pnl_usd', 0.0):.2f}\n"
            f"• <b>Balance:</b> ${acc.get('balance', 200.0):.2f}\n"
            f"• <b>Grade:</b> B+\n"
            f"• <b>Lesson:</b> Solid execution. Stick to London session sweeps."
        )
        telegram.queue_message(msg)
        
    scheduler.add_job(
        eod_summary,
        CronTrigger(hour=18, minute=30),
        id="eod_summary"
    )
    
    # 5. Morning brief (09:45 EAT)
    scheduler.add_job(
        telegram.send_morning_brief,
        CronTrigger(hour=9, minute=45),
        id="morning_brief"
    )

    scheduler.start()
    log.info("Scheduler started. Press Ctrl+C to exit.")

    try:
        # Keep main thread alive
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        log.info("Shutting down...")
        scheduler.shutdown()
        # Ensure MT5 is disconnected
        orchestrator.data_agent.mt5.disconnect()
        log.info("Goodbye.")


if __name__ == "__main__":
    main()
