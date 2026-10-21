@echo off
rem Builds the radio firmware.  build [env ...] [-t upload --upload-port COM17] ...   (default env: all three boards)
rem ESP-IDF can't build from a network share (S:\ is \\SERVER\salient), so this mirrors radio\ to a local folder,
rem %USERPROFILE%\.salient-radio\src, and builds there. On a local checkout, plain  pio run  works too.
rem Run it from cmd or PowerShell, not Git Bash: ESP-IDF's tool installer refuses MSYS shells.
setlocal
set "HERE=%~dp0"
set "WORK=%USERPROFILE%\.salient-radio"
set "PLATFORMIO_WORKSPACE_DIR=%WORK%\pio"
set "PIO=%USERPROFILE%\.platformio\penv\Scripts\pio.exe"
if not exist "%PIO%" set "PIO=pio"

py -3 "%HERE%tools\get_bluepad32.py" || exit /b 1
robocopy "%HERE%." "%WORK%\src" /MIR /XD .pio .deps dist build managed_components /XF sdkconfig.esp32dev sdkconfig.nodemcu-32s sdkconfig.ttgo-t-display /NFL /NDL /NJH /NJS /NP >nul
if errorlevel 8 exit /b 1
py -3 "%HERE%tools\apply_defaults.py" "%WORK%\src" || exit /b 1

set "ENVS="
set "REST="
:envs
if "%~1"=="" goto run
set "A=%~1"
if "%A:~0,1%"=="-" goto rest
set "ENVS=%ENVS% -e %~1"
shift
goto envs
:rest
if "%~1"=="" goto run
set "REST=%REST% %1"
shift
goto rest
:run
pushd "%WORK%\src"
"%PIO%" run %ENVS% %REST%
set RC=%ERRORLEVEL%
popd
exit /b %RC%
