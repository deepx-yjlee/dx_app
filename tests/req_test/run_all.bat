@echo off
REM =========================================================================
REM run_all.bat - run every Windows requirement test (test_*.bat) at once
REM               and print one aggregate PASS/FAIL/SKIP summary.
REM
REM Each test_[N].bat self-reports "Result: PASS=.. FAIL=.. SKIP=.." and exits
REM with a code equal to its FAIL count. This wrapper runs them all and tallies.
REM
REM Usage:
REM   tests\req_test\run_all.bat                run all test_*.bat
REM   tests\req_test\run_all.bat 518 520 530    run only these requirement numbers
REM
REM Exit code: number of scripts that reported at least one FAIL (0 = all clean).
REM (Linux: run the matching test_[N].sh files via run_all.sh.)
REM
REM Each script's FULL output is kept in tests\req_test\logs\[name].log and is
REM never deleted, so a finished run can still be inspected. The console keeps
REM showing only the one-line-per-script summary.
REM =========================================================================
setlocal enabledelayedexpansion
set "SCRIPT_DIR=%~dp0"
set "LOGDIR=%SCRIPT_DIR%logs"
if not exist "%LOGDIR%" mkdir "%LOGDIR%" >nul 2>&1
REM Each test_*.bat writes its own logs\[name].log when run standalone. Here the
REM whole child output is already redirected to that very file, so tell the child
REM to stand down - two writers on one path is a sharing violation. This also
REM suppresses the child's end-of-run pause, so run_all never blocks.
set "DXREQ_NOLOG=1"
set /a gP=0, gF=0, gS=0, nScripts=0, nFailed=0
set "FAILED="

set "LIST="
if "%~1"=="" (
    for %%f in ("%SCRIPT_DIR%test_*.bat") do set "LIST=!LIST! %%~nf"
) else (
    for %%a in (%*) do (
        if exist "%SCRIPT_DIR%test_%%a.bat" ( set "LIST=!LIST! test_%%a" ) else ( echo [skip] test_%%a.bat not found )
    )
)

echo Running requirement test^(s^) in %SCRIPT_DIR% ...
echo Full per-script logs are kept in %LOGDIR%
echo ------------------------------------------------------------------
for %%n in (%LIST%) do call :one %%n
echo ------------------------------------------------------------------
echo TOTAL  PASS=%gP%  FAIL=%gF%  SKIP=%gS%   (scripts: %nScripts%, with failures: %nFailed%)
if %nFailed% GTR 0 echo Failing scripts:%FAILED%
exit /b %nFailed%

:one
set "NAME=%~1"
REM Keep the full output on disk instead of piping it straight into findstr -
REM piping discarded every line the script printed once the run finished.
set "LOGFILE=%LOGDIR%\%NAME%.log"
cmd /c "%SCRIPT_DIR%%NAME%.bat" > "%LOGFILE%" 2>&1
set "SUMLINE="
for /f "usebackq delims=" %%L in (`findstr /b /c:"Result:" "%LOGFILE%"`) do set "SUMLINE=%%L"
set /a p=0, f=0, s=0
if defined SUMLINE (
    for /f "tokens=2,3,4" %%a in ("!SUMLINE!") do (
        for /f "tokens=2 delims==" %%x in ("%%a") do set /a p=%%x
        for /f "tokens=2 delims==" %%y in ("%%b") do set /a f=%%y
        for /f "tokens=2 delims==" %%z in ("%%c") do set /a s=%%z
    )
)
set /a gP+=p, gF+=f, gS+=s, nScripts+=1
if %f% GTR 0 (
    echo   [FAIL] %NAME%    PASS=%p%  FAIL=%f%  SKIP=%s%    log: !LOGFILE!
    set "FAILED=%FAILED% %NAME%"
    set /a nFailed+=1
) else (
    echo   [ ok ] %NAME%    PASS=%p%  FAIL=%f%  SKIP=%s%    log: !LOGFILE!
)
goto :eof
