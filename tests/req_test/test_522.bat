@echo off
REM > SDKREQ-522 - Python/C++ example coverage (Windows)
REM   Verify that each Python example directory provides all 4 variants
REM   (sync/async/sync_cpp/async_cpp) as a source-level fact (independent of
REM   model files/naming), that Python model coverage >= C++, that a common
REM   argument parser exists, and that the examples actually start up/infer.
REM   (Linux counterpart: test_521.sh)
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
call :say "PROJECT_ROOT=%PROJECT_ROOT% | BUILD_DIR=%BUILD_DIR% | PYTHON=%PYTHON%"
call :say ""
REM Example completeness: verify that each example directory provides all 4
REM variants (sync/async/sync_cpp/async_cpp) (shared _check_example_variants.py).
REM The registry model_name->dxnn->dir 3-stage fuzzy match produces false
REM positives due to variant suffixes (_1/_v2) and undownloaded models, so
REM verify by source fact.
call :pyfile "Python example 4-variant completeness (sync/async/cpp_postprocess)" "%SCRIPT_DIR%_check_example_variants.py"
REM Coverage: linked to the model catalog (model_registry.json) -- every supported
REM .dxnn model has a Python/C++ example, no orphan examples, python>=cpp (not a
REM hardcoded count). Registry-only match, no model download required.
call :pyfile "Model registry coverage (supported .dxnn <-> examples, python>=cpp)" "%SCRIPT_DIR%_check_registry_coverage.py"
call :ex "Windows demo launcher" "%PROJECT_ROOT%\run_demo.bat"
REM Runtime: whether Python examples actually start up on Windows
call :pyhelp "Python example runtime startup (--help exit 0)" "src\python_example" "*_sync.py"
REM run_tc port: if dx_engine+model exist, run actual inference via a Python example
call :rt "Python example actual inference (--no-display)" "NPU+dx_engine: python (task)\(model)\*_sync.py --model (m).dxnn --image (img)" "py-img"
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
:pycov
REM Coverage verification -- show python stdout (diagnostic log) as-is and judge by exit code.
REM   exit 0 = PASS, 77 = SKIP (model not downloaded), otherwise = FAIL.
if not defined PYTHON ( call :skip "%~1 (python not found)" & goto :eof )
call :tee "%PYTHON%" -c "%~2"
if "%RC%"=="0" ( call :pass "%~1" ) else if "%RC%"=="77" ( call :skip "%~1 (model not downloaded)" ) else ( call :fail "%~1" )
goto :eof
:pyfile
REM python script file execution -- show stdout (diagnostic log) as-is and PASS/FAIL by exit code.
if not defined PYTHON ( call :skip "%~1 (python not found)" & goto :eof )
call :tee "%PYTHON%" "%~2"
if "%RC%"=="0" ( call :pass "%~1" ) else ( call :fail "%~1" )
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
