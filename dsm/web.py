import logging
import os

from flask import Flask, render_template, redirect, send_from_directory, cli, jsonify, request

from dsm import config, jobs


# web app singleton, we won't need more than one
app = Flask("dcs_server_manager")
logger = logging.getLogger(__name__)


def launch():
    """
    Configure the web app and launch it.
    """
    debug = os.environ.get("DEBUG", False)

    if not debug:
        # disable all kinds of console output that I don't want to show to the user
        app.logger.disabled = True
        logging.getLogger("werkzeug").disabled = True
        logging.getLogger("apscheduler").disabled = True
        logging.getLogger("apscheduler.scheduler").disabled = True
        logging.getLogger("apscheduler.executors.default").disabled = True
        cli.show_server_banner = lambda *args: None

    jobs.launch()

    logger.info("Running DCS Server Manager")
    logger.info("Web UI: http://localhost:%s", config.current["DSM_WEB_UI_PORT"])

    app.run(
        host=config.current["DSM_WEB_UI_HOST"],
        port=config.current["DSM_WEB_UI_PORT"],
        debug=debug,
    )


@app.route("/")
def home():
    """
    Home page.
    """
    return render_template("home.html")


@app.route("/reload_jobs")
def reload_jobs():
    jobs.schedule_jobs()
    return "OK"
