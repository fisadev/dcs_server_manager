# Compiling exe

To compile the exe, first clone the repo in a Windows machine, and install UV.

Then, inside the repo in Git Bash, run this:

```bash
uv sync
uv run pyinstaller --name dsm --icon ./static/icon.ico --onefile run.py --add-data "templates:templates" --add-data "static:static" --clean
```

The new `dsm.exe` compiled executable will be in the `dist` folder.
