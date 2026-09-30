@echo off
REM > SDKREQ-526 - Python environment/version requirements (Windows)
REM   [Requirement] dx_app must build and run under the specified Python (minimum 3.8.10) environment.
REM   [Scenario] if the user activates a venv of the desired Python version and runs this script:
REM     (1) check that the active venv python meets the minimum requirement (3.8.10), and
REM     (2) build dx_app with that python (build.bat), and
REM     (3) if dx-engine is missing from the venv python -m pip list, show that list and warn, then
REM     (4) image inference for Python examples only (run_tc.sh --python --e2e-quick counterpart = in tests\python_example,
REM         pytest -m e2e_image). (a virtualenv test, so only Python image inference, not C++)
REM   run without activating a venv it only does static/lightweight verification and tells you to rerun.
REM   (Linux counterpart: test_525.sh)
REM =========================================================================
REM   ---------------------------------------------------------------------
REM   ASCII ONLY, CRLF ONLY - and print via `call :say "..."`, never `echo`.
REM   A non-ASCII byte or an LF-only ending desyncs cmd.exe's byte-offset
REM   re-seek (the script dies mid-run); a bare echo lets angle brackets and
REM   pipes in the message act as redirection and the line vanishes.
REM   See _dxlog.bat / _dxenv.bat and README.md section 1.5.
REM Result: [PASS]/[FAIL]/[SKIP]/[WARN], exit code = number of FAILs
REM   [PASS] static/runtime verification passed  [SKIP] environment required (manual)  [WARN] continues but affects confidence (not a FAIL)
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
REM if a venv is active (activate sets VIRTUAL_ENV), prefer that python
if defined VIRTUAL_ENV if exist "%VIRTUAL_ENV%\Scripts\python.exe" set "PYTHON=%VIRTUAL_ENV%\Scripts\python.exe"
if not defined PYTHON if defined PYTHON_PATH set "PYTHON=%PYTHON_PATH%"
if not defined PYTHON if exist "%PROJECT_ROOT%\venv\Scripts\python.exe" set "PYTHON=%PROJECT_ROOT%\venv\Scripts\python.exe"
if not defined PYTHON ( where python >nul 2>&1 && set "PYTHON=python" )
set "BUILD_DIR="
for %%d in (bin build_x86_64\release\bin build\bin) do if not defined BUILD_DIR if exist "%PROJECT_ROOT%\%%d" set "BUILD_DIR=%PROJECT_ROOT%\%%d"
REM the build command can be overridden with env(BUILD_CMD). e2e-short runs in the :e2e_short label.
if not defined BUILD_CMD set "BUILD_CMD=build.bat --all"
call :say "PROJECT_ROOT=%PROJECT_ROOT% | VIRTUAL_ENV=%VIRTUAL_ENV% | BUILD_DIR=%BUILD_DIR% | PYTHON=%PYTHON%"
call :say ""

REM -- (1) static + active interpreter: Python version requirement (minimum 3.8.10) --
call :say "[1] Python version/environment requirement verification"
call :ex "venv install script (setup.bat)" "%PROJECT_ROOT%\setup.bat"
call :gr "Python3xx auto-detection" "%PROJECT_ROOT%\setup.bat" "Python3"
call :pyshow "active python meets the minimum version (3.8.10)" "import sys;v=sys.version_info;print('python '+sys.version.split()[0]);assert v[:3]>=(3,8,10),'need>=3.8.10'"
call :say ""

REM -- (2) scenario: if a venv is active, build with that python, check dx-engine, Python image inference --
if defined VIRTUAL_ENV goto :scenario
call :say "[2] venv not active - lightweight verification only (activate a venv and rerun for the scenario)"
call :pyhelp "example startup in the current Python environment (--help exit 0)" "src\python_example" "*_sync.py"
call :rt "current Python environment example actual inference" "venv+build+NPU: python (task)\(model)\*_sync.py --model (m).dxnn --image (img)" "py-img"
call :skipcmd "active venv scenario (build + dx-engine check + Python image inference)" "activate the venv you want then rerun: (venv)\Scripts\activate.bat then test_526.bat"
goto :done

:scenario
call :say "[2] active venv scenario - build dx_app with this python, check dx-engine, Python example image inference"
call :say "   |_ active venv (%VIRTUAL_ENV%) detected: build/inference proceeds automatically (several minutes, NPU)"
REM (1) build dx_app with the active venv python
call :runstage "(1) dx_app build (active venv python)" "%BUILD_CMD%"
REM (2) dx-engine check (if missing, show pip list + warn)
call :check_dx_engine
REM (3) Python example image inference (run_tc.sh --python --e2e-quick counterpart)
call :e2e_quick

:done
call :say ""
call :say "Result: PASS=%P%  FAIL=%F%  SKIP/WARN=%S%"
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
:warn
call :say "[WARN] %~1"
set /a S+=1
goto :eof
:ex
if exist "%~2" ( call :pass "%~1 (%~2)" ) else ( call :fail "%~1 (missing: %~2)" )
goto :eof
:gr
findstr /C:"%~3" "%~2" >nul 2>&1 && ( call :pass "%~1" ) || ( call :fail "%~1 (not found: %~3)" )
goto :eof
:pyshow
if not defined PYTHON ( call :skip "%~1 (python not found)" & goto :eof )
call :tee "%PYTHON%" -c "%~2"
if errorlevel 1 ( call :fail "%~1" ) else ( call :pass "%~1" )
goto :eof
:skipcmd
call :skip "%~1"
call :say "   |_ manual: %~2"
goto :eof
:runstage
REM %1 title  %2 actual command - show the log then PASS/FAIL by ERRORLEVEL, propagate rc.
call :say "   $ %~2"
%~2
set "RSRC=%ERRORLEVEL%"
if "%RSRC%"=="0" ( call :pass "%~1" ) else ( call :fail "%~1 (run failed rc=%RSRC%)" )
exit /b %RSRC%
:e2e_quick
REM run_tc.sh --python --e2e-quick counterpart: run pytest -m e2e_image in tests\python_example.
REM   pytest exit 5 = no tests collected (models not installed) = treated as PASS (same as run_tc.sh).
if not defined PYTHON ( call :skip "(3) Python image inference (python not found)" & goto :eof )
call :say "   $ %PYTHON% -m pytest -m e2e_image --tb=short -v   (in tests\python_example)"
pushd "%PROJECT_ROOT%\tests\python_example"
call :tee "%PYTHON%" -m pytest -m e2e_image --tb=short -v
set "E2ERC=%ERRORLEVEL%"
popd
if "%E2ERC%"=="0" ( call :pass "(3) Python example image inference (--python --e2e-quick)" ) else if "%E2ERC%"=="5" ( call :skip "(3) Python image inference (no tests collected / models not installed)" ) else ( call :fail "(3) Python image inference (rc=%E2ERC%)" )
goto :eof
:check_dx_engine
REM confirm dx-engine in the active venv pip list. if missing, show pip list (dx related) + warn (not a FAIL).
REM   a literal parenthesis inside a ( ) else ( ) block ends the block early, so branch with goto.
if not defined PYTHON ( call :skip "(2) dx-engine check (python not found)" & goto :eof )
"%PYTHON%" -m pip list 2>nul | findstr /I /R "dx[-_]engine" >nul 2>&1
if not errorlevel 1 goto :dxe_found
call :warn "(2) dx-engine not installed - Python example image inference (--python --e2e-quick) may SKIP or fail"
call :say "   |_ dx-related pip packages in the current venv:"
"%PYTHON%" -m pip list 2>nul | findstr /I "dx" || call :say "      (no dx* package)"
call :say "   |_ install: pip install (dx_engine wheel)  or use a shared runtime venv that has dx_engine"
goto :eof
:dxe_found
call :pass "(2) dx-engine install check (active venv)"
goto :eof
:pyhelp
if not defined PYTHON ( call :skip "%~1 (python not found)" & goto :eof )
set "PEX="
for /r "%PROJECT_ROOT%\%~2" %%f in (%~3) do if not defined PEX set "PEX=%%f"
if not defined PEX ( call :skip "%~1 (no example: %~2)" & goto :eof )
call :say "   $ %PYTHON% !PEX! --help"
"%PYTHON%" "!PEX!" --help >nul 2>&1 && ( call :pass "%~1" ) || ( call :fail "%~1" )
goto :eof
:rt
if not defined PYTHON ( call :skip "%~1 (python not found)" & goto :eof )
call :say "   $ _rt_resolve.py %~3"
"%PYTHON%" "%SCRIPT_DIR%_rt_resolve.py" %~3 >nul 2>&1
set "RC=%ERRORLEVEL%"
if "%RC%"=="0" ( call :pass "%~1" ) else if "%RC%"=="77" ( call :skipcmd "%~1" "%~2" ) else ( call :fail "%~1 (rc=%RC%)" )
goto :eof
