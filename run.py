"""
Script meant to run the app itself.
"""
from multiprocessing import Process, Pipe
from pathlib import Path
from time import sleep

import click


@click.command()
@click.option("--config-path", type=click.Path(), default="./dsm.config",
              help="Path to the configuration file (./dsm.config if not specified)")
def cli(config_path):
    """
    Command line interface for the DCS Server Manager.
    This launches the manager in a new process, so we can restart it when needed.
    """
    while keep_running := True:
        # the pipe is used so the child DSM process can signal the parent process that it wants to
        # be restarted or killed
        parent_conn, dsm_conn = Pipe()
        dsm_process = Process(target=run_dcs_server_manager, args=(config_path, dsm_conn))
        dsm_process.start()
        message = ""

        while dsm_process.is_alive():
            # is there data in the pipeline? what did the child process say?
            if parent_conn.poll():
                message = parent_conn.recv()
                if message == "restart":
                    # wait a couple of seconds so the user gets any responses and messages pending
                    sleep(2)
                    dsm_process.terminate()

        dsm_process.join()
        keep_running = message == "restart"


def run_dcs_server_manager(config_path, pipe_to_parent_process):
    """
    Do everything needed to get the server manager up and running.
    """
    # these imports need to be here to avoid weird issues with the subprocess trying to use ports,
    # files, etc taken by the parent process
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

    web.launch(pipe_to_parent_process)


if __name__ == "__main__":
    cli()
