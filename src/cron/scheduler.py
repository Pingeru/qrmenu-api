import os

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from src.cron.cleanup_jobs import (
    cleanup_orphaned_data,
    delete_cancelled_orders_older_than,
)


def _should_start_scheduler(app) -> bool:
    if app.debug:
        return os.environ.get("WERKZEUG_RUN_MAIN") == "true"
    return True


def start_scheduler(app) -> BackgroundScheduler | None:
    if not _should_start_scheduler(app):
        return None

    scheduler = BackgroundScheduler(timezone="UTC")

    def _run_with_context(func, *args, **kwargs):
        with app.app_context():
            return func(*args, **kwargs)

    scheduler.add_job(
        lambda: _run_with_context(delete_cancelled_orders_older_than, 3),
        CronTrigger(minute=0),
        id="cleanup_cancelled_orders_hourly",
        replace_existing=True,
    )

    scheduler.add_job(
        lambda: _run_with_context(cleanup_orphaned_data, app.root_path),
        CronTrigger(day_of_week="sun", hour=3, minute=0),
        id="cleanup_orphaned_weekly",
        replace_existing=True,
    )

    scheduler.start()
    return scheduler

