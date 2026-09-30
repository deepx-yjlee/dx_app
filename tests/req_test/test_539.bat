@echo off
REM > SDKREQ-539 - Standalone model package extraction (Windows)
REM   the --output-dir/--no-generate-sln options of extract_sln_package.bat/.py and the
REM   verifies the SLN extractor CLI startup and Visual Studio solution generation.
REM   verifies actual extraction (--no-generate-sln, file copy) up to CMakeLists generation, and
REM   with --run / RUN_FULL=1 it also verifies actually generating the .sln with CMake (needs cmake+VS2022).
REM   (Linux counterpart: test_538.sh)
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
REM --run / RUN_FULL=1: verify actually generating the .sln with CMake from the extracted package
if /I "%~1"=="--run" set "RUN_FULL=1"
if not defined RUN_FULL set "RUN_FULL=0"
call :say "PROJECT_ROOT=%PROJECT_ROOT% | BUILD_DIR=%BUILD_DIR% | RUN_FULL=%RUN_FULL% | PYTHON=%PYTHON%"
call :say ""
call :ex "extract_sln_package.bat" "%PROJECT_ROOT%\scripts\extract_sln_package.bat"
call :ex "extract_sln_package.py" "%PROJECT_ROOT%\scripts\extract_sln_package.py"
call :gr "--output-dir option" "%PROJECT_ROOT%\scripts\extract_sln_package.py" "--output-dir"
call :gr "--no-generate-sln option" "%PROJECT_ROOT%\scripts\extract_sln_package.py" "--no-generate-sln"
call :pyc "extract_sln_package.py parses" "import ast;ast.parse(open('scripts/extract_sln_package.py',encoding='utf-8').read())"
REM run: whether the SLN extractor CLI actually starts (--help exit 0)
call :runpy "extract_sln_package.py --help exit 0" "scripts\extract_sln_package.py --help"
REM run: actually extract an SLN standalone package (--no-generate-sln, file copy - no VS needed) + confirm CMakeLists generation
call :sln_extract
REM --run: actually generate the .sln with CMake (VS2022 generator required)
if "%RUN_FULL%"=="1" ( call :sln_generate ) else ( call :skipcmd "SLN .sln actual generation + VS2022 build (--run)" "set RUN_FULL=1 and rerun, or test_539.bat --run - generate the .sln with CMake+VS2022" )
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
:sln_extract
REM actual SLN standalone package extraction (--no-generate-sln, file copy) - confirm CMakeLists generation (no VS needed).
if not defined PYTHON ( call :skip "SLN standalone package extraction (python not found)" & goto :eof )
set "MODELB="
for /d %%d in ("%PROJECT_ROOT%\src\cpp_example\object_detection\*") do if not defined MODELB set "MODELB=%%~nxd"
if not defined MODELB ( call :skip "SLN standalone package extraction (no example)" & goto :eof )
set "SLN_OUT=%TEMP%\req539_out"
if exist "%SLN_OUT%" rd /s /q "%SLN_OUT%"
call :say "   $ extract_sln_package.py object_detection/%MODELB% --output-dir (tmp) --no-generate-sln"
"%PYTHON%" scripts\extract_sln_package.py "object_detection/%MODELB%" --output-dir "%SLN_OUT%" --no-generate-sln >nul 2>&1
if exist "%SLN_OUT%\sln\object_detection\%MODELB%\CMakeLists.txt" ( call :pass "SLN standalone package extraction + CMakeLists generated" ) else ( call :fail "SLN standalone package extraction (CMakeLists not generated)" )
goto :eof
:sln_generate
REM --run: actually generate the .sln with CMake (VS2022 generator required). PASS if generated, else SKIP (no VS).
if not defined PYTHON ( call :skip "SLN .sln actual generation (python not found)" & goto :eof )
where cmake >nul 2>&1 || ( call :skipcmd "SLN .sln actual generation (--run)" "cmake+VS2022 required" & goto :eof )
set "MODELB="
for /d %%d in ("%PROJECT_ROOT%\src\cpp_example\object_detection\*") do if not defined MODELB set "MODELB=%%~nxd"
set "SLN_GEN=%TEMP%\req539_gen"
if exist "%SLN_GEN%" rd /s /q "%SLN_GEN%"
call :say "   $ extract_sln_package.py object_detection/%MODELB% --output-dir (tmp)  [CMake .sln generate]"
"%PYTHON%" scripts\extract_sln_package.py "object_detection/%MODELB%" --output-dir "%SLN_GEN%" >nul 2>&1
set "SLNOK="
for /r "%SLN_GEN%" %%f in (*.sln) do set "SLNOK=1"
if defined SLNOK ( call :pass "SLN actually generated (.sln, --run)" ) else ( call :skipcmd "SLN actual generation (--run)" "VS2022 generator required: .sln not generated" )
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
