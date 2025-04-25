"""
This module handles the interaction with the DCS server.
It is meant to be used as a singleton, like this:

from dsm import dcs
dcs.start()
print(dcs.current_status())
# and more...

This simplifies a lots of things, as we will never need to have multiple instances of this at the
same time.
"""
from datetime import datetime
from logging import getLogger
from enum import Enum

import requests

from dsm import config
from dsm import processes


logger = getLogger(__name__)


DCSServerStatus = Enum("DCSServerStatus", "RUNNING NOT_RUNNING NON_RESPONSIVE PROBABLY_BOOTING")


last_start = datetime.now()


def is_responsive():
    """
    Check if the DCS server is responsive (if not it's probably because it's frozen with an error).
    We consider it responsive when it answers a specific request that we got from
    https://github.com/ActiumDev/dcs-server-wine/blob/main/bin/dcs-watchdog.py
    """
    url = f"http://localhost:{config.current['DCS_SERVER_WEB_UI_PORT']}/encryptedRequest"
    body = {"ct": "/E5LnS99K/cq4BfuE9SwhgOVyvoFAD1FoJ+N0GhmhKg=", "iv": "rNuGPsuOIrY4NogYU01HIw=="}

    try:
        response = requests.post(url, json=body, timeout=30)
        if response.status_code == 200:
            return True
    except Exception as e:
        logger.warning(
            "Assuming DCS server down after failing to answer responsiveness check: %s", type(e)
        )

    return False


def current_status():
    """
    Check if the DCS server is up and running.
    """
    exe_path = config.current["DCS_SERVER_EXE_PATH"]
    exe_name = processes.get_exe_name(exe_path)

    process = processes.find(exe_name)

    if process:
        if is_responsive():
            if (datetime.now() - last_start).total_seconds() < config.current["DCS_SERVER_BOOT_TIMEOUT_SECONDS"]:
                return DCSServerStatus.PROBABLY_BOOTING
            else:
                return DCSServerStatus.RUNNING
        else:
            return DCSServerStatus.NON_RESPONSIVE
    else:
        return DCSServerStatus.NOT_RUNNING


def current_resources():
    """
    Get the current resources used by the DCS server.
    """
    exe_path = config.current["DCS_SERVER_EXE_PATH"]
    exe_name = processes.get_exe_name(exe_path)

    return processes.find(exe_name)


def start():
    """
    Start the DCS server.
    """
    global last_start

    exe_path = config.current["DCS_SERVER_EXE_PATH"]
    arguments = config.current["DCS_SERVER_EXE_ARGUMENTS"]

    logger.info("Starting DCS server...")

    started = processes.start(exe_path, arguments)
    if started:
        logger.info("DCS server started successfully")
        last_start = datetime.now()
    else:
        logger.warning("Failed to start DCS server")

    return started


def kill():
    """
    Kill the DCS server.
    """
    exe_path = config.current["DCS_SERVER_EXE_PATH"]
    exe_name = processes.get_exe_name(exe_path)

    logger.info("Killing the DCS server...")
    processes.kill(exe_name)

    return True


def restart():
    """
    Restart the DCS server.
    """
    logger.info("Restarting DCS server...")
    kill()
    return start()


def ensure_up():
    """
    Check if the server is running correctly. If not, depending on the configs, do whatever
    necessary to get it up.
    """
    restart_if_not_running = config.current["DCS_SERVER_RESTART_IF_NOT_RUNNING"]
    restart_if_not_responsive = config.current["DCS_SERVER_RESTART_IF_NOT_RESPONSIVE"]

    status = current_status()
    logger.info("DCS server status: %s", status.name)

    if status == DCSServerStatus.NOT_RUNNING and restart_if_not_running:
        start()
    elif status == DCSServerStatus.NON_RESPONSIVE and restart_if_not_responsive:
        restart()
