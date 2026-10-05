@echo off
chcp 65001 > nul
setlocal EnableExtensions EnableDelayedExpansion

title 2026 Environment Installer

:: ============================================================
:: 2026 Environment Installer
:: Release: v1.0.0
::
:: Installs:
::   - Python 3.13.16
::   - PostgreSQL 18.4
::   - pgAdmin 4
::   - Ollama
::   - Gemma 4
::   - Python packages from requirements.txt
::
:: NOTE:
::   PostgreSQL database creation and .dump restoration are
::   intentionally NOT handled by this script.
:: ============================================================

set "PROJECT_DIR=%~dp0"
set "DOWNLOAD_DIR=%USERPROFILE%\Downloads"

set "BASE_URL=https://github.com/zhihuac-tku/2026_env_install/releases/download/v1.0.0"

set "FILE_PY=python-3.13.16-amd64.exe"
set "FILE_PSQL=postgresql-18.4-2-windows-x64.exe"
set "FILE_PGADMIN=pgadmin4-9.18-x64.exe"
set "FILE_OLLAMA=OllamaSetup.exe"

cd /d "%DOWNLOAD_DIR%"

echo.
echo ============================================================
echo              2026 Environment Installer
echo ============================================================
echo.
echo Project folder:
echo %PROJECT_DIR%
echo.
echo Installation files will be downloaded to:
echo %DOWNLOAD_DIR%
echo.

:: ------------------------------------------------------------
:: 1. Download installation files
:: ------------------------------------------------------------
echo [1/6] Downloading installation files...
echo.

for %%F in ("%FILE_PY%" "%FILE_PSQL%" "%FILE_PGADMIN%" "%FILE_OLLAMA%") do (
    if exist "%%~F" (
        echo   [OK] %%~F already exists. Skip download.
    ) else (
        echo   [Download] %%~F
        curl.exe -L --fail --retry 3 "%BASE_URL%/%%~F" -o "%%~F"

        if errorlevel 1 (
            echo.
            echo [ERROR] Failed to download %%~F
            echo Please check GitHub Release v1.0.0.
            echo.
            pause
            exit /b 1
        )

        echo   [OK] Download completed.
    )
)

echo.
echo Download completed.
echo.

:: ------------------------------------------------------------
:: 2. Install Python 3.13.16
:: ------------------------------------------------------------
echo ============================================================
echo [2/6] Installing Python 3.13.16
echo ============================================================
echo.
echo Please complete the Python installation window.
echo.
echo IMPORTANT:
echo   If the option is shown, check "Add Python.exe to PATH".
echo.
pause

start /wait "" "%DOWNLOAD_DIR%\%FILE_PY%"

echo.
echo Detecting Python 3.13 installation...
echo.

set "PYTHON_EXE="

if exist "%LocalAppData%\Programs\Python\Python313\python.exe" (
    set "PYTHON_EXE=%LocalAppData%\Programs\Python\Python313\python.exe"
)

if not defined PYTHON_EXE if exist "%ProgramFiles%\Python313\python.exe" (
    set "PYTHON_EXE=%ProgramFiles%\Python313\python.exe"
)

if not defined PYTHON_EXE (
    py -3.13 -c "import sys; print(sys.executable)" > "%TEMP%\python_path.txt" 2>nul
    if exist "%TEMP%\python_path.txt" (
        set /p PYTHON_EXE=<"%TEMP%\python_path.txt"
        del "%TEMP%\python_path.txt" >nul 2>&1
    )
)

if not defined PYTHON_EXE (
    for /f "delims=" %%P in ('where python 2^>nul') do (
        if not defined PYTHON_EXE set "PYTHON_EXE=%%P"
    )
)

if not defined PYTHON_EXE (
    echo.
    echo [ERROR] Python could not be detected.
    echo Please install Python 3.13.16 manually and run this script again.
    echo.
    pause
    exit /b 1
)

echo [OK] Python detected:
echo      %PYTHON_EXE%
"%PYTHON_EXE%" --version

for %%P in ("%PYTHON_EXE%") do set "PYTHON_DIR=%%~dpP"
set "PATH=%PYTHON_DIR%;%PYTHON_DIR%Scripts;%PATH%"

:: ------------------------------------------------------------
:: 3. Install PostgreSQL 18.4
:: ------------------------------------------------------------
echo.
echo ============================================================
echo [3/6] Installing PostgreSQL 18.4
echo ============================================================
echo.
echo The PostgreSQL installer will now open.
echo.
echo IMPORTANT:
echo   - Complete the PostgreSQL installation.
echo   - Remember the postgres password.
echo   - You may cancel/skip Stack Builder if offered.
echo   - The .dump file is NOT restored by this script.
echo.
pause

start /wait "" "%DOWNLOAD_DIR%\%FILE_PSQL%"

echo.
echo PostgreSQL installation step completed.
echo.

:: ------------------------------------------------------------
:: 4. Install pgAdmin 4
:: ------------------------------------------------------------
echo ============================================================
echo [4/6] Installing pgAdmin 4
echo ============================================================
echo.
echo The pgAdmin installer will now open.
echo.
echo IMPORTANT:
echo   - Complete the pgAdmin installation.
echo   - pgAdmin will be used to manage PostgreSQL databases.
echo   - Database creation and .dump restoration are NOT
echo     performed automatically by this script.
echo.
pause

start /wait "" "%DOWNLOAD_DIR%\%FILE_PGADMIN%"

echo.
echo pgAdmin installation step completed.
echo.

:: ------------------------------------------------------------
:: 5. Install Ollama and download Gemma 4
:: ------------------------------------------------------------
echo ============================================================
echo [5/6] Installing Ollama
echo ============================================================
echo.

start /wait "" "%DOWNLOAD_DIR%\%FILE_OLLAMA%"

echo.
echo Detecting Ollama...
echo.

set "OLLAMA_EXE="

for /f "delims=" %%O in ('where ollama.exe 2^>nul') do (
    if not defined OLLAMA_EXE set "OLLAMA_EXE=%%O"
)

if not defined OLLAMA_EXE if exist "%LocalAppData%\Programs\Ollama\ollama.exe" (
    set "OLLAMA_EXE=%LocalAppData%\Programs\Ollama\ollama.exe"
)

if not defined OLLAMA_EXE if exist "%LocalAppData%\Ollama\ollama.exe" (
    set "OLLAMA_EXE=%LocalAppData%\Ollama\ollama.exe"
)

if not defined OLLAMA_EXE (
    echo.
    echo [ERROR] Ollama could not be detected.
    echo Please restart Windows or install Ollama manually.
    echo.
    pause
    exit /b 1
)

echo [OK] Ollama detected:
echo      %OLLAMA_EXE%
echo.

tasklist /FI "IMAGENAME eq ollama.exe" 2>nul | find /I "ollama.exe" >nul

if errorlevel 1 (
    echo Starting Ollama service...
    start "" "%OLLAMA_EXE%" serve
    timeout /t 5 /nobreak >nul
) else (
    echo Ollama is already running.
)

echo.
echo Downloading Gemma 4 model...
echo This may take some time.
echo.

"%OLLAMA_EXE%" pull gemma4

if errorlevel 1 (
    echo.
    echo [WARNING] Gemma 4 download failed.
    echo You can retry later with:
    echo     ollama pull gemma4
    echo.
) else (
    echo.
    echo [OK] Gemma 4 download completed.
)

:: ------------------------------------------------------------
:: 6. Install Python packages
:: ------------------------------------------------------------
echo.
echo ============================================================
echo [6/6] Installing Python packages
echo ============================================================
echo.

cd /d "%PROJECT_DIR%"

if not exist "requirements.txt" (
    echo [ERROR] requirements.txt was not found.
    echo Expected:
    echo %PROJECT_DIR%requirements.txt
    echo.
    pause
    exit /b 1
)

echo Upgrading pip...
"%PYTHON_EXE%" -m pip install --upgrade pip

echo.
echo Installing packages from requirements.txt...
echo.

"%PYTHON_EXE%" -m pip install -r requirements.txt

if errorlevel 1 (
    echo.
    echo ========================================================
    echo [ERROR] Python package installation failed.
    echo ========================================================
    echo.
    pause
    exit /b 1
)

:: ------------------------------------------------------------
:: Finish
:: ------------------------------------------------------------
echo.
echo ============================================================
echo                 Installation Completed
echo ============================================================
echo.
echo [OK] Python 3.13.16
echo [OK] PostgreSQL 18.4
echo [OK] pgAdmin 4
echo [OK] Ollama
echo [OK] Gemma 4
echo [OK] Python packages
echo.
echo NOTE:
echo   PostgreSQL database creation and .dump restoration
echo   have NOT been performed by this script.
echo.
echo Project folder:
echo %PROJECT_DIR%
echo.
echo You can now use pgAdmin to create the database and
echo restore the PostgreSQL .dump file.
echo.
echo You can now start the Streamlit application.
echo.
pause

endlocal
