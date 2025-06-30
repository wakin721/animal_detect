@echo off
rem Get the directory where the script is located
set "SCRIPT_DIR=%~dp0"

rem Change the current directory to the script's directory
cd /d "%SCRIPT_DIR%"

echo Starting the application and checking the environment, please wait...

rem Run the main Python script
rem The script will handle setup and close this window automatically.
python main.py