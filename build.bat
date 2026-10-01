@echo off
REM Builds the standalone CAT:annotation.exe into dist\CAT-annotation\
REM Requires: pip install pyinstaller (not a runtime dependency, build-only)

pyinstaller main.spec --noconfirm
if %ERRORLEVEL% NEQ 0 (
    echo Build failed.
    exit /b 1
)

echo.
echo Build complete: dist\CAT-annotation\CAT-annotation.exe
