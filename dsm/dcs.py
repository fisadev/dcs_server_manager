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
from pathlib import Path

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
    except Exception as err:
        logger.debug(
            "Assuming DCS server down after failing to answer responsiveness check: %s", type(err)
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
    resources = current_resources()

    if resources:
        resources_bit = (
            f"{resources.memory} MB, "
            f"{resources.cpu}% CPU, "
            f"{resources.threads} threads, "
            f"{resources.child_processes} sub processes"
        )
    else:
        resources_bit = ""

    logger.info("DCS server status: %s %s", status.name, resources_bit)

    if status == DCSServerStatus.NOT_RUNNING and restart_if_not_running:
        start()
    elif status == DCSServerStatus.NON_RESPONSIVE and restart_if_not_responsive:
        restart()


def get_config_path():
    """
    Get the path to the DCS Server config file.
    """
    saved_games_config = config.current["DCS_SERVER_SAVED_GAMES_PATH"]
    if saved_games_config:
        saved_games = Path(saved_games_config).absolute()
        return saved_games / "Config" / "serverSettings.lua"


def get_missions_path():
    """
    Get the path to the DCS Server missions folder.
    """
    saved_games_config = config.current["DCS_SERVER_SAVED_GAMES_PATH"]
    if saved_games_config:
        saved_games = Path(saved_games_config).absolute()
        return saved_games / "Missions"


def get_tracks_path():
    """
    Get the path to the DCS Server tracks/multiplayer folder.
    """
    saved_games_config = config.current["DCS_SERVER_SAVED_GAMES_PATH"]
    if saved_games_config:
        saved_games = Path(saved_games_config).absolute()
        return saved_games / "Tracks" / "Multiplayer"


def get_tacviews_path():
    """
    Get the path to the DCS Server tacview replays folder.
    """
    return Path(config.current["DCS_SERVER_TACVIEW_REPLAYS_PATH"]).absolute()


def list_missions():
    """
    List current missions in the DCS server Missions folder (not considering subfolders).
    """
    missions_path = get_missions_path()
    if not missions_path.exists():
        return []
    else:
        return [file_path for file_path in missions_path.glob("*.miz") if file_path.is_file()]


def list_tracks():
    """
    List current DCS track replays in the Tracks/Multiplayer folder (not considering subfolders).
    """
    tracks_path = get_tracks_path()
    if not tracks_path.exists():
        return []
    else:
        return [file_path for file_path in tracks_path.glob("*.trk") if file_path.is_file()]


def list_tacviews():
    """
    List current tacview replays in the tacview folder (not considering subfolders).
    """
    tacview_path = get_tacviews_path()
    if not tacview_path.exists():
        return []
    else:
        return [file_path for file_path in tacview_path.glob("*.*") if file_path.is_file()]
