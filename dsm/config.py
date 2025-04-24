"""
This module handles the app configs.
It is meant to be used as a singleton, like this:

import config
config.load("some path")
# do stuff with config.current
config.save("some path")

This simplifies a lots of things, as we will never need to have multiple configs at the same time.
"""
from copy import deepcopy
from logging import getLogger
import json


logger = getLogger(__name__)


BASE_CONFIG = {
    # general settings
    "SAVE_LOGS": True,
    "LOG_FILE_PATH": None,
    "DSM_WEB_UI_PORT": 9999,
    "DSM_WEB_UI_HOST": "0.0.0.0",
    "DSM_WEB_UI_PASSWORD": None,

    # dcs server configs
    "DCS_SERVER_EXE_PATH": r"C:\Program Files\Eagle Dynamics\DCS World Server\bin\DCS_server.exe",
    "DCS_SERVER_EXE_ARGUMENTS": "-w DCS.server1",
    "DCS_SERVER_SAVED_GAMES_PATH": None,
    "DCS_SERVER_WEB_UI_PORT": 8088,
    "DCS_SERVER_CHECK_EVERY_SECONDS": 60,
    "DCS_SERVER_RESTART_IF_NOT_RUNNING": True,
    "DCS_SERVER_RESTART_IF_NOT_RESPONSIVE": True,
    "DCS_SERVER_RESTART_DAILY_AT_HOUR": None,

    # srs server configs
    "SRS_SERVER_EXE_PATH": r"C:\Program Files\DCS-SimpleRadio-Standalone\SR-Server.exe",
    "SRS_SERVER_EXE_ARGUMENTS": "",
    "SRS_SERVER_CHECK_EVERY_SECONDS": 60,
    "SRS_SERVER_RESTART_IF_NOT_RUNNING": True,
    "SRS_SERVER_RESTART_DAILY_AT_HOUR": None,
}


# singleton config object, with load and save functions assuming this is the only config we ever
# want to use
current = {}
current_path = None


def load(config_path:str):
    """
    Load the configuration from the config file.
    """
    global current_path

    # clear with base configs
    current.update(BASE_CONFIG)

    # then apply the user config
    try:
        with open(config_path, "r") as config_file:
            user_config = json.load(config_file)
        current.update(user_config)
    except FileNotFoundError:
        pass

    # and also set the path from which we loaded the user configs
    current_path = config_path


def save(config_path:str):
    """
    Save the configuration to the config file.
    """
    with open(config_path, "w") as config_file:
        json.dump(current, config_file, indent=2)


def password_check():
    """
    Check if the password is set in the configuration.
    """
    if not current["DSM_WEB_UI_PASSWORD"]:
        logger.warning("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        logger.warning("!! No password set for the web UI! !!")
        logger.warning("!! This is not recommended!        !!")
        logger.warning("!! You should configure a password !!")
        logger.warning("!! as soon as possible!            !!")
        logger.warning("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
