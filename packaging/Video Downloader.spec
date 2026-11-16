# PyInstaller-Bauplan fuer die fertige EXE.
# Bauen:  packaging\build.bat   (legt alles unter %LOCALAPPDATA%\VideoDownloaderBuild ab)
import os
from PyInstaller.utils.hooks import collect_all, collect_submodules

APP = os.path.abspath(os.path.join(SPECPATH, ".."))
FFMPEG = os.environ["VD_FFMPEG_DIR"]  # Ordner mit ffmpeg.exe + ffprobe.exe (essentials build)

datas = [
    (os.path.join(APP, "ui.html"), "."),
    (os.path.join(APP, "icon.ico"), "."),
    (os.path.join(APP, "icon.png"), "."),
    (os.path.join(APP, "icon-128.png"), "."),
    (os.path.join(APP, "intro.wav"), "."),
    (os.path.join(APP, "feedback_form.json"), "."),
    (os.path.join(FFMPEG, "ffmpeg.exe"), "ffmpeg"),
    (os.path.join(FFMPEG, "ffprobe.exe"), "ffmpeg"),
]
binaries = []
hiddenimports = ["ytdlp_updater"]
# mutagen bewusst NICHT dabei (GPL, wird von der App nicht gebraucht)
for pkg in ("yt_dlp", "curl_cffi", "webview", "certifi", "websockets", "brotli", "Cryptodome"):
    try:
        d, b, h = collect_all(pkg)
        datas += d; binaries += b; hiddenimports += h
    except Exception as ex:  # optionale Pakete
        print("skip", pkg, ex)

a = Analysis(
    [os.path.join(APP, "Video Downloader.pyw")],
    pathex=[APP],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["tkinter", "numpy", "skia", "PIL.ImageQt", "matplotlib", "pytest", "mutagen"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="Video Downloader",
    icon=os.path.join(APP, "icon.ico"),
    version=os.path.join(SPECPATH, "version_info.txt"),
    console=False,
    upx=False,
)
coll = COLLECT(exe, a.binaries, a.datas, name="Video Downloader", upx=False)
