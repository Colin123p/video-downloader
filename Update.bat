@echo off
echo Aktualisiere yt-dlp (falls YouTube oder TikTok etwas geaendert haben) ...
python -m pip install -U "yt-dlp[default,curl-cffi]" pywebview pillow
echo.
echo Fertig. Fenster kann geschlossen werden.
pause
