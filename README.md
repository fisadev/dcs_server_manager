# DSM: DCS Server Manager

A super easy to use DCS and SRS server manager: simpler web UI, easily change missions, restart, 
monitor status, download tracks, etc.

It can even run in the background and automatically restart your DCS and SRS servers when 
they crash.

![](docs/screenshot1.png)

The main features are:

- 🚦 **Start/stop/restart DCS and SRS** servers from the UI.
- 🔎 **Check the current status** of the servers, plus CPU and RAM usage, mission and connected players.
- 📃 **Edit and apply DCS and SRS server configs** (change passwords, missions, etc).
- 🚑 **Automatic health checks**: ensure the servers are always up, auto-restart them when they 
  crash.
- 🔁 **Automatic daily reboots** of the DCS server, for missions that require it.
- 📁 **Manage misison, track and tacview files**: list them, download them, upload new 
  missions, delete old tracks, etc.
- 📈 **Historic logs** of your servers health and stats. See how the CPU, RAM, players, etc evolve 
  over time.

Plus a few other goodies.

# Installation

Just download the latest [released dsm.exe](https://github.com/fisadev/dcs_server_manager/releases)
and run it in your server (running the source code instead is also possible if you are paranoid 
about running random exes).

Then connect to it via a web browser using the URL displayed in the console (default is 
[http://localhost:9999](http://localhost:9999)), and configure the rest of DSM from the web UI 
itself.

The two config sections you surely want to set up first are the DCS server and SRS server settings
(including the optional installation of the DCS hook, which can be done with just a button):

![](docs/initial_settings.gif)

Every setting has a helpful tooltip if you have any doubts, and there's also the full
[User Manual](https://github.com/fisadev/dcs_server_manager/blob/main/docs/user_manual.md).

# Usage

Once everything is configured you just need to make sure you run `dsm.exe` every time you boot 
your server machine, and so you will be able to access the web UI. The easiest way is to add a 
scheduled task in Windows.
Everything else is done from the web UI. 

You can access the UI from the same server machine or from other computers in your local network.
For instance, you might have two computers, one is the server and the other is your personal 
laptop, and you can access the web UI from your laptop like this: `http://YOUR_SERVER_INTERNAL_IP:9999`.
You will probably need to add a firewall rule in the server to allow incoming connections to port 
9999, though (or whatever port you configured).

But please read the security section below before doing stuff like routing ports to be able to 
access it from the outside world.

More info about the things you can do with DSM and how to connect to it in the 
[User Manual](https://github.com/fisadev/dcs_server_manager/blob/main/docs/user_manual.md).

# Security

DSM is not meant to be exposed to the outside world by itself.
It can be configured to require a password, but the connection is still not encrypted!
If you want to use it from outside your local network, please use a VPN (or if you know about 
web servers, you can configure a reverse proxy with SSL like Nginx).

More info on this in the [User Manual](https://github.com/fisadev/dcs_server_manager/blob/main/docs/user_manual.md).

If you don't trust the distributed exe, you can also clone and run the source code directly (which 
you can easily inspect yourself). You only need to install some dependencies and be confortable 
with running things from a terminal.

More info on this in the [Development Docs](https://github.com/fisadev/dcs_server_manager/blob/main/docs/development.md).

# Community

TODO create a discord

# Developers

If you want to help develop this tool, take a look at the 
[Development Docs](https://github.com/fisadev/dcs_server_manager/blob/main/docs/development.md).
They explain how to clone and run this repo, build the exe, how the app works internally, etc.

# License

This tool is completely free, and released under MIT license. You can do whatever you want with it, 
as long as you include the original license with it if you re-distribute it.
