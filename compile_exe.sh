#!/bin/bash
uv run pyinstaller --name dsm --icon ./static/icon.ico --onefile run.py --add-data "templates:templates" --add-data "static:static" --clean
