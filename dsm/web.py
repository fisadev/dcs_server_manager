"""
This is the web app, allowing the user to check the status of the servers and to interact with
them, and the configs.
"""
import logging
import os
from pathlib import Path

from flask import Flask, render_template, cli, request
from flask_basicauth import BasicAuth
from werkzeug.utils import secure_filename

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
    dcs.DCSServerStatus.PROBABLY_BOOTING: "🟡",
    srs.SRSServerStatus.RUNNING: "🟢",
    srs.SRSServerStatus.NOT_RUNNING: "🔴",
}


@app.route("/<server_name>/status")
def server_status(server_name):
    status = SERVERS[server_name].current_status()
    icon = STATUS_ICONS[status]
    text = status.name.replace("_", " ").lower()
    return f"{icon} {text}"


@app.route("/<server_name>/status/icon")
def server_status_icon(server_name):
    status = SERVERS[server_name].current_status()
    return STATUS_ICONS[status]


@app.route("/<server_name>/resources")
def server_resources(server_name):
    resources = SERVERS[server_name].current_resources()
    return render_template("server_resources.html", resources=resources)


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
    broken_fields = set()
    warnings = []

    if request.method == "POST":
        new_configs = {}
        for config_name in relevant_config_names:
            try:
                if config_name.replace(prefix, "") in ("RESTART_IF_NOT_RUNNING", "RESTART_IF_NOT_RESPONSIVE"):
                    value = config_name in request.form
                else:
                    value = request.form.get(config_name, "").strip()
                    if config_name.endswith(("PORT", "SECONDS", "HOUR")):
                        if value:
                            value = int(value)
                        else:
                            value = None

                new_configs[config_name] = value

                if config_name.endswith("PATH") and value:
                    try:
                        value_path = Path(value).absolute()
                        if not value_path.exists():
                            warnings.append(f"Warning: path {value_path} does not exist")
                    except Exception as err:
                        # not important to show errors in this check to the user
                        logger.debug("Failed to run path check for %s: %s", config_name, err)
            except ValueError:
                broken_fields.add(config_name)

        if not broken_fields:
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
        broken_fields=broken_fields,
        warnings=warnings,
    )


@app.route("/<server_name>/config_form", methods=["GET", "POST"])
def server_config_form(server_name):
    config_path = SERVERS[server_name].get_config_path()
    config_contents = ""
    errors = []
    warnings = []

    if request.method == "POST":
        config_contents = request.form.get("config_contents", "").strip()
        try:
            if server_name == "dcs" and not config_path:
                errors.append("Config not saved: you must configure the location of the DCS "
                              "Server Saved Games folder in order to edit the config file.")
            elif not config_path.exists():
                errors.append(f"Config not saved: no config file found at {config_path}")
            else:
                if config_contents:
                    config_path.write_text(config_contents)
                    warnings.append("Just in case: saving the config does not restart the server, "
                                    "remember to do that if you want the changes applied")
                else:
                    errors.append("Config not saved: empty config contents")
        except Exception as err:
            logger.exception("Error trying to save the config!")
            errors.append(f"Error trying to save the config! {err}")
    else:
        if server_name == "dcs" and not config_path:
            errors.append("Can't read config: you must configure the location of the DCS Server "
                          "Saved Games folder in order to edit the config file.")
        elif not config_path.exists():
            errors.append(f"Can't read config: no config file found at {config_path}")
        else:
            config_contents = config_path.read_text()

    return render_template(
        "server_config_form.html",
        server_name=server_name,
        config_contents=config_contents,
        errors=errors,
        warnings=warnings,
    )


@app.route("/dcs/missions", methods=["GET", "POST"])
def dcs_missions():
    errors = []

    if request.method == "POST":
        missions_path = dcs.get_missions_path()

        file = request.files["mission_file"]
        # If the user does not select a file, the browser submits an empty file without a filename.
        if file.filename == "":
            errors.append("No mission file selected")
        elif not missions_path.exists():
            errors.append("The missions folder does not exist, mission not uploaded")
        else:
            filename = secure_filename(file.filename)
            file.save(missions_path / filename)

    missions = dcs.list_missions()
    return render_template("files_list.html", files=missions, errors=errors)


@app.route("/dcs/tracks")
def dcs_tracks():
    tracks = dcs.list_tracks()
    return render_template("files_list.html", files=tracks)


@app.route("/dcs/tacviews")
def dcs_tacviews():
    tacviews = dcs.list_tacviews()
    return render_template("files_list.html", files=tacviews)


@app.route("/logs")
def log_contents():
    log_path = logs.get_path()
    if log_path.exists():
        log_contents = log_path.read_text(encoding="utf-8")
    else:
        log_contents = "No log file found"

    return log_contents


@app.route("/logs/delete")
def log_delete():
    log_path = logs.get_path()
    if log_path.exists():
        log_path.write_text("")

    return "Logs emptied"
