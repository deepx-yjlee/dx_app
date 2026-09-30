@echo off
REM > SDKREQ-518 - Various input source support (Windows)
REM   [Requirement] every C++ executable and Python example must work with image / stream inference.
REM             except that image-only tasks (embedding/reid/attribute_recognition/object_pose_estimation/
REM             3d_object_detection/super_resolution) and face models are
REM             excluded from stream inference.
REM             (hand_detection/hand_landmark support stream via per-frame single-model inference.)
REM   [Verify] (1) input options (-i/-v/-c/-r) + C++ input abstraction layer exist (static)
REM          (2) image/stream inference over all C++ binaries and Python examples (runtime)
REM              run_tc.bat does not exist, so the same pytest markers as run_tc.sh are driven directly:
REM              - python -m pytest -m e2e_image  (all examples, image)
REM              - python -m pytest -m e2e_stream (all examples, video; image-only/face auto-skipped)
REM   (Linux counterpart: test_517.sh)
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

REM -- (1) static: input options + input abstraction layer --
call :ex "C++ input abstraction layer" "%PROJECT_ROOT%\src\cpp_example\common\inputs"
call :gr "image input option -i/--image_path" "%PROJECT_ROOT%\src\cpp_example\common\runner\async_detection_runner.hpp" "i, image_path"
call :gr "video input option -v/--video_path" "%PROJECT_ROOT%\src\cpp_example\common\runner\async_detection_runner.hpp" "v, video_path"
call :gr "camera option -c/--camera_index" "%PROJECT_ROOT%\src\cpp_example\common\runner\async_detection_runner.hpp" "c, camera_index"
call :gr "RTSP option -r/--rtsp_url" "%PROJECT_ROOT%\src\cpp_example\common\runner\async_detection_runner.hpp" "r, rtsp_url"
call :ex "Windows build script" "%PROJECT_ROOT%\build.bat"

REM -- (2) runtime: image/stream inference for every example (pytest e2e_image/e2e_stream) --
REM pytest treats "0 tests collected (exit 5)" as SKIP, but if every case skips individually
REM because models are missing, exit 0 can be a false PASS, so gate the preconditions first.
set "HAVE_PYTEST="
if defined PYTHON ( "%PYTHON%" -c "import pytest" >nul 2>&1 && set "HAVE_PYTEST=1" )
set "HAVE_MODELS="
if defined PYTHON ( "%PYTHON%" "%SCRIPT_DIR%_rt_resolve.py" models-present >nul 2>&1 && set "HAVE_MODELS=1" )
set "HAVE_CPPBIN="
if defined BUILD_DIR if exist "%BUILD_DIR%\*_sync.exe" set "HAVE_CPPBIN=1"
set "HAVE_PYRT="
if defined PYTHON ( "%PYTHON%" -c "import dx_engine" >nul 2>&1 && set "HAVE_PYRT=1" )

REM C++: all executables image / stream
set "CPP_OK="
if defined HAVE_PYTEST if defined HAVE_CPPBIN if defined HAVE_MODELS set "CPP_OK=1"
if defined CPP_OK (
    call :tc "C++ all binaries image inference (pytest -m e2e_image)" "cpp_example" "e2e_image"
    call :tc "C++ all binaries stream inference, image-only excluded (pytest -m e2e_stream)" "cpp_example" "e2e_stream"
) else (
    call :skipcmd "C++ all binaries image inference (pytest -m e2e_image)" "after VS2022 build+models+NPU: cd tests\cpp_example then python -m pytest -m e2e_image"
    call :skipcmd "C++ all binaries stream inference, image-only excluded (pytest -m e2e_stream)" "after VS2022 build+models+NPU: cd tests\cpp_example then python -m pytest -m e2e_stream"
)

REM Python: all examples image / stream
set "PY_OK="
if defined HAVE_PYTEST if defined HAVE_PYRT if defined HAVE_MODELS set "PY_OK=1"
if defined PY_OK (
    call :tc "Python all examples image inference (pytest -m e2e_image)" "python_example" "e2e_image"
    call :tc "Python all examples stream inference, image-only excluded (pytest -m e2e_stream)" "python_example" "e2e_stream"
) else (
    call :skipcmd "Python all examples image inference (pytest -m e2e_image)" "after venv+dx_engine+models+NPU: cd tests\python_example then python -m pytest -m e2e_image"
    call :skipcmd "Python all examples stream inference, image-only excluded (pytest -m e2e_stream)" "after venv+dx_engine+models+NPU: cd tests\python_example then python -m pytest -m e2e_stream"
)

REM -- camera / RTSP (input source coverage, device and server required) --
call :rt "USB camera live connection (auto-detect)" "camera device required: run_tc (Linux) --camera --camera-index 0" "cam"
call :skipcmd "RTSP live connection" "stream server required: bin\yolov5_sync.exe -r rtsp://(addr)/stream"
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
:tc
REM %1 title  %2 test subfolder (cpp_example or python_example)  %3 pytest marker (e2e_image or e2e_stream)
if not defined PYTHON ( call :skip "%~1 (python not found)" & goto :eof )
call :say "   $ pytest -m %~3 -v  (tests\%~2)"
pushd "%PROJECT_ROOT%\tests\%~2"
REM -v and NO redirection on purpose: pytest per-test progress must stream to
REM the console live, mirroring tc() in test_517.sh. :tee would buffer the whole
REM e2e run and print nothing until it ended. Standalone runs therefore keep only
REM the [PASS]/[FAIL] lines in LOGFILE; run_all.bat already redirects the child's
REM full output into that same log, so nothing is lost there.
"%PYTHON%" -m pytest -m %~3 --tb=short -v
set "RC=%ERRORLEVEL%"
popd
if "%RC%"=="0" ( call :pass "%~1" ) else if "%RC%"=="5" ( call :skipcmd "%~1" "environment incomplete (0 tests collected) - check build/models/NPU" ) else ( call :fail "%~1 (rc=%RC%)" )
goto :eof
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
:rt
if not defined PYTHON ( call :skip "%~1 (python not found)" & goto :eof )
call :say "   $ _rt_resolve.py %~3"
"%PYTHON%" "%SCRIPT_DIR%_rt_resolve.py" %~3 >nul 2>&1
set "RC=%ERRORLEVEL%"
if "%RC%"=="0" ( call :pass "%~1" ) else if "%RC%"=="77" ( call :skipcmd "%~1" "%~2" ) else ( call :fail "%~1 (rc=%RC%)" )
goto :eof
