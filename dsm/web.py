import logging
import os

from flask import Flask, render_template, cli, request
from flask_basicauth import BasicAuth

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

    if config.current["DSM_WEB_UI_PASSWORD"]:
        app.config["BASIC_AUTH_USERNAME"] = "admin"
        app.config["BASIC_AUTH_PASSWORD"] = config.current["DSM_WEB_UI_PASSWORD"]
        app.config["BASIC_AUTH_FORCE"] = True
        BasicAuth(app)

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


STATUS_ICONS = {
    dcs.DCSServerStatus.RUNNING: "🟢",
    dcs.DCSServerStatus.NON_RESPONSIVE: "🔴",
    dcs.DCSServerStatus.NOT_RUNNING: "🔴",
    srs.SRSServerStatus.RUNNING: "🟢",
    srs.SRSServerStatus.NOT_RUNNING: "🔴",
}


@app.route("/<server_name>/status")
def server_status(server_name):
    status = SERVERS[server_name].current_status()
    icon = STATUS_ICONS[status]
    text = status.name.replace("_", " ").capitalize()
    return f"{icon} {text}"


@app.route("/<server_name>/status/icon")
def server_status_icon(server_name):
    status = SERVERS[server_name].current_status()
    return STATUS_ICONS[status]


@app.route("/<server_name>/start")
def server_start(server_name):
    started = SERVERS[server_name].start()
    if started:
        return "Server started"
    else:
        return "Failed to start server"


@app.route("/<server_name>/restart")
def server_restart(server_name):
    restarted = SERVERS[server_name].restart()
    if restarted:
        return "Server restarted"
    else:
        return "Failed to restart server"


@app.route("/<server_name>/kill")
def server_kill(server_name):
    killed = SERVERS[server_name].kill()
    if killed:
        return "Server killed"
    else:
        return "Failed to kill server"


@app.route("/<server_name>/manager_config_form", methods=["GET", "POST"])
def server_manager_config_form(server_name):
    prefix = f"{server_name.upper()}_SERVER_"
    relevant_config_names = [
        config_name for config_name in config.current
        if config_name.startswith(prefix)
    ]
    errors = set()

    if request.method == "POST":
        new_configs = {}
        for config_name in relevant_config_names:
            try:
                if config_name.replace(prefix, "") in ("RESTART_IF_NOT_RUNNING", "RESTART_IF_NOT_RESPONSIVE"):
                    value = config_name in request.form
                else:
                    value = request.form[config_name].strip()
                    if config_name.endswith(("PORT", "SECONDS", "HOUR")):
                        if value:
                            value = int(value)
                        else:
                            value = None

                new_configs[config_name] = value
            except ValueError:
                errors.add(config_name)

        if not errors:
            config.current.update(new_configs)
            config.save(config.current_path)
            # reload jobs if configs have changed
            jobs.schedule_jobs()

    relevant_configs = {
        config_name: config.current[config_name]
        for config_name in relevant_config_names
    }

    return render_template(
        "server_manager_config_form.html",
        server_name=server_name,
        prefix=prefix,
        configs=relevant_configs,
        errors=errors,
    )


@app.route("/config")
def dsm_config():
    return config.current


@app.route("/logs")
def log_contents():
    log_path = logs.get_path()
    if log_path.exists():
        log_contents = log_path.read_text(encoding="utf-8")
    else:
        log_contents = ""

    return log_contents


@app.route("/logs/delete")
def log_delete():
    log_path = logs.get_path()
    if log_path.exists():
        log_path.write_text("")

    return "Logs emptied"
