"""
Script meant to run the app itself.
"""
import signal
import sys
from pathlib import Path
import multiprocessing

import click


dsm_process = None


@click.command()
@click.option("--config-path", type=click.Path(), default="./dsm.config",
              help="Path to the configuration file (./dsm.config if not specified)")
def main(config_path):
    """
    Cli interface, which launches the server manager in a separated process.
    This is needed because otherwise when closing the app in Windows there will be a leftover
    zombie process with the port taken, that prevents new server runs from using it (without even
    failing, they just don't bind the port).
    Gosh, I hate windows.
    """
    global dsm_process

    dsm_process = multiprocessing.Process(target=run_dcs_server_manager, args=(config_path,))
    dsm_process.start()
    dsm_process.join()


def run_dcs_server_manager(config_path):
    """
    Do everything needed to get the server manager up and running.
    """
    # these imports need to be here, in the target of the subprocess, otherwise weird things break
    # on the subprocess (like no logging, flask not being able to run, etc).
    import logging
    from dsm import config, web, jobs, logs

    logger = logging.getLogger(__name__)

    config_path = Path(config_path).absolute()

    config.load(config_path)
    logs.setup()
    config.password_check()

    logger.info("Using configuration at: %s", config_path)
    if not config_path.exists():
        logger.info("Configuration file not found, creating a new one")
        config.save(config_path)

    web.launch()


def handle_terminate(signal, frame):
    """
    Handle terminate and interrupt signals to shut down the server gracefully.
    """
    # this is what ensures that on windows the ports are really freed
    dsm_process.terminate()

    sys.exit(0)


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, handle_terminate)
    signal.signal(signal.SIGINT, handle_terminate)
    main()
