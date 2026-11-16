"""Sammelt die Lizenztexte aller mitgelieferten Teile in <ziel>\\Lizenzen
und schreibt eine Uebersicht (Hinweise zu Drittanbieter-Software.txt)."""
import glob
import os
import shutil
import sys
import sysconfig

OUT = os.path.join(sys.argv[1], "Lizenzen")
FFMPEG_ROOT = os.path.dirname(os.environ["VD_FFMPEG_DIR"].rstrip("\\/"))
SITE = sysconfig.get_paths()["purelib"]

PKGS = [  # (dist-Name, Anzeigename, Lizenz, Quelle)
    ("yt_dlp", "yt-dlp", "Unlicense (gemeinfrei)", "https://github.com/yt-dlp/yt-dlp"),
    ("pywebview", "pywebview", "BSD-3-Clause", "https://github.com/r0x0r/pywebview"),
    ("pythonnet", "pythonnet", "MIT", "https://github.com/pythonnet/pythonnet"),
    ("clr_loader", "clr-loader", "MIT", "https://github.com/pythonnet/clr-loader"),
    ("curl_cffi", "curl_cffi", "MIT (enthaelt libcurl, curl-Lizenz)", "https://github.com/lexiforest/curl_cffi"),
    ("cffi", "cffi", "MIT", "https://github.com/python-cffi/cffi"),
    ("pillow", "Pillow", "MIT-CMU", "https://github.com/python-pillow/Pillow"),
    ("certifi", "certifi", "MPL-2.0", "https://github.com/certifi/python-certifi"),
    ("websockets", "websockets", "BSD-3-Clause", "https://github.com/python-websockets/websockets"),
    ("brotli", "Brotli", "MIT", "https://github.com/google/brotli"),
    ("pycryptodomex", "PyCryptodome", "BSD-2-Clause / Public Domain", "https://github.com/Legrandin/pycryptodome"),
    ("requests", "requests", "Apache-2.0", "https://github.com/psf/requests"),
    ("urllib3", "urllib3", "MIT", "https://github.com/urllib3/urllib3"),
    ("bottle", "bottle", "MIT", "https://github.com/bottlepy/bottle"),
    ("proxy_tools", "proxy_tools", "BSD", "https://github.com/jtushman/proxy_tools"),
    ("typing_extensions", "typing_extensions", "PSF-2.0", "https://github.com/python/typing_extensions"),
]


def main():
    if os.path.isdir(OUT):
        shutil.rmtree(OUT)
    os.makedirs(OUT)
    lines = [
        "Video Downloader - Hinweise zu Drittanbieter-Software",
        "=" * 56,
        "",
        "Diese App enthaelt folgende Open-Source-Software. Die vollstaendigen Lizenztexte",
        "liegen im Ordner 'Lizenzen' neben dieser Datei.",
        "",
        "FFmpeg (ffmpeg.exe, ffprobe.exe)",
        "  Lizenz: GNU General Public License v3 (GPLv3)",
        "  Build: 'essentials' von Gyan Doshi, https://www.gyan.dev/ffmpeg/builds/",
        "  Quellcode: https://ffmpeg.org/download.html und https://github.com/FFmpeg/FFmpeg",
        "  FFmpeg ist ein eigenstaendiges Programm, das die App nur aufruft.",
        "",
        "Python 3.12",
        "  Lizenz: PSF License, https://docs.python.org/3/license.html",
        "",
    ]
    for f in ("LICENSE", "README.txt"):
        src = os.path.join(FFMPEG_ROOT, f)
        if os.path.exists(src):
            shutil.copy(src, os.path.join(OUT, f"FFmpeg-{f}" if f != "LICENSE" else "FFmpeg-LICENSE.txt"))
    py_lic = os.path.join(sys.base_prefix, "LICENSE.txt")
    if os.path.exists(py_lic):
        shutil.copy(py_lic, os.path.join(OUT, "Python-LICENSE.txt"))
    for dist, name, lic, url in PKGS:
        lines += [name, f"  Lizenz: {lic}", f"  Quelle: {url}", ""]
        for info in glob.glob(os.path.join(SITE, f"{dist}-*.dist-info")):
            for path in glob.glob(os.path.join(info, "**", "*"), recursive=True):
                base = os.path.basename(path).upper()
                if os.path.isfile(path) and (base.startswith("LICEN") or base.startswith("COPYING") or base.startswith("NOTICE")):
                    shutil.copy(path, os.path.join(OUT, f"{name}-{os.path.basename(path)}.txt".replace(".txt.txt", ".txt")))
    lines += [
        "Hinweis: Lade nur Inhalte herunter, bei denen du das darfst (z. B. fuer den privaten",
        "Gebrauch). Die Nutzungsbedingungen von YouTube und TikTok gelten weiterhin.",
    ]
    with open(os.path.join(sys.argv[1], "Hinweise zu Drittanbieter-Software.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    print("Lizenzen:", len(os.listdir(OUT)))


if __name__ == "__main__":
    main()
