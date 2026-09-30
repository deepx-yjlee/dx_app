@echo off
REM > SDKREQ-520 - Per-AI-task inference result output format (Windows)
REM   [Requirement] C++ examples infer via the per-task SyncRunner and print the result to stdout in "a fixed format".
REM     - Object Detection : [DET] class conf x1 y1 x2 y2 frame_w frame_h  (verbose=--show-log)
REM     - Classification   : "Top predictions:" top 5 + [CLS] pipeline tag
REM     - Pose : [POSE] / Instance Seg : [ISEG] / OBB : [OBB] / Face : [FACE] /
REM       Face Alignment : [ALIGN] / Hand Landmark : [HAND] / 3D Det : [3D]
REM     - Semantic Seg/Depth/Embedding/Restoration : the result is an image, saved with no stdout tag
REM       (with --show-log an INFO "produces image-based ..." is printed)
REM   [Verify] (1) static check that per-category output format markers exist in the runner sources (SKIP if absent)
REM          (2) actually run 1 representative per category with --show-log and check the format marker
REM              (_rt_resolve.py cpp-showlog --per-task - the per-category representative style of run_tc --e2e-short)
REM   Cannot test: actual output value correctness needs NPU+.dxnn (format/code path is checkable from source).
REM   (Linux counterpart: test_519.sh)
REM =========================================================================
REM   ---------------------------------------------------------------------
REM   ASCII ONLY, CRLF ONLY - and print via `call :say "..."`, never `echo`.
REM   A non-ASCII byte or an LF-only ending desyncs cmd.exe's byte-offset
REM   re-seek (the script dies mid-run); a bare echo lets angle brackets and
REM   pipes in the message act as redirection and the line vanishes.
REM   See _dxlog.bat / _dxenv.bat and README.md section 1.5.
REM Result: [PASS]/[FAIL]/[SKIP], exit code = number of FAILs
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
set "RUNNER=%PROJECT_ROOT%\src\cpp_example\common\runner"
call :say "PROJECT_ROOT=%PROJECT_ROOT% | PYTHON=%PYTHON%"
call :say ""

REM -- (1) static: per-category output format markers in the runner sources (SKIP if absent) --
REM tag style (dedicated runner, verbose=--show-log gated)
call :grcat "Object Detection"        "sync_detection_runner.hpp"      "[DET]"
call :grcat "Classification(Top-K)"   "sync_classification_runner.hpp" "Top predictions:"
call :grcat "Pose Estimation"         "sync_pose_runner.hpp"           "[POSE]"
call :grcat "Instance Segmentation"   "sync_segmentation_runner.hpp"   "[ISEG]"
call :grcat "OBB Detection"           "sync_obb_runner.hpp"            "[OBB]"
call :grcat "Face Detection"          "sync_face_runner.hpp"           "[FACE]"
call :grcat "Face Alignment"          "sync_face_alignment_runner.hpp" "[ALIGN]"
call :grcat "Hand Landmark"           "sync_hand_landmark_runner.hpp"  "[HAND]"
call :grcat "3D Object Detection"     "sync_3d_detection_runner.hpp"   "[3D]"
REM runner reuse (alias / include) - the output format is that of the reused runner
call :grcat "Object Pose (->Pose)"        "sync_pose_runner.hpp"           "[POSE]"
call :grcat "Keypoint Detection (->Pose)" "sync_pose_runner.hpp"           "[POSE]"
call :grcat "Panoptic Driving (->Det)"    "sync_detection_runner.hpp"      "[DET]"
call :grcat "Hand Detection (->Face,[HAND])" "sync_face_runner.hpp"        "[HAND]"
call :grcat "Attribute Recog (->Cls)"     "sync_classification_runner.hpp" "Top predictions:"
REM image-based (no text tag - the result image is saved; with --show-log, produces image-based)
call :grcat "Semantic Seg(img save)"  "sync_semantic_seg_runner.hpp"   "produces image-based"
call :grcat "Depth Estimation(img)"   "sync_depth_runner.hpp"          "produces image-based"
call :grcat "Embedding(img)"          "sync_embedding_runner.hpp"      "produces image-based"
call :grcat "ReID (->Embedding,img)"  "sync_embedding_runner.hpp"      "produces image-based"
call :grcat "Restoration/SR/Denoise/Enhance(img)" "sync_restoration_runner.hpp" "produces image-based"
REM PPU: reuses the detection/face/pose runner per model - no single output format
call :skip "output format PPU (varies by model: detection->[DET] / face->[FACE] / pose->[POSE] reused)"

REM -- (2) runtime: run 1 representative per category with --show-log, check the output format marker --
call :rt "per-category --show-log output format live check (1 representative each)" "after VS2022 build+models+NPU: bin\(model)_sync.exe -i (img) --show-log --no-display  (see run_tc --e2e-short)" "cpp-showlog --per-task"

REM extra: whether the Python examples expose --show-log and actually start
call :gr "Python --show-log option present" "%PROJECT_ROOT%\src\python_example\common\runner\args.py" "--show-log"
call :pyhelp "Python example runtime startup (--help exit 0)" "src\python_example\object_detection" "*_sync.py"
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
:gr
findstr /C:"%~3" "%~2" >nul 2>&1 && ( call :pass "%~1" ) || ( call :fail "%~1 (not found: %~3)" )
goto :eof
:grcat
REM %1 category label  %2 runner filename  %3 expected output format marker  (SKIP if absent)
findstr /C:"%~3" "%RUNNER%\%~2" >nul 2>&1 && ( call :pass "output format %~1 ('%~3' @ %~2)" ) || ( call :skip "output format %~1 (marker not found: '%~3' @ %~2)" )
goto :eof
:skipcmd
call :skip "%~1"
call :say "   |_ manual: %~2"
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
REM %1 title  %2 manual guidance on SKIP  %3 _rt_resolve args (pass quoted)
if not defined PYTHON ( call :skip "%~1 (python not found)" & goto :eof )
call :say "   $ _rt_resolve.py %~3"
call :tee "%PYTHON%" "%SCRIPT_DIR%_rt_resolve.py" %~3
if "%RC%"=="0" ( call :pass "%~1" ) else if "%RC%"=="77" ( call :skipcmd "%~1" "%~2" ) else ( call :fail "%~1 (rc=%RC%)" )
goto :eof
