@echo off
REM > SDKREQ-528 - Model/asset download (Windows)
REM   [Requirement] setup.bat --all must download every .dxnn model in the ModelZoo plus the test video.
REM   [Verify] (1) static check that the downloader (setup_assets.py)/setup.bat/options exist
REM          (2) check that the setup --all artifacts are actually in place:
REM              - whether the .dxnn count in assets\models matches the expected value (default 347)
REM              - whether a test video exists in assets\videos
REM   run mode (RUN_FULL=1 or --run): actually runs setup.bat --all before (2) above to download.
REM     (by default it does not download - network and several GB - it only checks already-downloaded assets.)
REM   the expected model count can be overridden with EXPECTED_MODELS (default 347).
REM   (Linux counterpart: test_527.sh)
REM =========================================================================
REM   ---------------------------------------------------------------------
REM   ASCII ONLY, CRLF ONLY - and print via `call :say "..."`, never `echo`.
REM   A non-ASCII byte or an LF-only ending desyncs cmd.exe's byte-offset
REM   re-seek (the script dies mid-run); a bare echo lets angle brackets and
REM   pipes in the message act as redirection and the line vanishes.
REM   See _dxlog.bat / _dxenv.bat and README.md section 1.5.
REM Result: [PASS]/[FAIL]/[SKIP], exit code = number of FAILs
REM   [PASS] static/runtime verification passed  [SKIP] environment required (manual)
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
REM settings: expected model count (overridable), actual run mode
if not defined EXPECTED_MODELS set "EXPECTED_MODELS=347"
if /I "%~1"=="--run" set "RUN_FULL=1"
if not defined RUN_FULL set "RUN_FULL=0"
call :say "PROJECT_ROOT=%PROJECT_ROOT% | EXPECTED_MODELS=%EXPECTED_MODELS% | RUN_FULL=%RUN_FULL% | PYTHON=%PYTHON%"
call :say ""

REM -- (1) static: downloader/options/manifest exist --
call :say "[1] downloader/manifest/option static verification"
call :ex "downloader setup_assets.py" "%PROJECT_ROOT%\scripts\setup_assets.py"
call :gr "model output path assets" "%PROJECT_ROOT%\scripts\setup_assets.py" "assets"
call :gr "--all option (setup_assets.py)" "%PROJECT_ROOT%\scripts\setup_assets.py" "--all"
call :ex "setup.bat" "%PROJECT_ROOT%\setup.bat"
call :ex "ModelZoo manifest" "%PROJECT_ROOT%\scripts\modelzoo_manifest.json"
call :runpy "setup_assets.py --help exit 0" "scripts\setup_assets.py --help"
call :manifest_count
call :say ""

REM -- (2) runtime: check the setup --all artifacts (model count / video present) --
call :say "[2] setup --all artifact verification (%EXPECTED_MODELS% models + test video)"
if "%RUN_FULL%"=="1" goto :run_setup
call :say "   |_ to actually download: set RUN_FULL=1 and rerun, or test_528.bat --run"
goto :after_setup
:run_setup
call :say "   |_ [FULL] RUN_FULL=1: actually runs setup.bat --all - network, several GB"
call :runstage "setup.bat --all actual download" "call setup.bat --all"
:after_setup
call :model_count
call :video_check
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
:skipcmd
call :skip "%~1"
call :say "   |_ manual: %~2"
goto :eof
:runpy
if not defined PYTHON ( call :skip "%~1 (python not found)" & goto :eof )
call :say "   $ %PYTHON% %~2"
"%PYTHON%" %~2 >nul 2>&1 && ( call :pass "%~1" ) || ( call :fail "%~1" )
goto :eof
:runstage
REM %1 title  %2 actual command - show the log then PASS/FAIL by ERRORLEVEL, propagate rc.
call :say "   $ %~2"
%~2
set "RSRC=%ERRORLEVEL%"
if "%RSRC%"=="0" ( call :pass "%~1" ) else ( call :fail "%~1 (run failed rc=%RSRC%)" )
exit /b %RSRC%
:manifest_count
REM manifest .dxnn entry count (informational). via a temp file (set /p) to avoid a for/f quote quirk.
if not defined PYTHON goto :eof
"%PYTHON%" -c "import json;print(sum(1 for e in json.load(open('scripts/modelzoo_manifest.json',encoding='utf-8')) if str(e.get('dxnn_url','')).endswith('.dxnn')))" > "%TEMP%\_dx528_man.txt" 2>nul
set "MANC=?"
if exist "%TEMP%\_dx528_man.txt" set /p MANC=<"%TEMP%\_dx528_man.txt"
del "%TEMP%\_dx528_man.txt" 2>nul
call :say "   |_ manifest .dxnn entry count = %MANC%  / expected downloads = %EXPECTED_MODELS%"
goto :eof
:model_count
REM whether the .dxnn count in assets\models matches the expected value (SKIP if absent). via a temp file (set /p).
REM   Windows downloads straight into assets\models with no links (a real directory). os.walk(followlinks=True)
REM   is identical to a normal walk for a real directory - it is kept defensively in case of links.
if not exist "%PROJECT_ROOT%\assets\models\" ( call :skipcmd "%EXPECTED_MODELS% models downloaded" "network: setup.bat --all or --run creates assets\models" & goto :eof )
if not defined PYTHON ( call :skip "%EXPECTED_MODELS% models check (python not found)" & goto :eof )
"%PYTHON%" -c "import os;print(sum(1 for r,_,fs in os.walk('assets/models',followlinks=True) for f in fs if f.endswith('.dxnn')))" > "%TEMP%\_dx528_mc.txt" 2>nul
set "MC=0"
if exist "%TEMP%\_dx528_mc.txt" set /p MC=<"%TEMP%\_dx528_mc.txt"
del "%TEMP%\_dx528_mc.txt" 2>nul
call :say "   |_ expected=%EXPECTED_MODELS%  actual=%MC%  assets\models\*.dxnn"
if "%MC%"=="%EXPECTED_MODELS%" ( call :pass "%EXPECTED_MODELS% models downloaded" ) else ( call :fail "model count mismatch expected=%EXPECTED_MODELS% actual=%MC%" )
goto :eof
:video_check
REM whether a video file exists in assets\videos (SKIP if absent). via a temp file (set /p).
if not exist "%PROJECT_ROOT%\assets\videos\" ( call :skipcmd "test video present" "network: setup.bat --all creates assets\videos" & goto :eof )
if not defined PYTHON ( call :skip "test video check (python not found)" & goto :eof )
"%PYTHON%" -c "import os;e=('.mp4','.mov','.avi','.mkv','.webm','.m4v');print(sum(1 for r,_,fs in os.walk('assets/videos',followlinks=True) for f in fs if f.lower().endswith(e)))" > "%TEMP%\_dx528_vc.txt" 2>nul
set "VC=0"
if exist "%TEMP%\_dx528_vc.txt" set /p VC=<"%TEMP%\_dx528_vc.txt"
del "%TEMP%\_dx528_vc.txt" 2>nul
call :say "   |_ videos found=%VC%  assets\videos"
if not "%VC%"=="0" ( call :pass "test videos present: %VC% @ assets\videos" ) else ( call :fail "no test video - assets\videos is empty" )
goto :eof
:rt
if not defined PYTHON ( call :skip "%~1 (python not found)" & goto :eof )
call :say "   $ _rt_resolve.py %~3"
"%PYTHON%" "%SCRIPT_DIR%_rt_resolve.py" %~3 >nul 2>&1
set "RC=%ERRORLEVEL%"
if "%RC%"=="0" ( call :pass "%~1" ) else if "%RC%"=="77" ( call :skipcmd "%~1" "%~2" ) else ( call :fail "%~1 (rc=%RC%)" )
goto :eof
