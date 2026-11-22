@echo off
rem Opens the Harmony of Despair Music Pack Builder window.
rem Needs Python 3 with numpy, soundfile and soxr:  python -m pip install numpy soundfile soxr
start "" pythonw "%~dp0hod_musicpack_gui.py"
