<p align="center"><img src="icon-128.png" width="96" alt="Video Downloader icon"></p>

<h1 align="center">Video Downloader</h1>

<p align="center">YouTube up to 4K with sound · TikTok without watermark · 16 languages<br>
YouTube bis 4K mit Ton · TikTok ohne Wasserzeichen · 16 Sprachen</p>

---

## English

A small Windows app with a dark, modern window. Paste a link, pick an option, done.

**YouTube**
- 4K (Ultra HD), 2K (1440p), 1080p, 720p as MP4 **with sound**
- MP3 (audio only, 320 kbps)
- Preview with thumbnail, channel, length and available quality

**TikTok**
- **Download Video** – the highest quality version **without the TikTok watermark** (usually 1080p, converted to H.264 so every Windows PC can play it)
- **Download Thumbnail** – the cover image in full size (e.g. 1080×1920 JPG)
- **Download Audio** – the sound of the video as MP3

**More**
- 16 languages, chosen automatically from your Windows language (globe menu at the top right)
- Takes a copied link straight from the clipboard and switches between YouTube and TikTok on its own
- Start animation with sound
- Keeps itself working: checks once a day for a new [yt-dlp](https://github.com/yt-dlp/yt-dlp) version (can be turned off, see *Privacy*)

### Install
1. Download `Video Downloader Setup.exe` from [Releases](../../releases).
2. Run it. No admin rights needed.
3. Windows may show *"Windows protected your PC"* because the app is new and not signed yet: click **More info → Run anyway**.

Requirements: Windows 10 (1809) or Windows 11, 64-bit.

> **Only download content you are allowed to** (for example for private use). The terms of service of YouTube and TikTok still apply.

---

## Deutsch

Eine kleine Windows-App mit dunklem, modernem Fenster. Link einfügen, auswählen, fertig.

- **YouTube:** 4K, 2K, 1080p, 720p als MP4 **mit Ton**, oder MP3
- **TikTok:** Video **ohne Wasserzeichen**, Thumbnail in voller Größe, Audio als MP3
- 16 Sprachen, automatisch nach der Windows-Sprache (Globus oben rechts)
- Aktualisiert yt-dlp automatisch (abschaltbar)

**Installieren:** `Video Downloader Setup.exe` unter [Releases](../../releases) laden und starten. Kommt die Meldung *„Der Computer wurde durch Windows geschützt“*: **Weitere Informationen → Trotzdem ausführen**.

> **Lade nur Inhalte herunter, bei denen du das darfst** (z. B. für den privaten Gebrauch). Die Nutzungsbedingungen von YouTube und TikTok gelten weiterhin.

---

## Privacy / Datenschutz

This program will not transfer any information to other networked systems unless specifically requested by the user or the person installing or operating it.

In detail, the app only connects to:
1. **YouTube / TikTok** – only for links you paste yourself.
2. **GitHub** – at most once a day to check for a new yt-dlp version, without any personal data. You can turn this off during setup, or later by creating an empty file named `no-auto-update` in `%APPDATA%\Video Downloader`.
3. **Google Forms** – only when you rate the app and click *Send*: the stars, your optional comment, the app version and language are sent anonymously to the developer (no name, no email).

No ads, no analytics, no tracking. The full text is shown during setup: [packaging/privacy.txt](packaging/privacy.txt).

## Code signing policy

Release builds are created automatically by [GitHub Actions](.github/workflows/build.yml) from the source code in this repository. Every release is approved by hand before it is published.

Team roles:
- **Author / Committer:** [@Colin123p](https://github.com/Colin123p)
- **Reviewer:** [@Colin123p](https://github.com/Colin123p) – every change from outside contributors (pull requests) is reviewed before merging
- **Approver (releases):** [@Colin123p](https://github.com/Colin123p)

All team members use multi-factor authentication for GitHub.

## Build it yourself

Needs Python 3.12, [Inno Setup 6](https://jrsoftware.org/isinfo.php) and an FFmpeg *essentials* build.

```powershell
python -m pip install -r requirements.txt
powershell -ExecutionPolicy Bypass -File packaging\build.ps1
```

The setup ends up in `release\Video Downloader Setup.exe`. Run the app without building: `pythonw "Video Downloader.pyw"`.

## Built with

[yt-dlp](https://github.com/yt-dlp/yt-dlp) · [FFmpeg](https://ffmpeg.org) · [pywebview](https://github.com/r0x0r/pywebview) · [curl_cffi](https://github.com/lexiforest/curl_cffi) · [Pillow](https://python-pillow.org) · [PyInstaller](https://pyinstaller.org) · [Inno Setup](https://jrsoftware.org/isinfo.php)

## License

[MIT](LICENSE) for the code in this repository. The Windows setup also contains third-party software under its own licenses (FFmpeg: GPLv3). See the *Lizenzen* folder in the installed app.
