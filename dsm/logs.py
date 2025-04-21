import logging
import os
from pathlib import Path

from dsm import config


def get_path():
    """
    Get the path to the log file.
    """
    log_path = config.current["LOG_FILE_PATH"]
    if not log_path:
        config_path = Path(config.current_path)
        log_path = config_path.parent / "dcs_server_manager.log"

    return log_path


def setup():
    """
    Set up logging for the application.
    """
    debug = os.environ.get("DEBUG", False)
    handlers = [logging.StreamHandler()]

    if config.current["SAVE_LOGS"]:
        handlers.append(logging.FileHandler(get_path()))

    logging.basicConfig(
        level=logging.DEBUG if debug else logging.INFO,
        handlers=handlers,
        format="%(asctime)s %(levelname)s %(message)s",
    )
