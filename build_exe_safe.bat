@echo off
chcp 65001 >nul
cls

echo ========================================================
echo   通用 Python 打包腳本 (PyInstaller)
echo ========================================================
echo.
echo 解決中文路徑編碼問題 - 使用虛擬磁碟機方案
echo.

REM ---------------------------------------------------------------------
REM [修改注意 1] 設定虛擬環境名稱
REM 如果您的虛擬環境資料夾不叫 .venv (例如 venv, myenv)，請在此修改
REM ---------------------------------------------------------------------
set VENV_NAME=.venv

REM ---------------------------------------------------------------------
REM [修改注意 2] 設定主程式入口
REM 請將 program/GUI.py 改為您程式的主要執行檔路徑 (例如 main.py)
REM ---------------------------------------------------------------------
set MAIN_SCRIPT=program/main.py

REM ---------------------------------------------------------------------
REM [修改注意 3] 設定生成的執行檔名稱 (不需要 .exe 副檔名)
REM ---------------------------------------------------------------------
set EXE_NAME=LuckyWheelApp

REM ---------------------------------------------------------------------
REM [修改注意 4] 設定需要額外打包的資料夾
REM 格式為 "來源資料夾;目標資料夾"，如果有多個請用空格分隔
REM 例如: --add-data "assets;assets" --add-data "config;config"
REM 如果不需要打包資料，請清空 DATA_OPTS
REM ---------------------------------------------------------------------
set DATA_OPTS=--add-data "assets;assets"

REM ---------------------------------------------------------------------
REM [修改注意 5] 設定需要搜尋的模組路徑或隱藏匯入
REM --paths: 增加額外的模組搜尋資料夾 (例如 program)
REM --hidden-import: 手動加入 PyInstaller 沒偵測到的模組 (例如 ui_files)
REM ---------------------------------------------------------------------
set IMPORT_OPTS=--paths program --hidden-import ui_files

REM =====================================================================
REM 以下為自動執行邏輯，通常不需要修改
REM =====================================================================

REM 0. Clean previous build (清除舊的打包檔案)
echo [Init] Cleaning previous build files...
if exist build (
    echo    Removing build folder...
    rd /s /q build
)
if exist dist (
    echo    Removing dist folder...
    rd /s /q dist
)
if exist "%EXE_NAME%.spec" (
    echo    Removing %EXE_NAME%.spec...
    del /q "%EXE_NAME%.spec"
)

REM 1. Mount current directory to Drive Z:
set BUILD_DRIVE=Z:
if exist Z:\ (
    if exist Y:\ (
        set BUILD_DRIVE=X:
    ) else (
        set BUILD_DRIVE=Y:
    )
)

echo Mounting project to drive %BUILD_DRIVE% ...
subst %BUILD_DRIVE% "%~dp0."
if %errorlevel% neq 0 (
    echo [Error] Failed to mount virtual drive.
    pause
    exit /b 1
)

REM 2. Switch to Build Drive
%BUILD_DRIVE%
cd \

REM 3. Run PyInstaller
echo.
echo [Build] Starting PyInstaller from %BUILD_DRIVE% ...
echo Using Python from: %VENV_NAME%\Scripts\python.exe
echo.

set PYTHON_EXE=%VENV_NAME%\Scripts\python.exe

REM 執行打包指令
%PYTHON_EXE% -m PyInstaller --noconsole --onefile ^
    %IMPORT_OPTS% ^
    %DATA_OPTS% ^
    --name "%EXE_NAME%" ^
    %MAIN_SCRIPT%

set BUILD_RESULT=%errorlevel%

REM 4. Cleanup
echo.
echo [Cleanup] Removing virtual drive...
c:
subst %BUILD_DRIVE% /d

if %BUILD_RESULT% neq 0 (
    echo.
    echo ========================================================
    echo    [FAILED] Packaging failed.
    echo ========================================================
    echo.
    echo Please check the error messages above.
    pause
    exit /b 1
)

echo.
echo ========================================================
echo    [SUCCESS] Packaging Complete!
echo ========================================================
echo.
echo The executable is located at:
echo    %~dp0dist\%EXE_NAME%.exe
echo.
pause
