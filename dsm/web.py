import logging
import os

from flask import Flask, render_template, redirect, send_from_directory, cli, jsonify, request

from dsm import config, jobs, dcs, srs, logs


# web app singleton, we won't need more than one
app = Flask("dcs_server_manager")
logger = logging.getLogger(__name__)

SERVERS = {"dcs": dcs, "srs": srs}


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


@app.route("/jobs/reload")
def reload_jobs():
    jobs.schedule_jobs()
    return {"result": "ok"}


@app.route("/<server_name>/status")
@app.route("/<server_name>/status/<response_format>")
def server_status(server_name, response_format="json"):
    status = SERVERS[server_name].current_status().name
    if response_format == "json":
        return {"status": status}
    elif response_format == "html":
        return status.replace("_", " ").capitalize()


@app.route("/<server_name>/start")
def server_start(server_name):
    SERVERS[server_name].start()
    return {"result": "ok"}


@app.route("/<server_name>/restart")
def server_restart(server_name):
    SERVERS[server_name].restart()
    return {"result": "ok"}


@app.route("/<server_name>/kill")
def server_kill(server_name):
    SERVERS[server_name].kill()
    return {"result": "ok"}


@app.route("/<server_name>/config")
@app.route("/<server_name>/config/<response_format>")
def server_config(server_name, response_format="json"):
    prefix = f"{server_name.upper()}_SERVER_"
    relevant_config = {
        key: value
        for key, value in config.current.items()
        if key.startswith(prefix)
    }
    if response_format == "json":
        return {"config": relevant_config}
    else:
        return render_template(
            "server_config.html",
            prefix=prefix,
            config=relevant_config,
        )


@app.route("/config")
def dsm_config():
    return {"config": config.current}


@app.route("/logs")
def log_contents():
    log_path = logs.get_path()
    if log_path.exists():
        log_contents = log_path.read_text(encoding="utf-8")
    else:
        log_contents = ""

    return log_contents
