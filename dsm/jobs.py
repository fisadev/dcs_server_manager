import logging
from functools import partial

from flask_apscheduler import APScheduler

from dsm import config


# scheduler singleton, we won't need more than one
scheduler = APScheduler()
logger = logging.getLogger(__name__)


def launch():
    """
    Configure the APScheduler and add it to the web app. Then add and start running its jobs.
    """
    # to avoid a circular import
    from dsm import web

    scheduler.init_app(web.app)
    scheduler.start()

    schedule_jobs()


def schedule_jobs():
    """
    Schedule all the periodic jobs into the APScheduler that runs inside the web app.
    """
    # to avoid a circular import
    from dsm.web import SERVERS

    # if any jobs are already scheduled, remove them (useful when modifying the config)
    scheduler.pause()
    for job in scheduler.get_jobs():
        job.remove()
    scheduler.resume()

    for server_name, server_module in SERVERS.items():
        check_every_seconds = config.current[f"{server_name.upper()}_SERVER_CHECK_EVERY_SECONDS"]
        if check_every_seconds:
            scheduler.add_job(
                func=server_module.ensure_up,
                trigger="interval",
                id=f"{server_name}_ensure_up",
                seconds=check_every_seconds,
                misfire_grace_time=10,
            )

        restart_hour = config.current[f"{server_name.upper()}_SERVER_RESTART_DAILY_AT_HOUR"]
        if restart_hour:
            scheduler.add_job(
                func=server_module.restart,
                trigger="cron",
                id=f"{server_name}_restart_daily",
                hour=restart_hour,
                misfire_grace_time=10,
            )
