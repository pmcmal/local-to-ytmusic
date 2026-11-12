@echo off
rem Buduje LocalToYTMusic.exe (jeden plik, bez konsoli) do folderu dist\
cd /d "%~dp0"
if not exist .venv (
    py -3 -m venv .venv || exit /b 1
)
.venv\Scripts\python.exe -m pip install -q -r requirements-build.txt || exit /b 1
.venv\Scripts\pyinstaller --noconfirm --clean --onefile --windowed --name LocalToYTMusic ^
    --icon assets\icon.ico --add-data "assets\icon.ico;assets" ^
    --collect-data ytmusicapi --copy-metadata ytmusicapi local_to_ytmusic.py || exit /b 1
echo.
echo Gotowe: dist\LocalToYTMusic.exe
