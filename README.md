# DCS Server Manager

DSM (DCS Server Manager) is a super easy to use DCS and SRS server manager: simpler web UI, easily 
change missions, restart, monitor status, download tracks, etc.

It can even run in the background and automatically restart your DCS and SRS servers when they 
crash.

And the best part: it's just a single exe that you download and run. Easiest possible setup.

![readme_screenshot](https://github.com/user-attachments/assets/f6f45b4d-7f0e-4169-90e7-df1399376bcd)

The main features are:

- **Start/stop/restart/pause/unpause DCS and SRS** servers from the UI.
- **Check the current status** of the servers, plus CPU and RAM usage, mission and connected players.
- **Edit and apply DCS and SRS server configs** (change passwords, missions, etc).
- **Automatic health checks**: ensure the servers are always up, auto-restart them when they 
  crash.
- **Automatic daily reboots** of the DCS server, for missions that require it.
- **Manage misison, track and tacview files**: list them, download them, upload new 
  missions, delete old tracks, etc.
- **Historic logs** of your servers health and stats. See how the CPU, RAM, players, etc evolve 
  over time.

Plus a few other goodies.
Full docs [here](https://github.com/fisadev/dcs_server_manager/wiki).

# Installation

Just download the latest [released dsm.exe](https://github.com/fisadev/dcs_server_manager/releases)
and run it in your server. That's it!

If you prefer, you can also clone and run the source code instead.

# Usage

Once it's running, use your favorite browser to access the URL displayed in the console (
[http://localhost:9999](http://localhost:9999) by default), and configure the rest of DSM from the web UI itself.

The two config sections that you 100% should set up first are the DCS server and SRS server 
settings (including the DCS Hook), so DSM can let you administer them.

![initial_settings](https://github.com/user-attachments/assets/26e82c6c-460b-4382-a113-66ad427895c6)

Every setting has a helpful tooltip if you have any doubts.

More info about how to run it securely, configure it, and more in the 
[Docs](https://github.com/fisadev/dcs_server_manager/wiki).

# Community

You can join the [Discord server](https://discord.gg/QEJyAEURZj) to ask questions, report bugs,
suggest features, etc.

# Developers

If you want to help develop this tool, take a look at the 
[Docs](https://github.com/fisadev/dcs_server_manager/wiki).
They explain how to clone and run this repo, build the exe, how the app works internally, etc.

# License

This tool is completely free, and released under MIT license. You can do whatever you want with it, 
as long as you include the original license with it if you re-distribute it.
