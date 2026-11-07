@echo off
chcp 65001 >nul
title Emote Audio Studio
cd /d "%~dp0"

python --version >nul 2>&1
if errorlevel 1 (
  echo Python belum terpasang. Pasang Python 3.9+ dari python.org, centang "Add to PATH".
  pause
  exit /b 1
)

echo Memperbarui yt-dlp ^(boleh gagal kalau offline, bisa diperbarui lewat tombol di website^)...
python -m pip install -U --pre --disable-pip-version-check "yt-dlp[default,curl-cffi]"
if errorlevel 1 python -m pip install -U --pre --disable-pip-version-check "yt-dlp[default]"

python app.py
pause