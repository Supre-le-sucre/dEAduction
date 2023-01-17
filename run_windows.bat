@echo off
title dEAduction
echo =============================
echo Welcome ! We'll be running dEAduction on windows :D
echo WARNING! dEAduction is intended for Unix like directory manager
echo PLEASE consider installing dEAduction on C:/ drive otherwise IT WON'T WORK !
echo %cd%
echo =============================
set /p op=Do you want to check dEAduction for update and install them if found ? (y/N):
if "%op%"=="y" (goto update) else (goto start)


:update
cls
title dEAduction Update
echo ~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~
echo Running update check routine !
git fetch & git pull
echo ~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~
goto start

:start
cls
title Starting dEAduction
if NOT exist env\ (
	echo Python virtual environnement not existing, creating...
	python -m venv env
)

if exist env\Scripts\activate (
	echo Initialising python virtual environnement
	call env\Scripts\activate

)

if exist requirements.txt (
	echo Checking and installing missing dependecencies
	pip install -r "requirements.txt"
) else (
	echo WARNING No requirements.txt file found !
)

SET PYTHONPATH=%PYTHONPATH%;%cd%\src
SET DEADUCTION_DEV_MODE=1

echo Lauching dEAduction
cd src\deaduction
title dEAduction Console (Do not close)
python -m dui


