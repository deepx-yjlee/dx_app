@echo off
REM > SDKREQ-533 - C++ postprocess (cpp_postprocess) pybind11 binding (Windows)
REM   the src/postprocess module and the dx_postprocess pybind11 module source;
REM   verifies that Python uses "from dx_postprocess import", and covers whether each postprocess
REM   category is registered in the pybind11 binding, plus importability and example execution.
REM   (Linux counterpart: test_531.sh - 532 is unused)
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
call :ex "postprocess module directory" "%PROJECT_ROOT%\src\postprocess"
call :ex "pybind dx_postprocess source" "%PROJECT_ROOT%\src\bindings\python\dx_postprocess"
call :gr "pybind11 module dx_postprocess" "%PROJECT_ROOT%\src\bindings\python\dx_postprocess\CMakeLists.txt" "pybind11_add_module(dx_postprocess"
call :gr "dx_postprocess import from Python" "%PROJECT_ROOT%\src\python_example\classification\alexnet\alexnet_sync_cpp_postprocess.py" "from dx_postprocess import"
REM category coverage: whether each postprocess category (family) has a source and is registered in the pybind11 binding
call :catcov "postprocess per-category source exists + registered in the pybind11 binding"
call :pytry "dx_postprocess importable (.pyd)" "import dx_postprocess"
REM run_tc port: if the postprocess library + NPU are present, actually run a cpp_postprocess Python example
call :rt "C++ postprocess Python example run" "build+NPU: python (task)\(model)\*_sync_cpp_postprocess.py --model (m).dxnn --image (img)" "py-cpp-img"
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
:catcov
REM postprocess category coverage (_rt_resolve.py postproc-coverage) - show output + judge by ERRORLEVEL.
if not defined PYTHON ( call :skip "%~1 (python not found)" & goto :eof )
call :tee "%PYTHON%" "%SCRIPT_DIR%_rt_resolve.py" postproc-coverage
if "%RC%"=="0" ( call :pass "%~1" ) else if "%RC%"=="77" ( call :skip "%~1 (src\postprocess not found)" ) else ( call :fail "%~1" )
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
