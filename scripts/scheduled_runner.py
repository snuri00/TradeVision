import sys
import json
from pathlib import Path
from datetime import datetime
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from apscheduler.schedulers.blocking import BlockingScheduler
from trader.db import init_db
from trader.analysis.signals import scan_watchlist_signals
from trader.analysis.discovery import scan_volume_anomalies, scan_gap_moves
from trader.analysis.sentiment import get_fear_greed_proxy
from trader.reports.performance import save_daily_snapshot, get_performance_report


def job_morning_scan():
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    print(f"\n{'='*60}")
    print(f"[{now}] MORNING SCAN")
    print(f"{'='*60}")

    sentiment = get_fear_greed_proxy()
    print(f"\nMarket Sentiment: {sentiment['label']} ({sentiment['score']}/100)")
    for s in sentiment["signals"]:
        print(f"  - {s}")

    print("\nScanning watchlist signals...")
    signals = scan_watchlist_signals()
    if signals["buy_signals"]:
        print(f"\n  BUY SIGNALS ({len(signals['buy_signals'])}):")
        for s in signals["buy_signals"][:5]:
            print(f"    {s['symbol']} @ {s['price']} | RSI: {s.get('rsi')} | Score: {s['buy_score']}")
    if signals["sell_signals"]:
        print(f"\n  SELL SIGNALS ({len(signals['sell_signals'])}):")
        for s in signals["sell_signals"][:5]:
            print(f"    {s['symbol']} @ {s['price']} | RSI: {s.get('rsi')} | Score: {s['sell_score']}")

    print("\nScanning volume anomalies...")
    anomalies = scan_volume_anomalies(top_n=5)
    if anomalies:
        print(f"  Found {len(anomalies)} anomalies:")
        for a in anomalies:
            print(f"    {a['symbol']} | Vol: {a['volume_ratio']}x | {a['change_pct']:+.1f}%")

    print("\nScanning gap moves...")
    gaps = scan_gap_moves(top_n=5)
    if gaps:
        print(f"  Found {len(gaps)} gaps:")
        for g in gaps:
            print(f"    {g['symbol']} | Gap: {g['gap_pct']:+.1f}% | Filled: {g['gap_filled']}")


def job_daily_snapshot():
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    print(f"\n[{now}] Saving daily snapshot...")
    save_daily_snapshot()
    print("  Done.")


def job_weekly_report():
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    print(f"\n{'='*60}")
    print(f"[{now}] WEEKLY PERFORMANCE REPORT")
    print(f"{'='*60}")
    report = get_performance_report("weekly")
    print(json.dumps(report, indent=2, default=str, ensure_ascii=False))


def main():
    init_db()
    scheduler = BlockingScheduler()

    scheduler.add_job(job_morning_scan, "cron", hour=9, minute=30,
                       id="morning_scan", name="Morning Market Scan")

    scheduler.add_job(job_daily_snapshot, "cron", hour=18, minute=0,
                       id="daily_snapshot", name="Daily Performance Snapshot")

    scheduler.add_job(job_weekly_report, "cron", day_of_week="fri", hour=18, minute=30,
                       id="weekly_report", name="Weekly Report")

    print("TradeVision Scheduler Started")
    print(f"  Morning Scan:    09:30 daily")
    print(f"  Daily Snapshot:  18:00 daily")
    print(f"  Weekly Report:   18:30 Friday")
    print("Press Ctrl+C to stop\n")

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        print("\nScheduler stopped.")


if __name__ == "__main__":
    main()
