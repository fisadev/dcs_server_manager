"""
This module handles the interaction with the SRS server.
It is meant to be used as a singleton, like this:

from dsm import srs
srs.start()
print(srs.current_status())
# and more...

This simplifies a lots of things, as we will never need to have multiple instances of this at the
same time.
"""
from logging import getLogger
from enum import Enum
from pathlib import Path

from dsm import config, processes


logger = getLogger(__name__)


SRSServerStatus = Enum("SRSServerStatus", "RUNNING NOT_RUNNING")


@config.require("SRS_SERVER_EXE_PATH")
def current_status():
    """
    Check if the SRS server is up and running.
    """
    exe_path = config.current["SRS_SERVER_EXE_PATH"]
    exe_name = processes.get_exe_name(exe_path)

    process = processes.find(exe_name)

    if process:
        return SRSServerStatus.RUNNING
    else:
        return SRSServerStatus.NOT_RUNNING


@config.require("SRS_SERVER_EXE_PATH")
def current_resources():
    """
    Get the current resources used by the SRS server.
    """
    exe_path = config.current["SRS_SERVER_EXE_PATH"]
    exe_name = processes.get_exe_name(exe_path)

    return processes.find(exe_name)


@config.require("SRS_SERVER_EXE_PATH")
def start():
    """
    Start the SRS server.
    """
    exe_path = config.current["SRS_SERVER_EXE_PATH"]
    arguments = config.current["SRS_SERVER_EXE_ARGUMENTS"]

    logger.info("Starting SRS server...")
    processes.start(exe_path, arguments)
    logger.info("SRS server started")


@config.require("SRS_SERVER_EXE_PATH")
def kill():
    """
    Kill the SRS server.
    """
    exe_path = config.current["SRS_SERVER_EXE_PATH"]
    exe_name = processes.get_exe_name(exe_path)

    logger.info("Killing the SRS server...")
    processes.kill(exe_name)
    logger.info("SRS server killed")


def restart():
    """
    Restart the SRS server.
    """
    logger.info("Restarting SRS server...")
    kill()
    start()


def ensure_up():
    """
    Check if the server is running correctly. If not, depending on the configs, do whatever
    necessary to get it up.
    """
    restart_if_not_running = config.current["SRS_SERVER_RESTART_IF_NOT_RUNNING"]

    status = current_status()
    resources = current_resources()

    if resources:
        resources_bit = (
            f"ram:{resources.memory}MB "
            f"cpu:{resources.cpu}% "
            f"threads:{resources.threads} "
            f"subprocs:{resources.child_processes}"
        )
    else:
        resources_bit = ""

    logger.info("SRS server status: %s %s", status.name, resources_bit)

    try:
        if status == SRSServerStatus.NOT_RUNNING and restart_if_not_running:
            start()
    except Exception as err:
        logger.warning("Failed to ensure the SRS Server is up: %s", err)


@config.require("SRS_SERVER_EXE_PATH")
def get_config_path():
    """
    Get the path to the SRS Server config file.
    """
    exe_path = Path(config.current["SRS_SERVER_EXE_PATH"].strip()).absolute()
    return exe_path.parent / "server.cfg"
