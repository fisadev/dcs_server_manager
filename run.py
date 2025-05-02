"""
Script meant to run the app itself.
"""
import logging
import signal
import sys
from pathlib import Path

import click

from dsm import config, web, logs


logger = logging.getLogger(__name__)


@click.command()
@click.option("--config-path", type=click.Path(), default="./dcs_server_manager_config.json",
              help="Path to the configuration file (./dcs_server_manager_config.json if not specified)")
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


def stop_dcs_server_manager(signal, frame):
    """
    Handle SIGTERM and SIGINT, stop everything gracefully.
    """
    logger.info("Received terminate signal, stopping the server manager")
    web.shutdown()
    sys.exit(0)


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, stop_dcs_server_manager)
    signal.signal(signal.SIGINT, stop_dcs_server_manager)
    run_dcs_server_manager()
