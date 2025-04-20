import logging
from pathlib import Path

import click

from dsm import web
from dsm import config


def setup_logging():
    """
    Set up logging for the application.
    """
    handlers = [logging.StreamHandler()]

    if config.current["SAVE_LOGS"]:
        log_path = Path(config.current["CONFIG_PATH"]).parent / "dcs_server_manager.log"
        handlers.append(logging.FileHandler(log_path))

    logging.basicConfig(
        level=logging.INFO,
        handlers=handlers,
        format="%(asctime)s %(levelname)s %(message)s",
    )


def password_check():
    """
    Check if the password is set in the configuration.
    """
    if not config.current["DSM_WEB_UI_PASSWORD"]:
        logging.warning("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        logging.warning("!! No password set for the web UI. This is not recommended! !!")
        logging.warning("!! You should configure a password as soon as possible!     !!")
        logging.warning("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")


@click.command()
@click.option("--config-path", type=click.Path(), default="./dcs_server_manager_config.json",
              help="Path to the configuration file (./config.json if not specified)")
def run_dcs_server_manager(config_path):
    """
    Do everything needed to get the server manager up and running.
    """
    config.load(config_path)
    setup_logging()
    password_check()

    logging.info("Using configuration at: %s", config_path)
    if not Path(config_path).exists():
        logging.info("Configuration file not found, creating a new one")
        config.save(config_path)

    web.launch()


if __name__ == "__main__":
    run_dcs_server_manager()
