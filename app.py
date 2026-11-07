"""Emote Audio Studio - server lokal.
Jalankan: python app.py   (atau klik dua kali start.bat di Windows)
Butuh: Python 3.9+. yt-dlp dipasang/diperbarui otomatis (juga lewat tombol di website).
ffmpeg opsional (untuk audio MP3 terpisah).
Upload ke Roblox memakai Open Cloud Assets API (hanya library bawaan Python).
"""
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import urllib.error
import urllib.request
import uuid
import webbrowser
from email import policy
from email.parser import BytesParser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, quote, urlparse

BASE = os.path.dirname(os.path.abspath(__file__))
MEDIA = os.path.join(BASE, "downloads")
IS_CLOUD = bool(os.environ.get("PORT") or os.environ.get("EAS_CLOUD") or os.environ.get("SPACE_ID") or os.environ.get("RAILWAY_ENVIRONMENT"))
PORT = int(os.environ.get("PORT", 8765))
HOST = os.environ.get("EAS_HOST", "0.0.0.0" if IS_CLOUD else "127.0.0.1")  # "0.0.0.0" = cloud/LAN, "127.0.0.1" = lokal
LAN = re.compile(r"^(127\.|10\.|192\.168\.|169\.254\.|172\.(1[6-9]|2\d|3[01])\.|100\.(6[4-9]|[7-9]\d|1[01]\d|12[0-7])\.|::1$)")
FFMPEG = shutil.which("ffmpeg")
ALLOWED = ("tiktok.com", "douyin.com", "youtube.com", "youtu.be")
YT_HOSTS = ("youtube.com", "youtu.be")
YT_MAX_SEC = 900  # YouTube: video lebih dari 15 menit atau live ditolak (hanya audio yang diambil)
BROWSERS = ("chrome", "edge", "firefox", "brave")
ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]|\[[0-9;]+m")
ENV = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
FLAGS = 0x08000000 if os.name == "nt" else 0  # tanpa jendela konsol tambahan
UPDATE_LOCK = threading.Lock()

RB_BASE = "https://apis.roblox.com/assets/v1"
RB_MAX_BYTES = 20 * 1024 * 1024  # batas aman untuk audio

# Cloudflare Turnstile Configuration (Default testing key / Cloud ENV)
TURNSTILE_SECRET = os.environ.get("CLOUDFLARE_TURNSTILE_SECRET_KEY", "1x0000000000000000000000000000000AA")
TURNSTILE_ENFORCE = os.environ.get("EAS_ENFORCE_TURNSTILE", "0") == "1"


# ---------- turnstile verification ----------
def verify_turnstile(token, ip=""):
    """Verifikasi token Cloudflare Turnstile ke server Cloudflare."""
    if not token:
        return False, "Token Turnstile kosong."
    try:
        data = urllib.parse.urlencode({
            "secret": TURNSTILE_SECRET,
            "response": token,
            "remoteip": ip or ""
        }).encode("utf-8")
        req = urllib.request.Request(
            "https://challenges.cloudflare.com/turnstile/v0/siteverify",
            data=data,
            method="POST",
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            res = json.loads(r.read().decode("utf-8") or "{}")
        if res.get("success"):
            return True, "Valid"
        errs = res.get("error-codes", ["Verifikasi Turnstile gagal."])
        return False, ", ".join(errs) if isinstance(errs, list) else str(errs)
    except Exception as e:
        return False, "Gagal menghubungi Cloudflare: %s" % str(e)


# ---------- util ----------
def clean(text):
    return ANSI.sub("", text or "").strip()


def host_in(url, names):
    host = (urlparse(url).hostname or "").lower()
    return any(host == d or host.endswith("." + d) for d in names)


def allowed(url):
    return urlparse(url).scheme in ("http", "https") and host_in(url, ALLOWED)


def is_youtube(url):
    return host_in(url, YT_HOSTS)


def youtube_video_ok(url):
    """Hanya link ke SATU video (watch?v=, youtu.be/ID, /shorts/, /live/, /embed/). Playlist dan channel ditolak."""
    p = urlparse(url)
    if (p.hostname or "").lower() == "youtu.be":
        return bool(p.path.strip("/"))
    if p.path == "/watch":
        return bool(parse_qs(p.query).get("v", [""])[0])
    parts = p.path.split("/")
    return len(parts) >= 3 and parts[1] in ("shorts", "live", "embed") and bool(parts[2])


def clean_url(url):
    """TikTok: buang ?is_from_webapp=... kecuali link pendek (vm./vt.). YouTube: sisakan hanya id video."""
    p = urlparse(url)
    host = (p.hostname or "").lower()
    if host.startswith(("vm.", "vt.")):
        return url
    if is_youtube(url):
        if host == "youtu.be":
            return "https://youtu.be" + p.path
        v = parse_qs(p.query).get("v", [""])[0]
        return "https://www.youtube.com" + p.path + ("?v=" + quote(v, safe="") if v else "")
    return f"{p.scheme}://{p.netloc}{p.path}"


def run(cmd, timeout):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=timeout, env=ENV, creationflags=FLAGS)
    except subprocess.TimeoutExpired:
        raise RuntimeError("Waktu habis. Periksa koneksi internet lalu coba lagi.")


def ytdlp(args, timeout=240):
    return run([sys.executable, "-m", "yt_dlp", "--no-colors"] + args, timeout)


def last_error(text):
    lines = [l for l in clean(text).splitlines() if l.strip()]
    errs = [l for l in lines if "ERROR" in l]
    msg = (errs[-1] if errs else (lines[-1] if lines else "Gagal mengunduh"))
    return msg.replace("ERROR: ", "")[:300]


# ---------- versi & update yt-dlp ----------
def vkey(v):
    return tuple(int(x) for x in re.findall(r"\d+", (v or "").replace(".dev0", "")))


def current_version():
    try:
        r = ytdlp(["--version"], 30)
        v = clean(r.stdout)
        return v if r.returncode == 0 and v else None
    except Exception:
        return None


def latest_version():
    """Versi terbaru di PyPI (termasuk nightly/pre-release)."""
    try:
        with urllib.request.urlopen("https://pypi.org/pypi/yt-dlp/json", timeout=10) as r:
            rel = json.load(r)["releases"]
        best = None
        for ver, files in rel.items():
            for f in files:
                if f.get("yanked"):
                    continue
                t = f.get("upload_time_iso_8601") or f.get("upload_time") or ""
                if best is None or t > best[0]:
                    best = (t, ver)
        return best[1].replace(".dev0", "") if best else None
    except Exception:
        return None


def version_info():
    cur, lat = current_version(), latest_version()
    outdated = (vkey(lat) > vkey(cur)) if (cur and lat) else None
    return {"current": cur, "latest": lat, "outdated": outdated, "ffmpeg": bool(FFMPEG)}


def pip_install_ytdlp():
    last = None
    for spec in ("yt-dlp[default,curl-cffi]", "yt-dlp[default]", "yt-dlp"):
        r = run([sys.executable, "-m", "pip", "install", "-U", "--pre", "--disable-pip-version-check", spec], 300)
        if r.returncode == 0:
            return
        last = r
    tail = " | ".join([l for l in clean(last.stderr or last.stdout).splitlines() if l.strip()][-3:])
    raise RuntimeError("pip gagal: " + tail[:300])


def do_update():
    with UPDATE_LOCK:
        cur, lat = current_version(), latest_version()
        if cur and lat and vkey(lat) <= vkey(cur):
            return {"updated": False, "current": cur, "latest": lat}
        pip_install_ytdlp()
        new = current_version()
        if not new:
            raise RuntimeError("yt-dlp tidak bisa dijalankan setelah update")
        return {"updated": new != cur, "current": new, "latest": lat or new}


# ---------- unduh ----------
def grab(url, browser=""):
    """Unduh video TikTok (atau audio saja dari YouTube), lalu ekstrak MP3 kalau ffmpeg tersedia."""
    url = clean_url(url)
    yt = is_youtube(url)
    uid = uuid.uuid4().hex[:10]
    if yt:  # audio saja (kecil), tolak live dan video terlalu panjang
        fmt = ["-f", "bestaudio[ext=m4a]/bestaudio/best", "--match-filter", "!is_live & duration<=%d" % YT_MAX_SEC]
    else:
        fmt = ["-f", "mp4/best", "--merge-output-format", "mp4"]
    base = [
        "--no-playlist", "--no-warnings", "--no-progress",
        "--retries", "3", "--socket-timeout", "20",
    ] + fmt + [
        "-o", os.path.join(MEDIA, uid + ".%(ext)s"),
        "--dump-single-json", "--no-simulate",
    ]
    if browser in BROWSERS:
        base += ["--cookies-from-browser", browser]

    r = None
    for extra in ([[]] if yt else [["--impersonate", "chrome"], []]):  # TikTok: coba menyamar sebagai browser dulu
        r = ytdlp(base + extra + [url])
        if r.returncode == 0:
            break
        if "mpersonat" not in clean(r.stderr):
            break
    if r.returncode != 0:
        raise RuntimeError(last_error(r.stderr or r.stdout))

    info = {}
    for line in reversed(clean(r.stdout).splitlines()):
        if line.startswith("{"):
            try:
                info = json.loads(line)
                break
            except ValueError:
                pass

    files = [f for f in os.listdir(MEDIA)
             if f.startswith(uid + ".") and not f.endswith((".part", ".ytdl", ".json", ".mp3"))]
    if not files:
        if yt:
            raise RuntimeError("Tidak ada file yang terunduh. Kemungkinan video lebih dari %d menit atau sedang live." % (YT_MAX_SEC // 60))
        raise RuntimeError("File video tidak ditemukan setelah diunduh")
    files.sort(key=lambda f: not f.endswith(".mp4"))
    video = files[0]
    audio = video
    if FFMPEG:
        try:
            out = uid + ".mp3"
            subprocess.run(
                [FFMPEG, "-y", "-i", os.path.join(MEDIA, video), "-vn",
                 "-acodec", "libmp3lame", "-q:a", "2", os.path.join(MEDIA, out)],
                check=True, capture_output=True, creationflags=FLAGS,
            )
            audio = out
        except Exception:
            audio = video
    return {
        "title": info.get("title") or info.get("description") or ("Video YouTube" if yt else "Video TikTok"),
        "by": info.get("uploader") or info.get("channel") or info.get("creator") or "",
        "kind": "youtube" if yt else "tiktok",
        "cover": info.get("thumbnail") or "",
        "vid": "/downloads/" + video,
        "aud": "/downloads/" + audio,
    }


# ---------- upload ke Roblox (Open Cloud Assets API) ----------
class RobloxError(Exception):
    pass


def rb_friendly(code, body):
    try:
        msg = json.loads(body).get("message") or body
    except Exception:
        msg = body
    if code == 401:
        return "API key ditolak (401). Cek apakah key-nya benar dan belum kedaluwarsa."
    if code == 403:
        return ("Akses ditolak (403). Pastikan API key punya permission asset:read dan asset:write, "
                "dan key tersebut diizinkan untuk grup ini. Detail: " + str(msg)[:200])
    if code == 429:
        return "Terlalu banyak upload dalam waktu singkat (429). Tunggu sebentar lalu coba lagi."
    return "Roblox menolak (%s): %s" % (code, str(msg)[:300])


def rb_call(req):
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            return json.loads(r.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as e:
        raise RobloxError(rb_friendly(e.code, e.read().decode("utf-8", "ignore")))
    except urllib.error.URLError as e:
        raise RobloxError("Tidak bisa terhubung ke Roblox: %s" % e.reason)


def rb_upload(api_key, group_id, name, filename, data, content_type="audio/wav"):
    """Kirim audio ke grup. Mengembalikan operation id (asset ID baru ada setelah selesai diproses)."""
    if not api_key:
        raise RobloxError("API key kosong.")
    if not str(group_id).isdigit():
        raise RobloxError("ID grup harus angka.")
    if len(data) > RB_MAX_BYTES:
        raise RobloxError("File terlalu besar (maks 20 MB). Potong audionya dulu.")
    meta = {
        "assetType": "Audio",
        "displayName": (name or filename)[:50],
        "description": "Uploaded via Emote Audio Studio",
        "creationContext": {"creator": {"groupId": str(group_id)}},
    }
    b = uuid.uuid4().hex
    parts = [
        ("--%s\r\nContent-Disposition: form-data; name=\"request\"\r\n"
         "Content-Type: application/json\r\n\r\n%s\r\n" % (b, json.dumps(meta))).encode("utf-8"),
        ("--%s\r\nContent-Disposition: form-data; name=\"fileContent\"; filename=\"%s\"\r\n"
         "Content-Type: %s\r\n\r\n" % (b, filename.replace('"', "").replace("\r", "").replace("\n", ""), content_type)).encode("utf-8"),
        data,
        ("\r\n--%s--\r\n" % b).encode("utf-8"),
    ]
    req = urllib.request.Request(
        RB_BASE + "/assets", data=b"".join(parts), method="POST",
        headers={"x-api-key": api_key, "Content-Type": "multipart/form-data; boundary=" + b},
    )
    path = rb_call(req).get("path", "")  # contoh: "operations/abc123"
    if not path:
        raise RobloxError("Balasan Roblox tidak berisi operation id.")
    return path.split("/")[-1]


def rb_status(api_key, op_id):
    """Cek hasil upload. Mengembalikan {done, assetId?, error?}."""
    if not api_key:
        raise RobloxError("API key kosong.")
    if not op_id or not all(c.isalnum() or c in "-_" for c in op_id):
        raise RobloxError("Operation id tidak valid.")
    res = rb_call(urllib.request.Request(RB_BASE + "/operations/" + op_id, headers={"x-api-key": api_key}))
    if not res.get("done"):
        return {"done": False}
    if res.get("error"):
        return {"done": True, "error": res["error"].get("message", "Upload gagal (kemungkinan ditolak moderasi).")}
    asset_id = (res.get("response") or {}).get("assetId")
    if not asset_id:
        return {"done": True, "error": "Selesai, tapi asset ID tidak ditemukan di balasan."}
    return {"done": True, "assetId": str(asset_id)}


def parse_multipart(ctype, body):
    """Urai body multipart/form-data -> (fields, files). Tanpa modul cgi (sudah dihapus di Python 3.13)."""
    msg = BytesParser(policy=policy.HTTP).parsebytes(
        b"Content-Type: " + ctype.encode("latin-1", "replace") + b"\r\nMIME-Version: 1.0\r\n\r\n" + body)
    fields, files = {}, {}
    if not msg.is_multipart():
        return fields, files
    for part in msg.iter_parts():
        name = part.get_param("name", header="content-disposition")
        if not name:
            continue
        payload = part.get_payload(decode=True) or b""
        fn = part.get_filename()
        if fn is not None:
            files[name] = (fn, payload, part.get_content_type())
        else:
            fields[name] = payload.decode("utf-8", "replace")
    return fields, files


# ---------- server ----------
class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=BASE, **k)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        # CORS Headers untuk deployment cloud (Render / Railway / HuggingFace)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Roblox-Key, CF-Turnstile-Response, Authorization")
        super().end_headers()

    def do_OPTIONS(self):
        """Preflight CORS response"""
        self.send_response(204)
        self.end_headers()

    def send_json(self, code, data):
        body = json.dumps(data).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def lan_ok(self):
        # Di cloud publik, izin akses terbuka (dilindungi oleh Cloudflare Turnstile & API Keys)
        if IS_CLOUD:
            return True
        if LAN.match(self.client_address[0]):
            return True
        self.send_json(403, {"error": "Hanya jaringan lokal"})
        return False

    def do_GET(self):
        if not self.lan_ok():
            return
        u = urlparse(self.path)
        if u.path in ("/api/health", "/api/ping"):
            return self.send_json(200, {
                "ok": True,
                "mode": "cloud" if IS_CLOUD else "local",
                "ytdlp": current_version(),
                "ffmpeg": bool(FFMPEG),
                "turnstile": bool(TURNSTILE_SECRET)
            })
        if u.path == "/api/info":
            q = parse_qs(u.query)
            url = q.get("url", [""])[0].strip()
            browser = q.get("cookies", [""])[0].strip().lower()
            if not allowed(url):
                return self.send_json(400, {"error": "Link harus dari tiktok.com, douyin.com, atau youtube.com"})
            if is_youtube(url) and not youtube_video_ok(url):
                return self.send_json(400, {"error": "Link YouTube harus ke satu video (bukan playlist atau channel)."})
            try:
                return self.send_json(200, grab(url, browser))
            except Exception as e:
                return self.send_json(500, {"error": clean(str(e))[:300] or "Gagal mengunduh"})
        if u.path == "/api/version":
            return self.send_json(200, version_info())
        if u.path == "/api/roblox/ping":
            return self.send_json(200, {"ok": True})
        if u.path == "/api/roblox/status":
            try:
                key = (self.headers.get("X-Roblox-Key") or "").strip()
                return self.send_json(200, rb_status(key, parse_qs(u.query).get("op", [""])[0].strip()))
            except RobloxError as e:
                return self.send_json(400, {"error": str(e)})
            except Exception as e:
                return self.send_json(500, {"error": clean(str(e))[:300] or "Gagal cek status"})
        super().do_GET()

    def drain(self):
        """Baca habis isi permintaan sebelum membalas error, supaya browser tidak melihat koneksi terputus."""
        try:
            left = int(self.headers.get("Content-Length") or 0)
            if left > 30 * 1024 * 1024:
                self.close_connection = True
                return
            while left > 0:
                chunk = self.rfile.read(min(65536, left))
                if not chunk:
                    break
                left -= len(chunk)
        except Exception:
            self.close_connection = True

    def do_POST(self):
        if not self.lan_ok():
            return
        u = urlparse(self.path)
        origin = self.headers.get("Origin")
        if not IS_CLOUD and origin and origin != "http://" + (self.headers.get("Host") or ""):
            self.drain()
            return self.send_json(403, {"error": "Asal permintaan tidak diizinkan"})
        if u.path == "/api/turnstile/verify":
            try:
                n = int(self.headers.get("Content-Length") or 0)
                body = self.rfile.read(n).decode("utf-8") if n > 0 else "{}"
                data = json.loads(body)
                token = data.get("token") or self.headers.get("CF-Turnstile-Response", "")
                ok, msg = verify_turnstile(token, self.client_address[0])
                return self.send_json(200 if ok else 400, {"success": ok, "message": msg})
            except Exception as e:
                return self.send_json(500, {"error": "Verifikasi gagal: " + str(e)})
        if u.path == "/api/update":
            try:
                return self.send_json(200, do_update())
            except Exception as e:
                return self.send_json(500, {"error": clean(str(e))[:300] or "Update gagal"})
        if u.path == "/api/roblox/upload":
            try:
                n = int(self.headers.get("Content-Length") or 0)
                if n <= 0 or n > RB_MAX_BYTES + 1024 * 1024:
                    self.drain()
                    raise RobloxError("File kosong atau lebih dari 20 MB.")
                fields, files = parse_multipart(self.headers.get("Content-Type", ""), self.rfile.read(n))

                # Verifikasi Turnstile jika diwajibkan atau dikirimkan
                cf_token = fields.get("turnstile_token") or self.headers.get("CF-Turnstile-Response")
                if TURNSTILE_ENFORCE:
                    ok, msg = verify_turnstile(cf_token, self.client_address[0])
                    if not ok:
                        raise RobloxError("Verifikasi Cloudflare Turnstile gagal: " + msg)

                f = files.get("file")
                if not f:
                    raise RobloxError("File audio tidak ada di permintaan.")
                key = (self.headers.get("X-Roblox-Key") or "").strip()
                name = (fields.get("name") or "").strip()
                op = rb_upload(key, (fields.get("groupId") or "").strip(), name, f[0] or "audio.wav", f[1], f[2] or "audio/wav")
                return self.send_json(200, {"operationId": op, "name": name})
            except RobloxError as e:
                return self.send_json(400, {"error": str(e)})
            except Exception as e:
                return self.send_json(500, {"error": clean(str(e))[:300] or "Upload gagal"})
        self.drain()
        self.send_json(404, {"error": "Tidak ditemukan"})

    def log_message(self, fmt, *args):
        if "/api/" in self.path:
            print(self.client_address[0], fmt % args, flush=True)


def main():
    ver = current_version()
    if not ver:
        print("yt-dlp belum terpasang, memasang...")
        try:
            pip_install_ytdlp()
            ver = current_version()
        except Exception as e:
            sys.exit("Gagal memasang yt-dlp: " + str(e))
    shutil.rmtree(MEDIA, ignore_errors=True)
    os.makedirs(MEDIA, exist_ok=True)
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    url = f"http://{'127.0.0.1' if HOST in ('0.0.0.0', '127.0.0.1') else HOST}:{PORT}/"
    print("=" * 60)
    print("Emote Audio Studio - " + ("CLOUD SERVER (24 Jam)" if IS_CLOUD else "LOKAL"))
    print("Berjalan di:", url, f"(Host: {HOST}, Port: {PORT})")
    print("yt-dlp versi:", ver)
    print("ffmpeg:", "terdeteksi (audio MP3 terpisah)" if FFMPEG else "tidak ada (audio diambil dari MP4)")
    print("Cloudflare Turnstile:", "Aktif" if TURNSTILE_SECRET else "Nonaktif", "(Enforce:" + str(TURNSTILE_ENFORCE) + ")")
    print("=" * 60)
    print("Tekan Ctrl+C untuk berhenti.")
    if not IS_CLOUD and HOST == "127.0.0.1":
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        shutil.rmtree(MEDIA, ignore_errors=True)


if __name__ == "__main__":
    main()