# DSM Development Docs

1. [Running the code](#running-the-code)
2. [Compiling the .exe](#compiling-the-exe)
3. [The inner workings of DSM](#the-inner-workings-of-dsm)
   - [The web app](#the-web-app)
   - [The backend of the web app](#the-backend-of-the-web-app)
   - [The background jobs](#the-background-jobs)
   - [The DCS and SRS libraries](#the-dcs-and-srs-libraries)
   - [Configs](#configs)
   - [Logs](#logs)
   - [The runner script and the exe](#the-runner-script-and-the-exe)
   - [Debug mode](#debug-mode)
4. [Security](#security)

## Running the code

This project is developed with Python 3.
All dependencies and execution in development mode are handled with UV, making things very simple.

The following steps assume you are familiar with running things from a terminal app:

1. Install Python 3: on Windows use the [official installers](https://www.python.org/downloads/windows), 
   on Linux use your package manager (if not already installed).
2. [Install UV](https://docs.astral.sh/uv/getting-started/installation/).
3. Install Git: on Windows use the [official installer](https://git-scm.com/download/win), on Linux 
  use your package manager (if not already installed).
4. Clone this repo and cd into it:
```bash
git clone https://github.com/fisadev/dcs_server_manager.git
cd dcs_server_manager
```
5. Install the dependencies:
```bash
uv sync
```
6. Run the server:
```bash
uv run python run.py
```

You can also run it in debug mode, which will automatically reload the server when you change any 
code and also print a lot more debug info:
```bash
uv run env DEBUG=1 python run.py
```

## Compiling the exe

To compile the exe you will need a Windows installation. After cloning the repo and installing the
dependencies, to compile the .exe run:

```bash
uv run pyinstaller --name dsm --icon ./static/icon.ico --onefile run.py --add-data "templates:templates" --add-data "static:static" --clean
```

The new `dsm.exe` compiled executable will be in the `dist` folder.

## The inner workings of DSM

In short, DSM is a simple web app with some background jobs, and some custom made libraries to 
interact with DCS and SRS. 

There's a **VERY** conscious effort to keep the code as clean as simple as possible.
No abstraction or design pattern is justified unless it really makes things simpler.

### The web app

This is a single page web app with a single HTML home page served by the backend (`templates/home.html`), 
and then everything else are AJAX requests fired from the frontend that update the DOM.

But probably to your surprise, it as almost no JavaScript at all.
No gigantic and overly complex JS framework like React or Vue either.
The last time I counted, it had the grand total of 15 lines of JavaScript.

Instead, it uses [HTMX](https://htmx.org/): a very simple and powerful library to build web apps 
in a declarative way, using HTML attributes to define the behavior of the app, and relying heavily 
on server-side rendering.

For instance, the icon that shows the current status of the DCS server is just this:

```html
<span hx-get="/dcs/status/short" hx-trigger="load, every 5s"/>
```

That's it! The frontend will automatically do an AJAX request to `/dcs/status/short` every 5 
seconds, the server return the icon, and HTMX will set it as the inner HTML of the span.
Look ma, no JavaScript!

Form submissions, file uploads, server actions, retrieving logs, etc, all done this way.

HTMX made the code so, so much easier to read and maintain, and the web app so much faster compared 
to using the "big frameworks", that there's no way DSM will switch to anything else.

### The backend of the web app

The backend is written in Python, using the very minimalist Flask framework.

There's a helper `dsm.web.launch()` function that starts the Flask server, and then the rest of the
code is just a bunch of endpoints that are called from the frontend.

The only complex bits are error handling and a couple of big endpoints that do different things 
depending on GET/POST/arguments received (for instance, file managing views or the config forms).

The rest are very short functions that just call some method from the DCS/SRS libraries and return
the result as HTML.

When in debug mode, we use the Flask server itself. 
Otherwise we run the server using [Waitress](https://docs.pylonsproject.org/projects/waitress/en/stable/).

### The background jobs

The background jobs are run using [APScheduler](https://apscheduler.readthedocs.io/en/stable/),
which allows you to schedule calls to functions at specific times or intervals.

The jobs are only used for two things:

- **Health checks**: with a configurable interval, the server checks if the DCS and SRS servers are 
  running, and if not (depending on the settings), it starts/restarts them.
- **Daily reboots**: if configured, the server will automatically restart the DCS server at a 
  specific time every day.

Both of them are using functions from the DCS/SRS libraries.

### The DCS and SRS libraries

These two libraries (`dsm.dcs` and `dsm.srs`) are the ones that do all the heavy lifting.
They encapsulate all the logic that interacts with DCS and SRS: detecting if the servers are 
running, launching or killing them, editing their configs, installing hooks, etc.

Some common logic was left in `dsm.processes`.

Both libraries are meant to be used as singletons, which simplifies lots of things:

```python
from dsm import dcs

dcs.current_status()
dcs.restart()
dcs.install_hook()
# etc...
```

There's no need to have a `DcsServer` class and to create instances, and to pass them around 
everywhere in the web app, etc.
This will never need to manage two DCS servers at the same time.
Just run two DSMs instead.


### Configs

Just like the DCS and SRS libraries, the config is also a singleton and very easy to use:

```python
from dsm import config

config.load("some path...")
config.save("some path...")
config.current["SOME_CONFIG_KEY"]
# etc...
```

Again, there's no need to pass around a `Config` instance everywhere or to have multiple configs.
A single config is enough for the whole app.

Configs are defined in a spec (`dsm.config.SPEC`) that specifies their name, type, default value,
and description for the user.

There's also a neat decorator to require configs in any function: `dsm.config.require` (meaning the 
function will rise a nice error telling the user they need to set the specified config).
Some examples on how to use it in the DCS and SRS libraries:

```python
@config.require("DCS_EXE_PATH")
def start():
    # ...
```

### Logs

In normal mode, logs in this app are used as a means to show info to the USER, not for a developer 
debugging the app.
The UI allows the user to see those logs, archive them, etc.

They're meant to show the user the historical status of the servers, and to let them know when DSM
did relevant things (like restarting a server, installing a hook, etc).

In debug mode, the logs are also used to show debug info to the developer.

So when adding a log line use this rule of thumb: should a normal user see this? No? Then use 
DEBUG level.

### The runner script and the exe

The runner script (`run.py`) is the entry point of the app.
To distribute the app, an executable is compiled using [PyInstaller](https://pyinstaller.org/en/stable/).

The exe basically runs the runner script, but it also includes all the app files (.py, templates,
static files, etc) inside the exe itself.
This means we need some little tricks to access those files from the code when running from the 
exe, detecting where those files get unpacked.
That's found in `dsm.config.get_data_path()`.

### Debug mode

To enable the debug mode, just run the app with the `DEBUG=1` environment variable set.
Like this:

```bash
uv run env DEBUG=1 python run.py
```

## Security

The web app is optionally protected by a password, but the connection is not encrypted.
The server DSM launches doesn't use SSL, just plain unencripted HTTP.

The server is meant to be accessed only from inside trusted networks, not as a public web app. 
Doing SSL well requires having a domain name, a valid SSL certificate, and a reverse proxy.
The domain name problem alone means that we cannot just distribute an exe with everything set up 
by default, because every user will have a different domain (or no domain at all!), and so they 
would need to create and configure their own certificates.

This exceeds the scope of this project, and it would make it much more complex to use.

Instead, we opt for the simple solution: telling users not to expose DSM to the outside world 
publicly.
If they need to access DSM from other places, they should use a VPN instead.
Or if they're skilled enough in server managing, they can use their own reverse proxy with SSL, 
like Nginx.

Optional feature to add in the future: a setting to enable SSL with self-signed certificates (less
secure than a proper cert, but way better than plain HTTP).
The main problem right now is that Waitress doesn't support SSL (the internal Flask server does, 
though!).
