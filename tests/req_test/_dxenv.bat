@echo off
REM =========================================================================
REM _dxenv.bat - shared environment discovery for tests\req_test\test_*.bat
REM
REM   Sets the following in the CALLER's scope. That is why this script must
REM   NOT use setlocal (with setlocal the values never reach the caller):
REM     PYTHON     path to the python that actually starts (undefined if none)
REM     BUILD_DIR  dir holding *_sync.exe / *_async.exe   (undefined if none)
REM
REM   Precondition: the caller has already set PROJECT_ROOT.
REM   Usage:  call "%SCRIPT_DIR%_dxenv.bat"
REM
REM   Already-defined values are never overwritten, so a caller can clear
REM   PYTHON= before the call, or force BUILD_DIR from the environment
REM   (same behaviour as the test_*.sh scripts).
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

REM -- PYTHON ---------------------------------------------------------------
REM Mirrors the test_*.sh search order (venv, .venv, shared runtime venv,
REM PATH) and adds a Windows-only py-launcher fallback.
if not defined PYTHON if defined VIRTUAL_ENV if exist "%VIRTUAL_ENV%\Scripts\python.exe" set "PYTHON=%VIRTUAL_ENV%\Scripts\python.exe"
if not defined PYTHON if defined PYTHON_PATH set "PYTHON=%PYTHON_PATH%"
for %%v in (venv .venv) do if not defined PYTHON if exist "%PROJECT_ROOT%\%%v\Scripts\python.exe" set "PYTHON=%PROJECT_ROOT%\%%v\Scripts\python.exe"
REM dx-all-suite shared runtime venv (counterpart of ..\venv-dx-runtime on Linux)
if not defined PYTHON if exist "%PROJECT_ROOT%\..\venv-dx-runtime\Scripts\python.exe" set "PYTHON=%PROJECT_ROOT%\..\venv-dx-runtime\Scripts\python.exe"
if not defined PYTHON ( where python >nul 2>&1 && set "PYTHON=python" )
REM Startup check: the Windows Store stub python.exe is found by `where` but
REM only opens the Store page when run. Keep it only if --version works.
if defined PYTHON ( "%PYTHON%" --version >nul 2>&1 || set "PYTHON=" )
REM py launcher fallback (same last resort as setup.bat). Callers quote it as
REM "%PYTHON%", so it must stay a single argument-free token: `py`, not `py -3`.
if not defined PYTHON ( where py >nul 2>&1 && set "PYTHON=py" )
if defined PYTHON ( "%PYTHON%" --version >nul 2>&1 || set "PYTHON=" )

REM -- BUILD_DIR ------------------------------------------------------------
REM Where build.bat / CMakeSettings.json actually place artifacts:
REM   build tree     out\build\[cfg]                     cfg = x64-Release or x64-Debug
REM   install tree   out\install\[cfg]\bin[\Release or \Debug]
REM   final copy     bin\                                only created when BUILD_SCOPE=all
REM The old candidate list only had bin / build_x86_64\release\bin (a Linux
REM style name) / build\bin, so builds that skip the install-copy step
REM (--minimal / --category) never resolved BUILD_DIR and every runtime check
REM was SKIPped.
if not defined _DXCFG if defined BUILD_CONFIG set "_DXCFG=%BUILD_CONFIG%"
if not defined _DXCFG set "_DXCFG=x64-Release"
set "_DXSHORT=%_DXCFG%"
for /f "tokens=2 delims=-" %%A in ("%_DXCFG%") do set "_DXSHORT=%%A"
REM bin\Release / bin\Debug are the MSVC default output locations. Keep these
REM candidates in sync with resolve_bin_dir() in tests\cpp_example\conftest.py -
REM if they drift apart this gate passes while pytest collects 0 tests, which
REM reads as "PASS with nothing executed".
for %%d in (
    "bin"
    "bin\Release"
    "bin\Debug"
    "out\install\%_DXCFG%\bin\%_DXSHORT%"
    "out\install\%_DXCFG%\bin"
    "out\install\x64-Release\bin\Release"
    "out\install\x64-Release\bin"
    "out\install\x64-Debug\bin\Debug"
    "out\install\x64-Debug\bin"
    "out\build\%_DXCFG%"
    "out\build\x64-Release"
    "out\build\x64-Debug"
    "build_x86_64\release\bin"
    "build\bin"
) do if not defined BUILD_DIR if exist "%PROJECT_ROOT%\%%~d\*.exe" set "BUILD_DIR=%PROJECT_ROOT%\%%~d"
set "_DXCFG="
set "_DXSHORT="
goto :eof
