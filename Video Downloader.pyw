"""Video Downloader - YouTube (bis 4K) und TikTok (ohne Wasserzeichen).
Modernes Fenster (pywebview) mit yt-dlp + ffmpeg. Doppelklick startet die App ohne Konsole.

Wichtig: Alle Attribute der Api-Klasse, die nicht vom Fenster aufgerufen werden,
muessen mit "_" anfangen. Sonst durchsucht pywebview sie beim Start rekursiv
(z. B. das Fenster-Objekt) und die App friert ein."""
import ctypes
import json
import locale
import os
import shutil
import subprocess
import tempfile
import sys
import threading
import time

import webview

import ytdlp_updater

APP_NAME = "Video Downloader"
APP_VERSION = "1.0.0"
FROZEN = getattr(sys, "frozen", False)  # True = laeuft als fertige EXE (PyInstaller)
APP_DIR = os.path.dirname(os.path.abspath(sys.executable if FROZEN else __file__))
# Dateien der App (Oberflaeche, Icon, Sound, ffmpeg): in der EXE im _internal-Ordner
RES_DIR = getattr(sys, "_MEIPASS", APP_DIR)
# Einstellungen: in der EXE pro Benutzer unter %APPDATA% (Programmordner ist schreibgeschuetzt)
DATA_DIR = os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"), APP_NAME) if FROZEN else APP_DIR
os.makedirs(DATA_DIR, exist_ok=True)
CONFIG = os.path.join(DATA_DIR, "ordner.txt")
LANG_FILE = os.path.join(DATA_DIR, "sprache.txt")
DEFAULT_DIR = os.path.join(os.path.expanduser("~"), "Downloads", APP_NAME)
UI = os.path.join(RES_DIR, "ui.html")
ICON = os.path.join(RES_DIR, "icon.ico")
INTRO_SOUND = os.path.join(RES_DIR, "intro.wav")
# Ziel fuer Bewertungen: Google-Formular des Entwicklers (Adresse + Feld-IDs, siehe feedback_form.json)
FEEDBACK_FORM_FILE = os.path.join(RES_DIR, "feedback_form.json")

yt_dlp = ytdlp_updater.load_yt_dlp(DATA_DIR)
NO_WINDOW = 0x08000000  # ffmpeg ohne schwarzes Konsolenfenster starten

LANGS = ("de", "en", "es", "fr", "it", "pt", "nl", "pl", "tr", "ru", "uk", "ar", "hi", "ja", "ko", "zh")
HEIGHTS = {"2160": 2160, "1440": 1440, "1080": 1080, "720": 720}
# TikTok: niemals das "download"-Format (das hat das Wasserzeichen)
TT_CLEAN = "[format_id!=download][format_note!*=?watermarked]"


def yt_format(h):
    # VP9 vor AV1 (laeuft auf mehr PCs fluessig), Ton als AAC fuer MP4 mit Ton ueberall
    return (
        f"bv*[height<={h}][vcodec^=vp09]+ba[ext=m4a]/"
        f"bv*[height<={h}][vcodec^=avc1]+ba[ext=m4a]/"
        f"bv*[height<={h}]+ba/b[height<={h}]/bv*+ba/b"
    )


def find_ffmpeg():
    bundled = os.path.join(RES_DIR, "ffmpeg")  # in der EXE mitgeliefert
    if os.path.exists(os.path.join(bundled, "ffmpeg.exe")):
        return bundled
    p = shutil.which("ffmpeg")
    if p:
        return os.path.dirname(p)
    base = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Microsoft", "WinGet", "Packages")
    if os.path.isdir(base):
        for root, _d, files in os.walk(base):
            if "ffmpeg.exe" in files:
                return root
    return None


def system_lang():
    """Sprache von Windows (z. B. de_AT -> de). Nicht unterstuetzte Sprachen -> Englisch."""
    try:
        lcid = ctypes.windll.kernel32.GetUserDefaultUILanguage()
        name = locale.windows_locale.get(lcid, "")
    except Exception:  # noqa: BLE001
        name = ""
    code = name.split("_")[0].lower()
    return code if code in LANGS else "en"


def is_tiktok(info):
    return "tiktok" in (info.get("extractor_key") or info.get("extractor") or "").lower()


class Cancelled(Exception):
    pass


class Api:
    def __init__(self):
        self._window = None
        self._ffmpeg = find_ffmpeg()
        self._cancel = False
        self._busy = False
        self._last_ui = 0.0
        self._fb_lock = threading.Lock()
        self._final = None
        self._proc = None

    # ---------- Fenster ----------
    def minimize(self):
        self._window.minimize()

    def close(self):
        self._cancel = True
        self._window.destroy()

    def play_intro(self):
        """Start-Sound, laeuft im Hintergrund parallel zur Animation."""
        if os.path.exists(INTRO_SOUND) and not os.environ.get("VD_SELFTEST"):
            try:
                import winsound
                winsound.PlaySound(INTRO_SOUND, winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT)
            except Exception:  # noqa: BLE001
                pass

    # ---------- Einstellungen ----------
    def _folder(self):
        try:
            with open(CONFIG, encoding="utf-8") as fh:
                p = fh.read().strip()
                if p:
                    return p
        except OSError:
            pass
        return DEFAULT_DIR

    def _lang(self):
        try:
            with open(LANG_FILE, encoding="utf-8") as fh:
                v = fh.read().strip()
                if v in LANGS:
                    return v
        except OSError:
            pass
        return system_lang()

    def get_state(self):
        fb = self._feedback()
        return {"folder": self._folder(), "lang": self._lang(), "syslang": system_lang(),
                "auto": not os.path.exists(LANG_FILE),
                "ytdlp": yt_dlp is not None, "ffmpeg": bool(self._ffmpeg),
                "rating": fb.get("rating", 0), "downloads": fb.get("downloads", 0),
                "asked": fb.get("asked", False)}

    # ---------- Bewertung (5 Sterne) ----------
    # Lokal in %APPDATA%\Video Downloader\feedback.json. Erst wenn der Nutzer auf "Senden" klickt,
    # gehen Sterne, Kommentar, App-Version und Sprache anonym an das Google-Formular des Entwicklers.
    # Ohne Internet bleibt die Bewertung in der Warteschlange und wird beim naechsten Start nachgeschickt.
    def _feedback_path(self):
        return os.path.join(DATA_DIR, "feedback.json")

    def _feedback(self):
        try:
            with open(self._feedback_path(), encoding="utf-8") as fh:
                return json.load(fh)
        except (OSError, ValueError):
            return {}

    def _save_fb(self, fb):
        try:
            with open(self._feedback_path(), "w", encoding="utf-8") as fh:
                json.dump(fb, fh, ensure_ascii=False, indent=1)
        except OSError:
            pass

    def save_feedback(self, rating, comment=""):
        rating = max(1, min(5, int(rating)))
        fb = self._feedback()
        fb["rating"] = rating
        fb["asked"] = True
        fb.setdefault("history", []).append({
            "rating": rating, "comment": str(comment or "")[:2000],
            "time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "version": APP_VERSION, "lang": self._lang(), "sent": False})
        self._save_fb(fb)
        threading.Thread(target=self._send_pending, daemon=True).start()
        return True

    def _send_pending(self):
        """Schickt alle noch nicht gesendeten Bewertungen an das Google-Formular."""
        with self._fb_lock:
            try:
                with open(FEEDBACK_FORM_FILE, encoding="utf-8") as fh:
                    form = json.load(fh)
            except (OSError, ValueError):
                return
            if not form.get("url") or not form.get("fields"):
                return
            fb = self._feedback()
            changed = False
            for item in fb.get("history", []):
                if item.get("sent"):
                    continue
                f = form["fields"]
                data = {f["rating"]: str(item["rating"]), f["comment"]: item.get("comment", ""),
                        f["version"]: item.get("version", ""), f["lang"]: item.get("lang", "")}
                try:
                    import urllib.parse
                    import urllib.request
                    req = urllib.request.Request(
                        form["url"], data=urllib.parse.urlencode(data).encode("utf-8"),
                        headers={"User-Agent": "VideoDownloader-Feedback",
                                 "Content-Type": "application/x-www-form-urlencoded"})
                    with urllib.request.urlopen(req, timeout=15) as r:
                        ok = 200 <= r.status < 400
                except Exception:  # noqa: BLE001  (offline -> spaeter nochmal)
                    ok = False
                if ok:
                    item["sent"] = True
                    changed = True
                else:
                    break
            if changed:
                self._save_fb(fb)

    def mark_rating_prompted(self):
        fb = self._feedback()
        fb["asked"] = True
        self._save_fb(fb)

    def _count_download(self):
        fb = self._feedback()
        fb["downloads"] = fb.get("downloads", 0) + 1
        self._save_fb(fb)
        return fb

    def set_lang(self, lang):
        """'auto' = wieder der Windows-Sprache folgen."""
        if lang == "auto":
            if os.path.exists(LANG_FILE):
                os.remove(LANG_FILE)
            return system_lang()
        if lang in LANGS:
            with open(LANG_FILE, "w", encoding="utf-8") as fh:
                fh.write(lang)
        return lang

    def choose_folder(self):
        res = self._window.create_file_dialog(webview.FileDialog.FOLDER, directory=self._folder())
        if res:
            p = os.path.normpath(res[0] if isinstance(res, (list, tuple)) else res)
            with open(CONFIG, "w", encoding="utf-8") as fh:
                fh.write(p)
            return p
        return None

    def open_folder(self):
        os.makedirs(self._folder(), exist_ok=True)
        os.startfile(self._folder())

    def open_file(self, path):
        if path and os.path.exists(path):
            os.startfile(path)

    def show_file(self, path):
        if path and os.path.exists(path):
            subprocess.Popen(["explorer", "/select,", os.path.normpath(path)])

    def get_clipboard(self):
        u32, k32 = ctypes.windll.user32, ctypes.windll.kernel32
        u32.GetClipboardData.restype = ctypes.c_void_p
        k32.GlobalLock.restype = ctypes.c_void_p
        k32.GlobalLock.argtypes = [ctypes.c_void_p]
        k32.GlobalUnlock.argtypes = [ctypes.c_void_p]
        text = ""
        if u32.OpenClipboard(0):
            try:
                h = u32.GetClipboardData(13)  # CF_UNICODETEXT
                if h:
                    p = k32.GlobalLock(h)
                    if p:
                        text = ctypes.wstring_at(p)
                        k32.GlobalUnlock(h)
            finally:
                u32.CloseClipboard()
        return text.strip()

    # ---------- Infos ----------
    def get_info(self, url):
        try:
            with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True, "noplaylist": True,
                                   "skip_download": True}) as ydl:
                info = ydl.extract_info(url, download=False)
        except Exception as ex:  # noqa: BLE001
            return {"error": self._clean(ex)}
        tt = is_tiktok(info)
        fmts = info.get("formats") or []
        if tt:
            fmts = [f for f in fmts if f.get("format_id") != "download"
                    and "watermark" not in (f.get("format_note") or "").lower()]
        # "p"-Wert = kurze Seite (TikTok ist hochkant: 1080x1920 -> 1080p)
        heights = sorted({min(f.get("height") or 0, f.get("width") or f.get("height") or 0)
                          for f in fmts if f.get("vcodec", "none") != "none"})
        thumb = info.get("thumbnail")
        if tt:
            for t in info.get("thumbnails") or []:
                if t.get("id") == "cover":
                    thumb = t.get("url")
        if not tt:
            for t in reversed(info.get("thumbnails") or []):
                u = t.get("url", "")
                if "maxresdefault" in u or "hq720" in u:
                    thumb = u
                    break
        return {
            "platform": "tiktok" if tt else "youtube",
            "title": self._title(info),
            "channel": ("@" + info["uploader"]) if tt and info.get("uploader") else
                       (info.get("channel") or info.get("uploader") or ""),
            "duration": info.get("duration") or 0,
            "views": info.get("view_count") or 0,
            "likes": info.get("like_count") or 0,
            "thumb": thumb,
            "maxh": heights[-1] if heights else 0,
            "fps": max([f.get("fps") or 0 for f in fmts] or [0]),
            # HDR vorhanden? (YouTube: dynamic_range "HDR10", "HLG" ... bei den Videoformaten)
            "hdr": any((f.get("dynamic_range") or "SDR") != "SDR" for f in fmts
                       if f.get("vcodec", "none") != "none"),
        }

    # ---------- Download ----------
    def cancel(self):
        self._cancel = True
        if self._proc and self._proc.poll() is None:
            self._proc.kill()

    def download(self, url, mode):
        if self._busy:
            return False
        self._busy = True
        self._cancel = False
        threading.Thread(target=self._worker, args=(url, mode), daemon=True).start()
        return True

    def _js(self, fn, *args):
        try:
            # run_js wartet nicht auf eine Antwort -> Oberflaeche bleibt fluessig
            self._window.run_js(f"{fn}({','.join(json.dumps(a) for a in args)})")
        except Exception:  # noqa: BLE001
            pass

    def _worker(self, url, mode):
        out = self._folder()
        os.makedirs(out, exist_ok=True)
        self._final = None
        tiktok = mode.startswith("tt_")
        tmpl = "TikTok @%(uploader)s %(id)s.%(ext)s" if tiktok else "%(title)s.%(ext)s"
        # Audio wird erst in einem eigenen Temp-Ordner gebaut: beim Umwandeln loescht yt-dlp
        # die Quelldatei - im Zielordner koennte das ein gleichnamiges, schon geladenes Video sein.
        audio_tmp = tempfile.mkdtemp(prefix="vd-") if mode in ("mp3", "tt_audio") else None
        opts = {
            "outtmpl": os.path.join(audio_tmp or out, tmpl),
            "windowsfilenames": True,
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            "noprogress": True,
            "progress_hooks": [self._hook],
            "postprocessor_hooks": [self._pp_hook],
        }
        if self._ffmpeg:
            opts["ffmpeg_location"] = self._ffmpeg

        kind = "video"
        if mode == "mp3":
            kind = "audio"
            opts["format"] = "ba/b"
            opts["postprocessors"] = [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3",
                                       "preferredquality": "320"}]
        elif mode == "tt_video":
            opts["format"] = f"b{TT_CLEAN}[vcodec!=none]"
            opts["format_sort"] = ["res", "br"]
        elif mode == "tt_audio":
            kind = "audio"
            # Ton aus dem Video selbst (nicht der Original-Song), ohne Wasserzeichen-Datei
            opts["format"] = f"b{TT_CLEAN}[vcodec!=none]"
            opts["format_sort"] = ["res", "br"]
            opts["postprocessors"] = [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3",
                                       "preferredquality": "320"}]
        elif mode == "tt_thumb":
            kind = "image"
        else:
            # Hoehe = gewaehlte Karte (auch z. B. "480" bei alten Videos). Das Format nimmt nie mehr
            # als diese Hoehe; hat das Video weniger, kommt die beste vorhandene (Label zeigt die echte).
            opts["format"] = yt_format(int(mode) if mode.isdigit() else HEIGHTS.get(mode, 2160))
            opts["merge_output_format"] = "mp4"
            # Gibt es das Video in HDR, wird HDR genommen (bei gleicher Aufloesung und fps)
            opts["format_sort"] = ["res", "fps", "hdr:12"]

        try:
            if kind == "image":
                info, path, dims = self._save_thumb(url, out)
                fb = self._count_download()
                self._js("onDone", {"title": self._title(info), "path": path, "label": "JPG · " + dims,
                                    "size": os.path.getsize(path), "kind": kind,
                                    "downloads": fb.get("downloads", 0), "asked": fb.get("asked", False),
                                    "rating": fb.get("rating", 0)})
                return
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)
                path = self._final or ydl.prepare_filename(info)
            base = os.path.splitext(path)[0]
            exts = {"audio": (".mp3",), "image": (".jpg", ".webp", ".png", ".jpeg"),
                    "video": (".mp4", ".mkv", ".webm")}[kind]
            for ext in exts:
                if os.path.exists(base + ext):
                    path = base + ext
                    break
            if kind == "image" and not os.path.exists(path):
                raise RuntimeError("Thumbnail nicht gefunden.")

            vcodec = (info.get("vcodec") or "").lower()
            if audio_tmp and os.path.exists(path):
                dest = os.path.join(out, os.path.basename(path))
                shutil.move(path, dest)
                path = dest

            if mode == "tt_video" and any(c in vcodec for c in ("h265", "hevc", "bytevc1", "hvc1", "hev1")):
                path = self._to_h264(path, info.get("duration") or 0)

            size = os.path.getsize(path) if os.path.exists(path) else 0
            h = min(info.get("height") or 0, info.get("width") or info.get("height") or 0)
            if kind == "audio":
                label = "MP3"
            elif kind == "image":
                label = "JPG"
            elif (h or 0) >= 2160:
                label = "4K"
            elif (h or 0) >= 1440:
                label = "2K"
            else:
                label = f"{h}p" if h else "MP4"
            if kind == "video" and (info.get("dynamic_range") or "SDR") != "SDR":
                label += " · HDR"
            fb = self._count_download()
            self._js("onDone", {"title": self._title(info), "path": path, "label": label,
                                "size": size, "kind": kind, "downloads": fb.get("downloads", 0),
                                "asked": fb.get("asked", False), "rating": fb.get("rating", 0)})
        except Cancelled:
            self._js("onError", "cancelled")
        except Exception as ex:  # noqa: BLE001
            self._js("onError", "cancelled" if self._cancel else self._clean(ex))
        finally:
            if audio_tmp:
                shutil.rmtree(audio_tmp, ignore_errors=True)
            self._busy = False
            self._proc = None

    def _to_h264(self, path, duration):
        """TikTok liefert 1080p oft nur als H.265. Windows spielt das ohne Zusatz-Codec
        nicht ab, darum wird es in H.264 umgewandelt (gleiche Aufloesung, sehr hohe Qualitaet)."""
        if not self._ffmpeg:
            return path
        self._js("onStage", "convert")
        tmp = os.path.splitext(path)[0] + ".h264.mp4"
        cmd = [os.path.join(self._ffmpeg, "ffmpeg.exe"), "-y", "-v", "error", "-progress", "pipe:1",
               "-i", path, "-c:v", "libx264", "-preset", "medium", "-crf", "16", "-pix_fmt", "yuv420p",
               "-c:a", "copy", "-movflags", "+faststart", tmp]
        self._proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                      text=True, creationflags=NO_WINDOW)
        for line in self._proc.stdout:
            if line.startswith("out_time_us=") and duration:
                try:
                    pct = int(line.split("=")[1]) / 1e6 / duration * 100
                    self._js("onConvert", max(0, min(100, pct)))
                except ValueError:
                    pass
        self._proc.wait()
        if self._cancel:
            if os.path.exists(tmp):
                os.remove(tmp)
            raise Cancelled()
        if self._proc.returncode == 0 and os.path.exists(tmp):
            os.replace(tmp, path)
        elif os.path.exists(tmp):
            os.remove(tmp)
        return path

    def _hook(self, d):
        if self._cancel:
            raise Cancelled()
        if d["status"] == "downloading":
            now = time.monotonic()  # hoechstens ~8 Updates pro Sekunde an die Oberflaeche
            if now - self._last_ui < 0.12:
                return
            self._last_ui = now
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            done = d.get("downloaded_bytes", 0)
            info = d.get("info_dict", {})
            part = "video" if info.get("vcodec", "none") != "none" else "audio"
            self._js("onProgress", {
                "pct": done / total * 100 if total else 0,
                "speed": d.get("speed") or 0,
                "eta": d.get("eta"),
                "done": done,
                "total": total,
                "part": part,
            })

    def _pp_hook(self, d):
        if d["status"] == "started":
            key = d.get("postprocessor", "")
            self._js("onStage", "audio" if "ExtractAudio" in key else
                     "thumb" if "Thumbnail" in key else "merge")
        if d["status"] == "finished":
            fp = d.get("info_dict", {}).get("filepath")
            if fp:
                self._final = fp

    @staticmethod
    def _title(info):
        t = (info.get("title") or "").strip()
        if is_tiktok(info) and (not t or t.startswith("TikTok video #")):
            t = (info.get("description") or "").strip() or f"TikTok @{info.get('uploader') or ''}".strip()
        return t

    def _save_thumb(self, url, out):
        """Groesstes TikTok-Titelbild suchen und als JPG speichern (yt-dlp nimmt sonst oft nur 540p)."""
        from io import BytesIO
        from PIL import Image
        self._js("onStage", "thumb")
        with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True, "noplaylist": True}) as ydl:
            info = ydl.extract_info(url, download=False)
            best, area = None, 0
            for t in info.get("thumbnails") or []:
                if self._cancel:
                    raise Cancelled()
                try:
                    data = ydl.urlopen(t["url"]).read()
                    im = Image.open(BytesIO(data))
                    im.load()
                except Exception:  # noqa: BLE001
                    continue
                if im.width * im.height > area:
                    best, area = im, im.width * im.height
        if best is None:
            raise RuntimeError("Thumbnail nicht gefunden.")
        if getattr(best, "is_animated", False):
            best.seek(0)
        name = f"TikTok @{info.get('uploader') or 'video'} {info.get('id')}.jpg"
        name = "".join("_" if c in '<>:"/\\|?*' else c for c in name)
        path = os.path.join(out, name)
        best.convert("RGB").save(path, "JPEG", quality=95)
        return info, path, f"{best.width}×{best.height}"

    @staticmethod
    def _clean(ex):
        msg = str(ex).replace("ERROR: ", "")
        if msg.startswith("[") and ":" in msg:
            msg = msg.split(":", 2)[-1].strip()
        return msg[:240]


def set_window_icon():
    """pywebview setzt unter Windows kein eigenes Icon -> per WinAPI nachreichen."""
    if not os.path.exists(ICON):
        return
    u32 = ctypes.windll.user32
    u32.FindWindowW.restype = ctypes.c_void_p
    u32.LoadImageW.restype = ctypes.c_void_p
    u32.LoadImageW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_uint, ctypes.c_int, ctypes.c_int, ctypes.c_uint]
    u32.SendMessageW.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_void_p, ctypes.c_void_p]
    for _ in range(50):
        hwnd = u32.FindWindowW(None, APP_NAME)
        if hwnd:
            break
        time.sleep(0.1)
    else:
        return
    big = u32.LoadImageW(None, ICON, 1, 256, 256, 0x10)    # IMAGE_ICON, LR_LOADFROMFILE
    small = u32.LoadImageW(None, ICON, 1, 32, 32, 0x10)
    if big:
        u32.SendMessageW(hwnd, 0x80, ctypes.c_void_p(1), ctypes.c_void_p(big))    # WM_SETICON, ICON_BIG
    if small:
        u32.SendMessageW(hwnd, 0x80, ctypes.c_void_p(0), ctypes.c_void_p(small))  # ICON_SMALL


def _selftest(api, win, out):
    """Nur fuer Tests: VD_SELFTEST=<ordner> setzen. Laedt je einen YouTube- und TikTok-Clip
    in allen Modi, schreibt das Ergebnis nach <ordner>\\selftest.txt und beendet die App."""
    global CONFIG, LANG_FILE
    os.makedirs(out, exist_ok=True)
    # Test-Einstellungen nur im Testordner, nie die echten Einstellungen anfassen
    CONFIG = os.path.join(out, "ordner.txt")
    LANG_FILE = os.path.join(out, "sprache.txt")
    log = open(os.path.join(out, "selftest.txt"), "w", encoding="utf-8", buffering=1)
    done = threading.Event()
    res = {}

    def hook(name):
        def f(*a):
            res["r"] = (name, a[0] if a else None)
            done.set()
        return f
    api._js = lambda fn, *a: hook(fn)(*a) if fn in ("onDone", "onError") else None
    try:
        time.sleep(5)
        log.write(f"frozen={FROZEN} ffmpeg={api._ffmpeg} data={DATA_DIR}\n")
        log.write(f"yt_dlp={yt_dlp.version.__version__} from={getattr(yt_dlp, '__file__', '?')}\n")
        log.write(f"ui_bridge={win.evaluate_js('typeof boot + \"/\" + typeof LANGS')}\n")
        with open(CONFIG, "w", encoding="utf-8") as fh:
            fh.write(os.path.join(out, "dl"))
        jobs = [("https://www.youtube.com/watch?v=YAFUyPp_238", "2160"),
                ("https://www.youtube.com/watch?v=YAFUyPp_238", "mp3"),
                ("https://www.tiktok.com/@_atyrka/video/7705874133321813266", "tt_video"),
                ("https://www.tiktok.com/@_atyrka/video/7705874133321813266", "tt_thumb"),
                ("https://www.tiktok.com/@_atyrka/video/7705874133321813266", "tt_audio")]
        for url, mode in jobs:
            info = api.get_info(url)
            log.write(f"info {mode}: {info.get('error') or (info.get('platform'), info.get('maxh'))}\n")
            done.clear()
            res.pop("r", None)
            while api._busy:  # vorheriger Download raeumt noch auf
                time.sleep(0.2)
            started = api.download(url, mode)
            done.wait(600) if started else None
            name, payload = res.get("r", ("timeout", None))
            log.write(f"{mode}: {name} {json.dumps(payload, ensure_ascii=False)[:300]}\n")
    except Exception as ex:  # noqa: BLE001
        log.write(f"EXC {ex!r}\n")
    log.write("end\n")
    log.close()
    os._exit(0)


if __name__ == "__main__":
    # Ohne Konsole (pythonw) gibt es kein stdout/stderr -> ins Leere umleiten statt abzustuerzen
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w")
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w")
    if os.environ.get("VD_SELFTEST"):  # Testmodus: Fehler und Abstuerze mitschreiben
        import faulthandler
        os.makedirs(os.environ["VD_SELFTEST"], exist_ok=True)
        sys.stderr = open(os.path.join(os.environ["VD_SELFTEST"], "stderr.txt"), "w", buffering=1)
        faulthandler.enable(sys.stderr)
        threading.excepthook = lambda a: sys.stderr.write(f"THREAD EXC {a.exc_type.__name__}: {a.exc_value}\n")
    # eigener Eintrag in der Taskleiste (statt "Python")
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Colin123p.VideoDownloader")
    except Exception:  # noqa: BLE001
        pass
    api = Api()
    win = webview.create_window(
        APP_NAME, UI, js_api=api,
        width=800, height=760, min_size=(660, 640),
        frameless=True, easy_drag=False, background_color="#09090b",
        hidden=bool(os.environ.get("VD_SELFTEST")),  # Selbsttest laeuft unsichtbar
    )
    api._window = win
    # Auto-Update ist abschaltbar: Setup-Option oder Datei "no-auto-update" in DATA_DIR
    if yt_dlp is not None and not os.path.exists(os.path.join(DATA_DIR, "no-auto-update")):
        threading.Thread(target=ytdlp_updater.update_in_background,
                         args=(DATA_DIR, yt_dlp.version.__version__), daemon=True).start()
    threading.Thread(target=api._send_pending, daemon=True).start()
    if os.environ.get("VD_SELFTEST"):
        threading.Thread(target=_selftest, args=(api, win, os.environ["VD_SELFTEST"]), daemon=True).start()
    webview.start(set_window_icon)
