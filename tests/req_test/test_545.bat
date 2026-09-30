@echo off
REM =========================================================================
REM   ---------------------------------------------------------------------
REM   ASCII ONLY, CRLF ONLY - and print via `call :say "..."`, never `echo`.
REM   A non-ASCII byte or an LF-only ending desyncs cmd.exe's byte-offset
REM   re-seek (the script dies mid-run); a bare echo lets angle brackets and
REM   pipes in the message act as redirection and the line vanishes.
REM   See _dxlog.bat / _dxenv.bat and README.md section 1.5.
REM SDKREQ-545 - Unified demo launcher (run_demo) (Windows)
REM   Verify run_demo's --task/--mode/--input/--all options, launcher parsing
REM   and run_demo.py CLI startup (--help), and that `run_demo.py --all`
REM   really runs every demo (C++ and Python async, image, --no-display, save)
REM   and summarises PASS/FAIL/SKIP.
REM   (Linux equivalent: test_544.sh)
REM =========================================================================
REM Result: [PASS]/[FAIL]/[SKIP], exit code = FAIL count
REM   [PASS] static verification or runtime verification (ERRORLEVEL after a real run)
REM   [SKIP] requires NPU/device/network/VS2022 build (manual guidance)
REM   Mixed static + runtime (run_tc style) verification.
REM
REM   ASCII ONLY - see the header of _dxenv.bat. Non-ASCII text desyncs the
REM   cmd.exe batch parser and makes REM text run as commands.
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
set "BUILD_DIR="
call "%SCRIPT_DIR%_dxenv.bat"
REM Runtime logs are kept on disk (never deleted) so a finished run can still
REM be inspected. One file per runtime case under tests\req_test\logs\.
set "LOGDIR=%SCRIPT_DIR%logs"
if not exist "%LOGDIR%" mkdir "%LOGDIR%" >nul 2>&1
set /a RTN=0
call :say "PROJECT_ROOT=%PROJECT_ROOT% | BUILD_DIR=%BUILD_DIR% | PYTHON=%PYTHON%"
call :say "LOGDIR=%LOGDIR%"
call :say ""
call :ex "run_demo.bat" "%PROJECT_ROOT%\run_demo.bat"
call :ex "run_demo.py" "%PROJECT_ROOT%\scripts\run_demo.py"
call :gr "--task option" "%PROJECT_ROOT%\scripts\run_demo.py" "--task"
call :gr "--mode option" "%PROJECT_ROOT%\scripts\run_demo.py" "--mode"
call :gr "--input option" "%PROJECT_ROOT%\scripts\run_demo.py" "--input"
call :gr "run_demo.py --all option" "%PROJECT_ROOT%\scripts\run_demo.py" "\"--all\""
REM Run: whether the demo delegate script CLI actually starts (--help exit 0)
call :runpy "run_demo.py --help exit 0" "scripts\run_demo.py --help"
REM run_demo --all: really run every demo (C++ and Python async, image,
REM --no-display, save) and summarise.
REM   NOTE: keep '&' out of test labels. The report helpers echo the label
REM   after %~1 has stripped its quotes, so a bare '&' would split the echo
REM   line and the remainder would run as a command.
call :demoall "run_demo --all runs every demo (C++ and Python async, image, no-display, save)"
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
REM -- report helpers -------------------------------------------------------
REM Echo through a variable with delayed expansion: the label text is
REM substituted AFTER the line is parsed, so the &, pipe and redirection characters inside a label stay
REM literal instead of being treated as operators.
:pass
set "MSG=%~1"
call :say "[PASS] !MSG!"
set /a P+=1
goto :eof
:fail
set "MSG=%~1"
call :say "[FAIL] !MSG!"
set /a F+=1
goto :eof
:skip
set "MSG=%~1"
call :say "[SKIP] !MSG!"
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
set "MSG=%~2"
call :say "   |_ manual: !MSG!"
goto :eof
:demoall
REM Really run run_demo.py --all - 3-state (0 = some succeeded, 1 = failure,
REM 77 = nothing to run). Output streams to the console AND is kept in a log.
if not defined PYTHON ( call :skip "%~1 (python not found)" & goto :eof )
call :say "   $ %PYTHON% scripts\run_demo.py --all"
call :tee "%PYTHON%" scripts\run_demo.py --all
if "%RC%"=="0" ( call :pass "%~1" ) else if "%RC%"=="77" ( call :skipcmd "%~1" "build+model+NPU: python scripts\run_demo.py --all" ) else ( call :fail "%~1 (rc=%RC%)" )
goto :eof
REM -- runtime verification helpers (run_tc style) --------------------------
:runpy
if not defined PYTHON ( call :skip "%~1 (python not found)" & goto :eof )
call :say "   $ %PYTHON% %~2"
set /a RTN+=1
set "RTLOG=%LOGDIR%\test_545_runpy_!RTN!.log"
"%PYTHON%" %~2 >"!RTLOG!" 2>&1
set "RC=%ERRORLEVEL%"
call :say "   |_ log: !RTLOG!"
if "%RC%"=="0" ( call :pass "%~1" ) else ( call :fail "%~1" )
goto :eof
:pyhelp
if not defined PYTHON ( call :skip "%~1 (python not found)" & goto :eof )
set "PEX="
for /r "%PROJECT_ROOT%\%~2" %%f in (%~3) do if not defined PEX set "PEX=%%f"
if not defined PEX ( call :skip "%~1 (example not found: %~2)" & goto :eof )
call :say "   $ %PYTHON% !PEX! --help"
"%PYTHON%" "!PEX!" --help >nul 2>&1 && ( call :pass "%~1" ) || ( call :fail "%~1" )
goto :eof
:pybad
if not defined PYTHON ( call :skip "%~1 (python not found)" & goto :eof )
set "PEX="
for /r "%PROJECT_ROOT%\%~2" %%f in (%~3) do if not defined PEX set "PEX=%%f"
if not defined PEX ( call :skip "%~1 (example not found: %~2)" & goto :eof )
"%PYTHON%" "!PEX!" %~4 >nul 2>&1 && ( call :fail "%~1" ) || ( call :pass "%~1" )
goto :eof
:rt
if not defined PYTHON ( call :skip "%~1 (python not found)" & goto :eof )
call :say "   $ _rt_resolve.py %~3"
set /a RTN+=1
set "RTLOG=%LOGDIR%\test_545_rt_!RTN!.log"
"%PYTHON%" "%SCRIPT_DIR%_rt_resolve.py" %~3 >"!RTLOG!" 2>&1
set "RC=%ERRORLEVEL%"
call :say "   |_ log: !RTLOG!"
if "%RC%"=="0" ( call :pass "%~1" ) else if "%RC%"=="77" ( call :skipcmd "%~1" "%~2" ) else ( call :fail "%~1 (rc=%RC%)" )
goto :eof
