@echo off
REM > SDKREQ-543 - Model registry and benchmarking (Windows)
REM   confirms 347 unique models registered in model_registry.json and that the bench script exists,
REM   verifies build.bat and the Python example startup/inference for registry models.
REM   with --run / RUN_FULL=1 it actually infers a representative model per task category in both C++/Python
REM   (bench_models.sh is Linux only, so Windows substitutes per-task inference).
REM   (Linux counterpart: test_542.sh)
REM =========================================================================
REM   ---------------------------------------------------------------------
REM   ASCII ONLY, CRLF ONLY - and print via `call :say "..."`, never `echo`.
REM   A non-ASCII byte or an LF-only ending desyncs cmd.exe's byte-offset
REM   re-seek (the script dies mid-run); a bare echo lets angle brackets and
REM   pipes in the message act as redirection and the line vanishes.
REM   See _dxlog.bat / _dxenv.bat and README.md section 1.5.
REM Result: [PASS]/[FAIL]/[SKIP], exit code = number of FAILs
REM   [PASS] static verification or runtime verification (actual run + ERRORLEVEL check) passed
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
REM --run / RUN_FULL=1: actually infer registry models per task category (C++/Python).
REM   (bench_models.sh is Linux only, so on Windows a per-task representative inference is used)
if /I "%~1"=="--run" set "RUN_FULL=1"
if not defined RUN_FULL set "RUN_FULL=0"
call :say "PROJECT_ROOT=%PROJECT_ROOT% | BUILD_DIR=%BUILD_DIR% | RUN_FULL=%RUN_FULL% | PYTHON=%PYTHON%"
call :say ""
call :ex "model_registry.json" "%PROJECT_ROOT%\config\model_registry.json"
REM Count UNIQUE dxnn files, not rows: model_registry.json may register the same
REM   .dxnn under two model_name aliases (e.g. deitbase384 / deit_base384_distilled
REM   both map to deit-b_384x384.dxnn), so len(d) is 348 while there are 347 models.
REM   347 is the single canonical figure - it matches scripts\modelzoo_manifest.json
REM   entries and EXPECTED_MODELS in test_528.bat (assets\models\*.dxnn downloads).
call :pyc "347 unique models registered" "import json;d=json.load(open('config/model_registry.json',encoding='utf-8'));n=len({e['dxnn_file'] for e in d});assert n==347,n"
call :ex "build.bat" "%PROJECT_ROOT%\build.bat"
REM run: whether the Python examples actually start on Windows
call :pyhelp "Python example runtime startup (--help exit 0)" "src\python_example" "*_sync.py"
REM run_tc port: check that actual Sync inference works with a registry model
call :rt "Registry model Sync inference" "VS2022+NPU: bin\(model)_sync.exe / _async.exe" "cpp-img"
REM --run: actually infer a representative model per task category in both C++/Python (full coverage, bench replacement)
if "%RUN_FULL%"=="1" (
    call :rt "Registry model per-task actual inference (C++)" "VS2022+NPU: bin\(model)_sync.exe per task" "cpp-img --per-task"
    call :rt "Registry model per-task actual inference (Python)" "NPU+dx_engine: python (task)\(model)\*_sync.py per task" "py-img --per-task"
) else (
    call :skipcmd "Registry model full per-task actual inference (--run)" "set RUN_FULL=1 and rerun, or test_543.bat --run - bench_models.sh is Linux only"
)
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
REM -- runtime verification helpers (run_tc style) --
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
