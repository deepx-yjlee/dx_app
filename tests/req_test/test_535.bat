@echo off
REM SDKREQ-535 - Repeated inference (loop) option (Windows)
REM   Verify the C++(-l/--loop)/Python(--loop) repeated inference option is exposed, and verify stable termination of actual repeated inference.
REM   [Run scenario] classification async 2 representatives to image input, --loop 10000 /
REM                  object_detection async 2 representatives to video input, --loop 20.
REM   (Linux equivalent: test_534.sh)
REM =========================================================================
REM   ---------------------------------------------------------------------
REM   ASCII ONLY, CRLF ONLY - and print via `call :say "..."`, never `echo`.
REM   A non-ASCII byte or an LF-only ending desyncs cmd.exe's byte-offset
REM   re-seek (the script dies mid-run); a bare echo lets angle brackets and
REM   pipes in the message act as redirection and the line vanishes.
REM   See _dxlog.bat / _dxenv.bat and README.md section 1.5.
REM Result: [PASS]/[FAIL]/[SKIP], exit code = FAIL count
REM   [PASS] static verification or runtime verification (check ERRORLEVEL after actual run) passed
REM   [SKIP] requires NPU/device/network/VS2022 build (manual guidance)
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
set "BUILD_DIR="
call "%SCRIPT_DIR%_dxenv.bat"
REM Runtime logs are kept on disk (never deleted) so a finished run can still be
REM inspected. One file per runtime case under tests\req_test\logs\.
set "LOGDIR=%SCRIPT_DIR%logs"
if not exist "%LOGDIR%" mkdir "%LOGDIR%" >nul 2>&1
set /a RTN=0
call :say "PROJECT_ROOT=%PROJECT_ROOT% | BUILD_DIR=%BUILD_DIR% | PYTHON=%PYTHON%"
call :say "LOGDIR=%LOGDIR%"
call :say ""
call :gr "Repeated inference option -l/--loop" "%PROJECT_ROOT%\src\cpp_example\common\runner\async_detection_runner.hpp" "l, loop"
call :gr "Python --loop" "%PROJECT_ROOT%\src\python_example\common\runner\args.py" "--loop"
REM Run: whether the Python example actually launches and exposes the --loop option
call :pyhelp "Python example --loop exposure/launch (--help exit 0)" "src\python_example\object_detection" "*_sync.py"
REM run_tc port: actually run repeated inference (--loop) and confirm stable termination
REM   On a low-spec board (ARM + cores 8 or fewer, or RT_LOW_SPEC=1) _rt_resolve.py caps --loop to fit a
REM   300s per-case budget. That deviates from the requirement, so the reason line is printed.
REM   classification async 2 representatives to image input, --loop 10000
call :rtloop "Classification async 2 x image --loop 10000 stability (auto-capped on low-spec board)" "build+model+NPU: bin\(cls)_async.exe -m (m).dxnn -i (img) -l 10000 --no-display (2 representatives)" "async-loop --task classification --input img --loop 10000 --count 2"
REM   object_detection async 2 representatives to video input, --loop 20
call :rtloop "Object Detection async 2 x video --loop 20 stability" "build+model+NPU: bin\(od)_async.exe -m (m).dxnn -v (vid) -l 20 --no-display (2 representatives)" "async-loop --task object_detection --input vid --loop 20 --count 2"
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
REM -- report helpers ------------------------------------------------------
REM Echo through a variable with delayed expansion: the label text is
REM substituted AFTER the line is parsed, so the &, pipe and redirection
REM characters inside a label stay literal instead of acting as operators
REM (%~1 strips the quotes, which would otherwise split the echo line).
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
REM -- Runtime verification helper (run_tc style) --
:runpy
if not defined PYTHON ( call :skip "%~1 (python not found)" & goto :eof )
call :say "   $ %PYTHON% %~2"
"%PYTHON%" %~2 >nul 2>&1 && ( call :pass "%~1" ) || ( call :fail "%~1" )
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
set "RTLOG=%LOGDIR%\test_535_rt_!RTN!.log"
"%PYTHON%" "%SCRIPT_DIR%_rt_resolve.py" %~3 >"!RTLOG!" 2>&1
set "RC=%ERRORLEVEL%"
call :say "   |_ log: !RTLOG!"
if "%RC%"=="0" ( call :pass "%~1" ) else if "%RC%"=="77" ( call :skipcmd "%~1" "%~2" ) else ( call :fail "%~1 (rc=%RC%)" )
goto :eof
REM rtloop: same as :rt but surfaces the low-spec auto-cap reason ([rt][loop-cut] line).
REM   When capped from the required --loop 10000 the result stays PASS, but the reason is logged.
:rtloop
if not defined PYTHON ( call :skip "%~1 (python not found)" & goto :eof )
call :say "   $ _rt_resolve.py %~3"
set /a RTN+=1
set "RTLOG=%LOGDIR%\test_535_rtloop_!RTN!.log"
"%PYTHON%" "%SCRIPT_DIR%_rt_resolve.py" %~3 >"!RTLOG!" 2>&1
set "RC=%ERRORLEVEL%"
findstr /C:"[rt][loop-cut]" "!RTLOG!"
call :say "   |_ log: !RTLOG!"
if "%RC%"=="0" ( call :pass "%~1" ) else if "%RC%"=="77" ( call :skipcmd "%~1" "%~2" ) else ( call :fail "%~1 (rc=%RC%)" )
goto :eof
