@echo off
REM > SDKREQ-524 - x86-64 / aarch64 native build and run (Windows)
REM   [Requirement] dx_app must work in the "native" environment of each architecture (not cross-compiled):
REM     the install then build then setup then run_tc(pytest) pipeline must run as-is.
REM     - Windows (x86-64) native pipeline:
REM         (1) dependency: VS2022 + vcpkg (vcpkg.json manifest)  [Linux install.sh counterpart]
REM         (2) build.bat --all  (x64 native build, produces bin\*_sync.exe)
REM         (3) setup.bat        (model .dxnn + test media)
REM         (4) pytest -m e2e_image  (example run/inference)      [Linux run_tc.sh counterpart]
REM     - the aarch64 native pipeline runs on aarch64 (Linux) hardware - test_523.sh verifies it.
REM   [Verify] (1) Windows native pipeline components exist + the x86_64,aarch64 cmake toolchains
REM              statically confirm that "both" exist (= both archs are build targets)
REM          (2) if build artifacts exist on the current x64 host, verify actual inference via the pytest path
REM   Cannot test: an aarch64 native build needs aarch64 hardware (manual guidance, see test_523.sh).
REM   (Linux counterpart: test_523.sh)
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
call :say "PROJECT_ROOT=%PROJECT_ROOT% | HOST_ARCH=x86_64(Windows) | BUILD_DIR=%BUILD_DIR% | PYTHON=%PYTHON%"
call :say ""

REM -- (1) static: Windows native pipeline + both archs are build targets --
call :say "[1] Windows native pipeline (vcpkg to build.bat to setup.bat to pytest) and arch support, static verification"
call :ex "(1) dependency vcpkg manifest (install.sh counterpart)" "%PROJECT_ROOT%\vcpkg.json"
call :ex "(1) CMakeSettings.json (VS2022)" "%PROJECT_ROOT%\CMakeSettings.json"
call :ex "(2) build.bat (x64 native build)" "%PROJECT_ROOT%\build.bat"
call :gr "(2) build.bat --all option" "%PROJECT_ROOT%\build.bat" "--all"
call :gr "(2) build.bat --minimal option" "%PROJECT_ROOT%\build.bat" "--minimal"
call :gr "(2) build.bat --category option" "%PROJECT_ROOT%\build.bat" "--category"
call :ex "(3) setup.bat (model/media download)" "%PROJECT_ROOT%\setup.bat"
REM actually parse vcpkg.json to confirm it is valid JSON
call :pyc "(1) vcpkg.json parses as valid JSON" "import json;json.load(open('vcpkg.json',encoding='utf-8'))"
REM both the x86_64 and aarch64 toolchains must exist for "both architectures" to be native build targets
call :ex "x86_64 toolchain (= x86-64 native build target)" "%PROJECT_ROOT%\cmake\toolchain.x86_64.cmake"
call :ex "aarch64 toolchain (= aarch64 native build target)" "%PROJECT_ROOT%\cmake\toolchain.aarch64.cmake"
call :say ""

REM -- (2) runtime: whether the native pipeline actually holds on the current x64 host --
call :say "[2] native pipeline feasibility on the current host (x86_64/Windows)"
REM (2) artifact: whether a real native build happened on this host (bin\*_sync.exe exists)
set "HAVE_BIN="
if defined BUILD_DIR for %%f in ("%BUILD_DIR%\*_sync.exe") do set "HAVE_BIN=1"
if defined HAVE_BIN ( call :pass "(2) native build artifacts present (x64: %BUILD_DIR%\*_sync.exe)" ) else ( call :skipcmd "(2) native build artifacts (x64)" "after VS2022+vcpkg: build.bat --all" )
REM (3)+(4): if models (setup.bat artifacts) + build artifacts exist, verify actual inference via the pytest path
call :rt "(3)(4) setup models + pytest actual inference (x64 host)" "full pipeline: after vcpkg install, build.bat --all then setup.bat then pytest -m e2e_image" "cpp-img"
REM the aarch64 native pipeline is verified on aarch64 (Linux) hardware via test_523.sh
call :skipcmd "aarch64 native pipeline (that arch hardware required)" "on aarch64 Linux hardware run test_523.sh (install.sh then build.sh then setup.sh then run_tc.sh)"
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
:pyc
if not defined PYTHON ( call :skip "%~1 (python not found)" & goto :eof )
"%PYTHON%" -c "%~2" >nul 2>&1 && ( call :pass "%~1" ) || ( call :fail "%~1" )
goto :eof
:skipcmd
call :skip "%~1"
call :say "   |_ manual: %~2"
goto :eof
:rt
if not defined PYTHON ( call :skip "%~1 (python not found)" & goto :eof )
call :say "   $ _rt_resolve.py %~3"
"%PYTHON%" "%SCRIPT_DIR%_rt_resolve.py" %~3 >nul 2>&1
set "RC=%ERRORLEVEL%"
if "%RC%"=="0" ( call :pass "%~1" ) else if "%RC%"=="77" ( call :skipcmd "%~1" "%~2" ) else ( call :fail "%~1 (rc=%RC%)" )
goto :eof
