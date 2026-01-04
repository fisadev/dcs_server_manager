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
from collections import namedtuple
from datetime import datetime, timedelta
from logging import getLogger
from enum import Enum
from pathlib import Path

import requests

from dsm import config, processes, VERSION
from dsm.exceptions import ImproperlyConfigured


logger = getLogger(__name__)


DCSServerStatus = Enum("DCSServerStatus", "RUNNING NOT_RUNNING NON_RESPONSIVE PROBABLY_BOOTING")
MissionStatus = namedtuple("MissionStatus", "updated_at mission players paused")


last_start = datetime.now()
last_mission_status = None
pending_orders = []  # orders that are pending to be executed by the DCS server, like pausing, etc


MISSION_FILE_EXTENSION = "miz"
TRACK_FILE_EXTENSION = "trk"
TACVIEW_FILE_EXTENSION = "acmi"
HOOKS_FILE_NAME = "dsm_hooks.lua"
MISSION_STATUS_MAX_LIFE = timedelta(seconds=60)

# these lines should be commented in INSTALL_FOLDER\Scripts\MissionScripting.lua for Pretense to
# be able to persist state between missions
PRETENSE_PERSISTENCE_LINES = (
    "sanitizeModule('io')",
    "sanitizeModule('lfs')",
)


def is_responsive():
    """
    Check if the DCS server is responsive (if not it's probably because it's frozen with an error).
    We consider it responsive when it answers a specific request that we got from
    https://github.com/ActiumDev/dcs-server-wine/blob/main/bin/dcs-watchdog.py
    """
    url = f"http://localhost:{config.current['DCS_WEB_UI_PORT']}/encryptedRequest"
    body = {"ct": "/E5LnS99K/cq4BfuE9SwhgOVyvoFAD1FoJ+N0GhmhKg=", "iv": "rNuGPsuOIrY4NogYU01HIw=="}

    try:
        response = requests.post(url, json=body, timeout=30)
        if response.status_code == 200:
            return True
    except Exception as err:
        logger.debug(
            "Assuming DCS server not responsive after failing to answer responsiveness check: %s",
            type(err),
        )

    return False


@config.require("DCS_EXE_PATH")
def current_status():
    """
    Check if the DCS server is up and running.
    """
    exe_path = config.current["DCS_EXE_PATH"]
    exe_name = processes.get_exe_name(exe_path)

    process = processes.find(exe_name)

    if process:
        if is_responsive():
            return DCSServerStatus.RUNNING
        else:
            if (datetime.now() - last_start).total_seconds() < config.current["DCS_BOOT_TIMEOUT_SECONDS"]:
                return DCSServerStatus.PROBABLY_BOOTING
            else:
                return DCSServerStatus.NON_RESPONSIVE
    else:
        return DCSServerStatus.NOT_RUNNING


@config.require("DCS_EXE_PATH")
def current_resources():
    """
    Get the current resources used by the DCS server.
    """
    exe_path = config.current["DCS_EXE_PATH"]
    exe_name = processes.get_exe_name(exe_path)

    return processes.find(exe_name)


@config.require("DCS_EXE_PATH")
def start():
    """
    Start the DCS server.
    """
    global last_start

    exe_path = config.current["DCS_EXE_PATH"]
    arguments = config.current["DCS_EXE_ARGUMENTS"]

    logger.info("Starting DCS server...")
    processes.start(exe_path, arguments)
    last_start = datetime.now()
    logger.info("DCS server started")


@config.require("DCS_EXE_PATH")
def stop(kill=False):
    """
    Stop the DCS server.
    """
    exe_path = config.current["DCS_EXE_PATH"]
    exe_name = processes.get_exe_name(exe_path)

    logger.info("Stopping the DCS server... (kill=%s)", kill)
    processes.stop(exe_name, kill=kill)
    logger.info("DCS server stopped")


def restart(kill=False):
    """
    Restart the DCS server.
    """
    logger.info("Restarting DCS server...")
    stop(kill=kill)
    start()


def ensure_up():
    """
    Check if the server is running correctly. If not, depending on the configs, do whatever
    necessary to get it up.
    """
    restart_if_not_running = config.current["DCS_RESTART_IF_NOT_RUNNING"]
    restart_if_not_responsive = config.current["DCS_RESTART_IF_NOT_RESPONSIVE"]

    status = current_status()
    resources = current_resources()
    mission_status = current_mission_status()

    if resources:
        resources_bit = (
            f"ram:{resources.memory}MB "
            f"cpu:{resources.cpu}% "
            f"threads:{resources.threads} "
            f"subprocs:{resources.child_processes}"
        )
    else:
        resources_bit = ""

    if mission_status:
        mission_bit = (
            f"mission:{mission_status.mission} "
            f"players:{len(mission_status.players)}:{','.join(mission_status.players)}"
        )
    else:
        mission_bit = ""

    logger.info("DCS server status: %s %s %s", status.name, resources_bit, mission_bit)

    try:
        if status == DCSServerStatus.NOT_RUNNING and restart_if_not_running:
            start()
        elif status == DCSServerStatus.NON_RESPONSIVE and restart_if_not_responsive:
            restart(kill=True)
    except Exception as err:
        logger.warning("Failed to ensure the DCS Server is up: %s", err)


@config.require("DCS_SAVED_GAMES_PATH")
def get_config_path():
    """
    Get the path to the DCS Server config file.
    """
    saved_games_config = config.current["DCS_SAVED_GAMES_PATH"].strip()
    saved_games = Path(saved_games_config).absolute()
    return saved_games / "Config" / "serverSettings.lua"


@config.require("DCS_SAVED_GAMES_PATH")
def get_missions_path():
    """
    Get the path to the DCS Server missions folder.
    """
    saved_games_config = config.current["DCS_SAVED_GAMES_PATH"].strip()
    saved_games = Path(saved_games_config).absolute()
    return saved_games / "Missions"


@config.require("DCS_SAVED_GAMES_PATH")
def get_tracks_path():
    """
    Get the path to the DCS Server tracks/multiplayer folder.
    """
    saved_games_config = config.current["DCS_SAVED_GAMES_PATH"].strip()
    saved_games = Path(saved_games_config).absolute()
    return saved_games / "Tracks" / "Multiplayer"


@config.require("DCS_TACVIEW_REPLAYS_PATH")
def get_tacviews_path():
    """
    Get the path to the DCS Server tacview replays folder.
    """
    return Path(config.current["DCS_TACVIEW_REPLAYS_PATH"].strip()).absolute()


@config.require("DCS_SAVED_GAMES_PATH")
def get_hooks_path():
    """
    Get the path to the DCS Server scripts/hooks folder.
    """
    saved_games_config = config.current["DCS_SAVED_GAMES_PATH"].strip()
    saved_games = Path(saved_games_config).absolute()
    return saved_games / "Scripts" / "Hooks"


def install_hook():
    """
    Install the DCS server hook to get info about the running mission.
    """
    dcs_hooks_path = get_hooks_path()
    hook_path_source = config.get_data_path() / "templates" / HOOKS_FILE_NAME
    hook_path_destination = dcs_hooks_path / HOOKS_FILE_NAME

    dsm_port = config.current['DSM_PORT']
    dsm_password = config.current["DSM_PASSWORD"]
    if dsm_password:
        host = f"admin:{dsm_password}@localhost:{dsm_port}"
    else:
        host = f"localhost:{dsm_port}"

    hooks = hook_path_source.read_text()
    hooks = hooks.replace("%HOST%", host)
    hooks = hooks.replace("%VERSION%", VERSION)

    if not dcs_hooks_path.exists():
        dcs_hooks_path.mkdir(parents=True, exist_ok=True)
        logger.info("Created the DCS server hooks folder")

    hook_path_destination.write_text(hooks)
    logger.info("Latest version of the DCS hook installed")


def uninstall_hook():
    """
    Uninstall the DCS server hook.
    """
    dcs_hooks_path = get_hooks_path()
    hook_path = dcs_hooks_path / HOOKS_FILE_NAME

    if hook_path.exists():
        hook_path.unlink()

    logger.info("DCS hook no longer installed")


def hook_check():
    """
    Returns three values:
    - If the hook is installed or not
    - If the hook is up to date or not
    - If the hook is installed, what version it is
    """
    dcs_hooks_path = get_hooks_path()
    hook_path = dcs_hooks_path / HOOKS_FILE_NAME

    if hook_path.exists():
        version = "unknown"
        content = hook_path.read_text("utf-8")
        for line in content.splitlines():
            if line.startswith("-- HOOK FROM DSM"):
                version = line.split()[-1].strip()
        return True, version == VERSION, version
    else:
        return False, False, None


def current_mission_status():
    """
    Get the current mission status, if it's known and fresh enough (otherwise, return None).
    """
    if last_mission_status:
        if datetime.now() - last_mission_status.updated_at < MISSION_STATUS_MAX_LIFE:
            return last_mission_status


def set_mission_status(mission, players, paused):
    """
    Set the current mission status, recording also the time of the update.
    """
    global last_mission_status

    # for some reason, dcs lists the server as a player itself
    if players and players[0].strip() == "Server":
        players = players[1:]

    last_mission_status = MissionStatus(
        updated_at=datetime.now(),
        mission=mission,
        players=players,
        paused=paused,
    )


def consume_pending_orders():
    """
    Get the pending orders that are to be executed by the DCS server.
    This is used to pause, resume, etc. the mission.
    Returned orders are removed (consumed) from the queue, we assume the server got them.
    """
    orders = pending_orders.copy()
    pending_orders.clear()
    return orders


def add_pending_order(order):
    """
    Add an order to the pending orders queue.
    This is used to pause, resume, etc the mission.
    """
    if order not in pending_orders:
        pending_orders.append(order)


@config.require("DCS_EXE_PATH")
def get_mission_scripting_path():
    r"""
    Get the path to the DCS Server INSTALL_FOLDER\Scripts\MissionScripting.lua file.
    This file is edited to enable the Pretense missions to be persistent.
    """
    dcs_exe = Path(config.current["DCS_EXE_PATH"].strip()).absolute()
    dcs_install_folder = dcs_exe.parent.parent
    return dcs_install_folder / "Scripts" / "MissionScripting.lua"


def pretense_is_persistent():
    """
    Check if the DCS Server scripts are modified to enable persistence of the Pretense missions
    or not.
    """
    mission_scripting_path = get_mission_scripting_path()
    if not mission_scripting_path.exists():
        raise ImproperlyConfigured(f"{mission_scripting_path} not found")

    content = mission_scripting_path.read_text("utf-8")

    for original_line in PRETENSE_PERSISTENCE_LINES:
        commented_line = "--" + original_line
        if commented_line not in content:
            # found a line that should be commented for persistence, but isn't
            return False

    return True


def pretense_enable_persistence():
    """
    Modify the script file to enable the persistence of the Pretense missions.
    """
    mission_scripting_path = get_mission_scripting_path()
    if not mission_scripting_path.exists():
        raise ImproperlyConfigured(f"{mission_scripting_path} not found")

    content = mission_scripting_path.read_text("utf-8")

    for original_line in PRETENSE_PERSISTENCE_LINES:
        commented_line = "--" + original_line
        if commented_line not in content:
            content = content.replace(original_line, commented_line)

    mission_scripting_path.write_text(content, "utf-8")
    logger.info("Pretense persistence enabled")


def pretense_disable_persistence():
    """
    Modify the script file to disable the persistence of the Pretense missions.
    """
    mission_scripting_path = get_mission_scripting_path()
    if not mission_scripting_path.exists():
        raise ImproperlyConfigured(f"{mission_scripting_path} not found")

    content = mission_scripting_path.read_text("utf-8")

    for original_line in PRETENSE_PERSISTENCE_LINES:
        commented_line = "--" + original_line
        if commented_line in content:
            content = content.replace(commented_line, original_line)

    mission_scripting_path.write_text(content, "utf-8")
    logger.info("Pretense persistence disabled")
