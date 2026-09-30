@echo off
REM > SDKREQ-530 - Error handling and shutdown handling (Windows)
REM   Verifies the unified error format ([DXAPP] [ERROR]) and the exit handler,
REM   and verifies abnormal exit (ERRORLEVEL!=0) when given no arguments / an invalid option / a nonexistent model path.
REM   Also verifies the SDKREQ-529 input policy:
REM     - explicit -m wrong path -> immediate [ERROR] with NO auto-download (a wrong path is a user error)
REM     - -m omitted -> resolve the example default model via the registry and try auto-download
REM     - missing -i/-v input -> 'Input file not found' exit (no fallback to the default sample)
REM     - all input omitted -> use the default sample (normal)
REM     - .bin-requiring 3D example -> error on a non-.bin input
REM   (Linux counterpart: test_529.sh)
REM =========================================================================
REM   ---------------------------------------------------------------------
REM   ASCII ONLY, CRLF ONLY - and print via `call :say "..."`, never `echo`.
REM   A non-ASCII byte or an LF-only ending desyncs cmd.exe's byte-offset
REM   re-seek (the script dies mid-run); a bare echo lets angle brackets and
REM   pipes in the message act as redirection and the line vanishes.
REM   See _dxlog.bat / _dxenv.bat and README.md section 1.5.
REM Result: [PASS]/[FAIL]/[SKIP], exit code = number of FAILs
REM   [PASS] static verification or runtime verification (check ERRORLEVEL after actual run) passed
REM   [SKIP] NPU/device/network/VS2022 build required (manual guidance)
REM   Mixed static + runtime (run_tc style) verification.
REM =========================================================================
setlocal enabledelayedexpansion
set "SCRIPT_DIR=%~dp0"
pushd "%SCRIPT_DIR%..\.."
set "PROJECT_ROOT=%CD%"
REM Keep the full output of this run on disk (logs\%~n0.log) so it
REM survives the console window closing. See _dxlog.bat.
call "%SCRIPT_DIR%_dxlog.bat" "%~n0"
set /a P=0
set /a F=0
set /a S=0
set "PYTHON="
if defined PYTHON_PATH set "PYTHON=%PYTHON_PATH%"
if not defined PYTHON if exist "%PROJECT_ROOT%\venv\Scripts\python.exe" set "PYTHON=%PROJECT_ROOT%\venv\Scripts\python.exe"
if not defined PYTHON ( where python >nul 2>&1 && set "PYTHON=python" )
set "BUILD_DIR="
for %%d in (bin build_x86_64\release\bin build\bin) do if not defined BUILD_DIR if exist "%PROJECT_ROOT%\%%d" set "BUILD_DIR=%PROJECT_ROOT%\%%d"
REM --run / RUN_FULL=1: after static verification, verify error/shutdown handling with the actual binary too
if /I "%~1"=="--run" set "RUN_FULL=1"
if not defined RUN_FULL set "RUN_FULL=0"
call :say "PROJECT_ROOT=%PROJECT_ROOT% | BUILD_DIR=%BUILD_DIR% | RUN_FULL=%RUN_FULL% | PYTHON=%PYTHON%"
call :say ""
call :grd "error format [DXAPP] [ERROR]" "%PROJECT_ROOT%\src\cpp_example\common\runner" "[DXAPP] [ERROR]"
call :gr "SIGINT(Ctrl+C) handler" "%PROJECT_ROOT%\src\cpp_example\common\utility\run_dir.hpp" "signalHandler"
REM SDKREQ-529/530 policy helpers (common_util.hpp) static check
call :gr "model policy resolveAndValidateModel (-m omitted->default/auto-dl, given->immediate check)" "%PROJECT_ROOT%\src\cpp_example\common\utility\common_util.hpp" "resolveAndValidateModel"
call :gr "default model registry resolve resolveDefaultModelPath" "%PROJECT_ROOT%\src\cpp_example\common\utility\common_util.hpp" "resolveDefaultModelPath"
call :gr "input-exists check requireInputExists (wrong -i/-v -> immediate exit)" "%PROJECT_ROOT%\src\cpp_example\common\utility\common_util.hpp" "requireInputExists"
call :gr ".bin input check requireBinInput (3D LiDAR)" "%PROJECT_ROOT%\src\cpp_example\common\utility\common_util.hpp" "requireBinInput"
REM Runtime: whether invalid input actually causes abnormal exit (ERRORLEVEL not 0) -- argparse/validation level
REM NOTE(SDKREQ-529): -m is now optional (omitted -> auto-dl example default), so "no arguments" is
REM   no longer an error. Instead verify an explicit wrong -m path exits abnormally.
call :pybad "Python invalid option -> abnormal exit (exit!=0)" "src\python_example" "*_sync.py" "--nonexistent-xyz"
call :pybad "Python explicit wrong -m path -> abnormal exit (exit!=0)" "src\python_example" "*_sync.py" "-m __nonexistent__.dxnn --image sample/img/sample_street.jpg"
REM -- Actual run verification (--run / RUN_FULL=1): use the built .exe to confirm error format and Ctrl+C graceful shutdown --
if "%RUN_FULL%"=="1" goto :runfull
call :skipcmd "actual run error/shutdown handling (--run)" "set RUN_FULL=1 then rerun, or test_530.bat --run -> confirm [DXAPP][ERROR]+abnormal exit with the binary"
goto :afterrun
:runfull
call :say "[--run] Verify error/shutdown handling with the actual binary"
REM (1) Run with a nonexistent model/file -> unified error format [DXAPP] [ERROR] + abnormal exit (NPU not required)
call :rt "C++ nonexistent model -> [DXAPP][ERROR] format + abnormal exit" "build required: build.bat --all then bin\*_sync.exe" "cpp-badmodel"
REM (1a) SDKREQ-529 policy: explicit -m wrong path -> immediate [ERROR], NO auto-download
call :rt "C++ explicit -m wrong path -> immediate [ERROR] without auto-dl (policy)" "build required: bin\*_sync.exe -m <missing> -i <any> (downloader must NOT run)" "cpp-model-policy"
REM (1b) SDKREQ-529 policy: missing -i input -> 'Input file not found' exit (no default fallback)
call :rt "C++ missing -i input -> 'Input file not found' exit" "build+model required: bin\(det)_sync.exe -m <model> -i <missing>" "cpp-badinput"
REM (1c) SDKREQ-529 policy: non-.bin input to a 3D example -> .bin/LiDAR error exit
call :rt "C++ 3D non-.bin input -> .bin/LiDAR error exit" "build+3D model required: bin\sfa3d_*_sync.exe -m <model> -i <.jpg>" "cpp-bin-input"
REM (2) Ctrl+C during a stream -> graceful shutdown (Windows is unsuitable for automation -> auto SKIP, manual check)
call :rt "C++ Ctrl+C during stream -> graceful shutdown" "Windows is manual: while running bin\(det)_sync.exe -v (video), press Ctrl+C -> normal shutdown" "cpp-sigint"
:afterrun
call :say ""
call :say "Result: PASS=%P%  FAIL=%F%  SKIP=%S%"
if defined LOGFILE call :say "Full log: %LOGFILE%"
REM DXREQ_PAUSE=1 holds the window open when the script is started by
REM double-click. run_all.bat sets DXREQ_NOLOG so it never pauses.
if not defined DXREQ_NOLOG if defined DXREQ_PAUSE pause
popd
exit /b %F%

goto :eof
REM -- output helpers: print to the console AND append to LOGFILE ------------
REM :say is the ONLY way these scripts print. It must stay delayed-expansion
REM based: cmd parses a line for redirection BEFORE substituting !VAR!, so a
REM message containing angle brackets or a pipe is printed literally instead of
REM being eaten as a redirection. Plain "echo [PASS] %~1" unquotes the message
REM and silently swallowed every such line - e.g. the ".dxnn to examples" one.
:say
set "_M=%~1"
echo(!_M!
if defined LOGFILE >>"%LOGFILE%" echo(!_M!
goto :eof
REM :tee runs a command whose stdout must be shown to the user, capturing it so
REM the same text also lands in LOGFILE. Sets RC to the command's exit code.
:tee
%* > "%DXTMP%" 2>&1
set "RC=%ERRORLEVEL%"
type "%DXTMP%" 2>nul
if defined LOGFILE type "%DXTMP%" >> "%LOGFILE%" 2>nul
del "%DXTMP%" >nul 2>&1
goto :eof
:pass
call :say "[PASS] %~1"
set /a P+=1
goto :eof
:fail
call :say "[FAIL] %~1"
set /a F+=1
goto :eof
:skip
call :say "[SKIP] %~1"
set /a S+=1
goto :eof
:ex
if exist "%~2" ( call :pass "%~1 (%~2)" ) else ( call :fail "%~1 (missing: %~2)" )
goto :eof
:gr
findstr /C:"%~3" "%~2" >nul 2>&1 && ( call :pass "%~1" ) || ( call :fail "%~1 (not found: %~3)" )
goto :eof
:grd
findstr /S /C:"%~3" "%~2\*" >nul 2>&1 && ( call :pass "%~1" ) || ( call :fail "%~1 (not found: %~3)" )
goto :eof
:pyc
if not defined PYTHON ( call :skip "%~1 (python not found)" & goto :eof )
"%PYTHON%" -c "%~2" >nul 2>&1 && ( call :pass "%~1" ) || ( call :fail "%~1" )
goto :eof
:pytry
if not defined PYTHON ( call :skip "%~1 (python not found)" & goto :eof )
"%PYTHON%" -c "%~2" >nul 2>&1 && ( call :pass "%~1" ) || ( call :skip "%~1 (not built)" )
goto :eof
:skipcmd
call :skip "%~1"
call :say "   |_ manual: %~2"
goto :eof
REM -- Runtime verification helpers (run_tc style) --
:runpy
if not defined PYTHON ( call :skip "%~1 (python not found)" & goto :eof )
call :say "   $ %PYTHON% %~2"
"%PYTHON%" %~2 >nul 2>&1 && ( call :pass "%~1" ) || ( call :fail "%~1" )
goto :eof
:pyhelp
if not defined PYTHON ( call :skip "%~1 (python not found)" & goto :eof )
set "PEX="
for /r "%PROJECT_ROOT%\%~2" %%f in (%~3) do if not defined PEX set "PEX=%%f"
if not defined PEX ( call :skip "%~1 (no example: %~2)" & goto :eof )
call :say "   $ %PYTHON% !PEX! --help"
"%PYTHON%" "!PEX!" --help >nul 2>&1 && ( call :pass "%~1" ) || ( call :fail "%~1" )
goto :eof
:pybad
if not defined PYTHON ( call :skip "%~1 (python not found)" & goto :eof )
set "PEX="
for /r "%PROJECT_ROOT%\%~2" %%f in (%~3) do if not defined PEX set "PEX=%%f"
if not defined PEX ( call :skip "%~1 (no example: %~2)" & goto :eof )
"%PYTHON%" "!PEX!" %~4 >nul 2>&1 && ( call :fail "%~1" ) || ( call :pass "%~1" )
goto :eof
:rt
if not defined PYTHON ( call :skip "%~1 (python not found)" & goto :eof )
call :say "   $ _rt_resolve.py %~3"
"%PYTHON%" "%SCRIPT_DIR%_rt_resolve.py" %~3 >nul 2>&1
set "RC=%ERRORLEVEL%"
if "%RC%"=="0" ( call :pass "%~1" ) else if "%RC%"=="77" ( call :skipcmd "%~1" "%~2" ) else ( call :fail "%~1 (rc=%RC%)" )
goto :eof
