"""
Logging utilities.
"""
import logging
import os
import shutil
from datetime import datetime
from pathlib import Path

from dsm import config


def get_path():
    """
    Get the path to the log file.
    """
    log_path = config.current["DSM_LOG_FILE_PATH"]
    if not log_path:
        config_path = Path(config.current_path)
        log_path = config_path.parent / "dsm.log"

    return log_path


def setup():
    """
    Set up logging for the application.
    """
    debug = os.environ.get("DEBUG", False)
    handlers = [logging.StreamHandler()]

    if config.current["DSM_SAVE_LOGS"]:
        handlers.append(logging.FileHandler(get_path()))

    logging.basicConfig(
        level=logging.DEBUG if debug else logging.INFO,
        handlers=handlers,
        format="%(asctime)s %(levelname)s %(message)s",
    )


def read_contents():
    """
    Read the contents of the current log file.
    If no file is found, return None.
    """
    log_path = get_path()
    if log_path.exists():
        return log_path.read_text(encoding="utf-8")


def delete():
    """
    Clear the contents of the current log file.
    """
    log_path = get_path()
    if log_path.exists():
        log_path.write_text("")


def archive():
    """
    Archive the current log contents into a new file, and clean the current log file.
    If successful, returns the path to the archived log file.
    If the current log file does not exist, returns None.
    """
    log_path = get_path()
    if log_path.exists():
        while True:
            # create a new archive name, but make sure it doesn't exist
            archive_date = datetime.now().strftime("%Y%m%d_%H%M%S")
            archive_path = log_path.parent / log_path.name.replace(".log", f"_{archive_date}.log")

            if not archive_path.exists():
                break

        # can't just move the current file because that breaks the logging handles, so we must
        # copy to a new file and clean the current one instead
        shutil.copy(log_path, archive_path)
        log_path.write_text("")

        return archive_path


def current_size():
    """
    Get the size of the current log file in bytes.
    If the file does not exist, returns None.
    """
    log_path = get_path()
    if log_path.exists():
        return log_path.stat().st_size
