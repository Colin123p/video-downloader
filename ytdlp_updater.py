"""Haelt yt-dlp in der fertigen EXE aktuell (YouTube/TikTok aendern oft etwas).

In der EXE steckt eine feste yt-dlp-Version. Zusaetzlich laedt die App im Hintergrund
hoechstens einmal am Tag die neueste offizielle Version von GitHub (yt-dlp/yt-dlp,
Datei "yt-dlp" = Python-ZIP) und prueft sie gegen die offizielle SHA-256-Liste.
Beim naechsten Start wird dann diese neuere Version benutzt. Klappt das nicht
(z. B. kaputte Datei), faellt die App automatisch auf die eingebaute Version zurueck.
"""
import hashlib
import importlib.abc
import importlib.util
import json
import os
import sys
import time
import urllib.request
import zipimport

RELEASE_API = "https://api.github.com/repos/yt-dlp/yt-dlp/releases/latest"
ASSET = "yt-dlp"            # plattformunabhaengiges Python-ZIP
SUMS = "SHA2-256SUMS"
CHECK_EVERY = 24 * 3600


class _ZipFirstFinder(importlib.abc.MetaPathFinder):
    """Laedt 'yt_dlp' und alle Untermodule aus der heruntergeladenen ZIP statt aus der EXE."""

    def __init__(self, zip_path):
        self.zip_path = zip_path

    def find_spec(self, fullname, path=None, target=None):
        if fullname != "yt_dlp" and not fullname.startswith("yt_dlp."):
            return None
        parts = fullname.split(".")
        importer = zipimport.zipimporter(os.path.join(self.zip_path, *parts[:-1]))
        return importer.find_spec(fullname)


def load_yt_dlp(data_dir):
    """Importiert yt_dlp: zuerst die aktualisierte ZIP (falls vorhanden), sonst die eingebaute."""
    zip_path = os.path.join(data_dir, "yt-dlp.zip")
    if getattr(sys, "frozen", False) and os.path.exists(zip_path):
        finder = _ZipFirstFinder(zip_path)
        sys.meta_path.insert(0, finder)
        try:
            import yt_dlp  # noqa: F401
            from yt_dlp import YoutubeDL  # noqa: F401  (prueft, dass es wirklich laeuft)
            return sys.modules["yt_dlp"]
        except Exception:  # noqa: BLE001  -> ZIP unbrauchbar: weg damit, eingebaute nehmen
            sys.meta_path.remove(finder)
            for name in [n for n in sys.modules if n == "yt_dlp" or n.startswith("yt_dlp.")]:
                del sys.modules[name]
            try:
                os.remove(zip_path)
            except OSError:
                pass
    try:
        import yt_dlp
        return yt_dlp
    except ImportError:
        return None


def _get(url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": "VideoDownloader-Updater",
                                               "Accept": "application/octet-stream, application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def update_in_background(data_dir, current_version):
    """Prueft auf eine neue yt-dlp-Version und legt sie fuer den naechsten Start bereit."""
    if not getattr(sys, "frozen", False):
        return  # im Entwickler-Modus macht das Update.bat (pip)
    os.makedirs(data_dir, exist_ok=True)
    stamp = os.path.join(data_dir, "yt-dlp-check.json")
    try:
        with open(stamp, encoding="utf-8") as fh:
            st = json.load(fh)
        if time.time() - st.get("checked", 0) < CHECK_EVERY:
            return
    except (OSError, ValueError):
        pass
    try:
        rel = json.loads(_get(RELEASE_API))
        tag = rel.get("tag_name", "")
        result = {"checked": time.time(), "latest": tag, "current": current_version}
        if tag and tag != current_version:
            assets = {a["name"]: a["browser_download_url"] for a in rel.get("assets", [])}
            if ASSET in assets and SUMS in assets:
                sums = _get(assets[SUMS]).decode("utf-8", "replace")
                want = None
                for line in sums.splitlines():
                    p = line.split()
                    if len(p) == 2 and p[1].lstrip("*") == ASSET:
                        want = p[0].lower()
                data = _get(assets[ASSET], timeout=120)
                if want and hashlib.sha256(data).hexdigest() == want:
                    tmp = os.path.join(data_dir, "yt-dlp.zip.new")
                    with open(tmp, "wb") as fh:
                        fh.write(data)
                    os.replace(tmp, os.path.join(data_dir, "yt-dlp.zip"))
                    result["installed"] = tag
                else:
                    result["error"] = "checksum mismatch"
        with open(stamp, "w", encoding="utf-8") as fh:
            json.dump(result, fh)
    except Exception as ex:  # noqa: BLE001  (kein Internet o. Ae. -> naechstes Mal)
        try:
            with open(stamp, "w", encoding="utf-8") as fh:
                json.dump({"checked": time.time() - CHECK_EVERY + 3600, "error": str(ex)[:200]}, fh)
        except OSError:
            pass
