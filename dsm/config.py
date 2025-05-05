"""
This module handles the app configs.
It is meant to be used as a singleton, like this:

from dsm import config
config.load("some path")
# do stuff with config.current
config.save("some path")

This simplifies a lots of things, as we will never need to have multiple configs at the same time.
"""
from collections import namedtuple
from copy import deepcopy
from functools import wraps
from logging import getLogger
from pathlib import Path
import json
import sys

from dsm.exceptions import ImproperlyConfigured


logger = getLogger(__name__)


Config = namedtuple("Config", "default type help")


SPEC = {
    # general settings
    "DSM_SAVE_LOGS": Config(True, bool, "Wether to save logs to a file or not."),
    "DSM_LOG_FILE_PATH": Config("", Path, "Path where to save the log file."),
    "DSM_PORT": Config(9999, int, "Port for the Server Manager web UI."),
    "DSM_HOST": Config("0.0.0.0", str, "Host for the Server Manager web UI (use 0.0.0.0 if you want to be able to connect from other computers)."),
    "DSM_PASSWORD": Config("", str, "Password for the Server Manager web UI (user is 'admin'). If you forget it, you can always manually edit the config file."),

    # dcs server configs
    "DCS_EXE_PATH": Config(r"C:\Program Files\Eagle Dynamics\DCS World Server\bin\DCS_server.exe", Path, "Full path of the DCS server executable, usually called DCS_server.exe"),
    "DCS_EXE_ARGUMENTS": Config("-w DCS.server1", str, "Arguments to pass to the DCS server executable. This usually includes -w with the name of the Saved Games folder for this server, like -w DCS.server1"),
    "DCS_SAVED_GAMES_PATH": Config("", Path, r"Path to the DCS server Saved Games folder. This is usually something like C:\Users\<username>\Saved Games\DCS.server1"),
    "DCS_TACVIEW_REPLAYS_PATH": Config("", Path, r"Path to the folder where tacview replays are saved. This is usually something like C:\Users\<username>\Documents\Tacview"),
    "DCS_WEB_UI_PORT": Config(8088, int, "Port for the DCS server web UI, which is usually 8088. This is used to check wether the server is responsive or stuck in an error."),
    "DCS_CHECK_EVERY_SECONDS": Config(60, int, "How often to check if the DCS server is running or not. Leave empty if you want to disable these checks."),
    "DCS_RESTART_IF_NOT_RUNNING": Config(True, bool, "Whether to restart the DCS server if it is not running when the checks are done. This is useful if you want to make sure the server is always running."),
    "DCS_RESTART_IF_NOT_RESPONSIVE": Config(True, bool, "Whether to restart the DCS server if it is not responsive when the checks are done (for instance, when the mission scripts raise an error the server gets stuck). This is useful if you want to make sure the server is always running."),
    "DCS_RESTART_DAILY_AT_HOUR": Config(None, int, "Hour at which to restart the DCS server daily. This is useful if you want to 'reset' the server to a clean state every day, or deal with memory leaks, etc. If not set, the server will not be restarted daily."),
    "DCS_BOOT_TIMEOUT_SECONDS": Config(120, int, "How long to wait for the DCS server to boot before considering it as not responsive."),

    # srs server configs
    "SRS_EXE_PATH": Config(r"C:\Program Files\DCS-SimpleRadio-Standalone\SR-Server.exe", Path, "Full path of the SRS server executable, usually called SR-Server.exe"),
    "SRS_EXE_ARGUMENTS": Config("", str, "Arguments to pass to the SRS server executable. This is usually left empty."),
    "SRS_CHECK_EVERY_SECONDS": Config(60, int, "How often to check if the SRS server is running or not. Leave empty if you want to disable these checks."),
    "SRS_RESTART_IF_NOT_RUNNING": Config(True, bool, "Whether to restart the SRS server if it is not running when the checks are done. This is useful if you want to make sure the server is always running."),
    "SRS_RESTART_DAILY_AT_HOUR": Config(None, int, "Hour at which to restart the SRS server daily. This is useful if you want to 'reset' the server to a clean state every day, or deal with memory leaks, etc. If not set, the server will not be restarted daily."),
}


# singleton config object, with load and save functions assuming this is the only config we ever
# want to use
current = {}
current_path = None


def load(config_path):
    """
    Load the configuration from the config file.
    """
    global current
    global current_path

    # start with the default configs
    current = {config_name: config.default
               for config_name, config in SPEC.items()}

    # then apply the user config
    try:
        user_config = json.loads(config_path.read_text("utf-8"))
        current.update(user_config)
    except FileNotFoundError:
        pass

    # and also set the path from which we loaded the user configs
    current_path = config_path


def save(config_path):
    """
    Save the configuration to the config file.
    """
    config_path.write_text(json.dumps(current, indent=2), "utf-8")


def password_check():
    """
    Check if the password is set in the configuration.
    """
    if not current["DSM_PASSWORD"]:
        logger.warning("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        logger.warning("!! No password set for the web UI! !!")
        logger.warning("!! This is not recommended!        !!")
        logger.warning("!! You should configure a password !!")
        logger.warning("!! as soon as possible!            !!")
        logger.warning("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")


def require(config_names):
    """
    Decorator maker, to be able to check for configs.
    If the config doesn't exist, raise an ImproperlyConfigured error.
    """
    if isinstance(config_names, str):
        config_names = [config_names]

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for config_name in config_names:
                if config_name not in current:
                    raise ImproperlyConfigured(f"Config {config_name} is not set")
                else:
                    spec = SPEC[config_name]
                    value = current[config_name]

                    if spec.type in (str, Path):
                        if not value.strip():
                            raise ImproperlyConfigured(f"Config {config_name} is not set")
                    if spec.type is Path:
                        path = Path(value).absolute()
                        if not path.exists():
                            raise ImproperlyConfigured(f"Path {path} does not exist")

            return func(*args, **kwargs)

        return wrapper

    return decorator


def get_data_path():
    """
    When running within the exe generated with pyinstaller, data files are extracted from the exe
    into a temporary folder.
    In development mode instead, data is in the repo root.
    This functions finds out and returns whatever folder is the root of all data.
    """
    if getattr(sys, 'frozen', False):
        # running the exe generated with pyinstaller, data in temp path
        data_path = Path(sys._MEIPASS).absolute()
    else:
        # running in development mode, data in root of repo
        data_path = Path(".").absolute()

    return data_path
