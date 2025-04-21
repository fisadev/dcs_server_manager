import logging
import os
from pathlib import Path

import click

from dsm import config, web


def setup_logging():
    """
    Set up logging for the application.
    """
    debug = os.environ.get("DEBUG", False)
    handlers = [logging.StreamHandler()]

    if config.current["SAVE_LOGS"]:
        log_path = config.current["LOG_FILE_PATH"]
        if not log_path:
            log_path = Path(config.current["CONFIG_PATH"]).parent / "dcs_server_manager.log"
        handlers.append(logging.FileHandler(log_path))

    logging.basicConfig(
        level=logging.DEBUG if debug else logging.INFO,
        handlers=handlers,
        format="%(asctime)s %(levelname)s %(message)s",
    )


def password_check():
    """
    Check if the password is set in the configuration.
    """
    if not config.current["DSM_WEB_UI_PASSWORD"]:
        logging.warning("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        logging.warning("!! No password set for the web UI! !!")
        logging.warning("!! This is not recommended!        !!")
        logging.warning("!! You should configure a password !!")
        logging.warning("!! as soon as possible!            !!")
        logging.warning("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")


@click.command()
@click.option("--config-path", type=click.Path(), default="./dcs_server_manager_config.json",
              help="Path to the configuration file (./dcs_server_manager_config.json if not specified)")
def run_dcs_server_manager(config_path):
    """
    Do everything needed to get the server manager up and running.
    """
    config_path = Path(config_path).absolute()

    config.load(config_path)
    setup_logging()
    password_check()

    logging.info("Using configuration at: %s", config_path)
    if not config_path.exists():
        logging.info("Configuration file not found, creating a new one")
        config.save(config_path)

    web.launch()


if __name__ == "__main__":
    run_dcs_server_manager()
