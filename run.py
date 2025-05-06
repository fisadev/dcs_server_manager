"""
Script meant to run the app itself.
"""
from pathlib import Path
from time import sleep
import logging

import click
import psutil

from dsm import config, web, logs


logger = logging.getLogger(__name__)


@click.command()
@click.option("--config-path", type=click.Path(), default="./dsm.config",
              help="Path to the configuration file (./dsm.config if not specified)")
def run_dcs_server_manager(config_path):
    """
    Do everything needed to get the server manager up and running.
    """
    config_path = Path(config_path).absolute()

    config.load(config_path)
    logs.setup()
    config.password_check()

    logger.info("Using configuration at: %s", config_path)
    if not config_path.exists():
        logger.info("Configuration file not found, creating a new one")
        config.save(config_path)

    web.launch()


if __name__ == "__main__":
    run_dcs_server_manager()
