@echo off
REM =========================================================================
REM _dxlog.bat - shared console+file logging setup for tests\req_test\test_*.bat
REM
REM   Sets the following in the CALLER's scope. That is why this script must
REM   NOT use setlocal (with setlocal the values never reach the caller):
REM     LOGFILE  tests\req_test\logs\[script].log - full transcript of this run.
REM              Truncated once here, then appended to by the caller's :say
REM              and :tee helpers. NEVER deleted afterwards, so the output can
REM              still be read after the console window is gone.
REM     DXTMP    scratch file used by :tee to capture a sub-process' stdout so
REM              it can be shown live AND appended to LOGFILE.
REM
REM   Precondition: the caller has already set SCRIPT_DIR.
REM   Usage:  call "%SCRIPT_DIR%_dxlog.bat" "%~n0"
REM
REM   DXREQ_NOLOG=1 disables the per-script log file. run_all.bat sets it
REM   because it already redirects each child's whole output to the very same
REM   logs\[script].log - if the child also opened that file the write would
REM   fail with a sharing violation.
REM
REM   ---------------------------------------------------------------------
REM   ASCII ONLY - DO NOT PUT NON-ASCII TEXT IN THIS FILE.
REM   cmd.exe re-seeks a batch file by byte offset but computes the step from
REM   the codepage-converted length, so every multi-byte character desyncs the
REM   parser: parsing resumes in the middle of a later line and REM text gets
REM   executed as a command ("'...' is not recognized as an internal or
REM   external command"). Redirection characters inside those fragments then
REM   produce "The system cannot find the file/path specified.".
REM   For the same reason never put raw redirection or pipe characters in a
REM   REM line - write them as [cfg] / "or" instead, or escape them with ^^.
REM =========================================================================

set "LOGDIR=%~dp0logs"
set "LOGFILE="
set "DXTMP=%TEMP%\dxreq_%~1_%RANDOM%.tmp"
if defined DXREQ_NOLOG goto :eof
if not exist "%LOGDIR%" mkdir "%LOGDIR%" >nul 2>&1
if not exist "%LOGDIR%" goto :eof
set "LOGFILE=%LOGDIR%\%~1.log"
REM Truncate: this run replaces the previous run's transcript for this script.
type nul > "%LOGFILE%" 2>nul || set "LOGFILE="
goto :eof
