import logging
from functools import partial

from flask_apscheduler import APScheduler

from dsm import config
from dsm import processes


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
    # if any jobs are already scheduled, remove them (useful when modifying the config)
    scheduler.pause()
    for job in scheduler.get_jobs():
        job.remove()
    scheduler.resume()

    for server_configs_prefix in ("DCS", "SRS"):
        check_interval = config.current[f"{server_configs_prefix}_SERVER_CHECK_INTERVAL_SECONDS"]
        if check_interval:
            scheduler.add_job(
                func=partial(processes.check_server_up, server_configs_prefix),
                trigger="interval",
                id=f"check_{server_configs_prefix}_server_up",
                seconds=check_interval,
                misfire_grace_time=10,
            )

        restart_hour = config.current[f"{server_configs_prefix}_SERVER_DAILY_RESTART_AT_HOUR"]
        if restart_hour:
            scheduler.add_job(
                func=partial(processes.restart_server, server_configs_prefix),
                trigger="cron",
                id=f"restart_{server_configs_prefix}_server",
                hour=restart_hour,
                misfire_grace_time=10,
            )
