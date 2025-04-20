from logging import getLogger
from enum import Enum

import requests
from requests.exceptions import RequestException, ConnectionError

from dsm import config
from dsm import processes


logger = getLogger(__name__)


DCSServerStatus = Enum("DCSServerStatus", "RUNNING NOT_RUNNING NON_RESPONSIVE")


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
            "Assuming DCS server down after failing to answer responsiveness check: %s", e
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
            return DCSServerStatus.RUNNING
        else:
            return DCSServerStatus.NON_RESPONSIVE
    else:
        return DCSServerStatus.NOT_RUNNING


def start():
    """
    Start the DCS server.
    """
    exe_path = config.current["DCS_SERVER_EXE_PATH"]
    arguments = config.current["DCS_SERVER_EXE_ARGUMENTS"]

    logger.info("Starting DCS server...")

    started = processes.start(exe_path, arguments)
    if started:
        logger.info("DCS server started successfully")
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


def restart():
    """
    Restart the DCS server.
    """
    logger.info("Restarting DCS server...")
    kill()
    start()


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
