"""
roblox_upload.py - upload audio ke Roblox lewat Open Cloud Assets API.
Hanya memakai library bawaan Python (tanpa pip install).

Cara pakai di app.py (kalau pakai Flask), tambahkan 2 baris ini setelah `app = Flask(...)`:

    import roblox_upload
    roblox_upload.register_flask(app)

API key dikirim dari browser lewat header X-Roblox-Key ke server lokalmu,
lalu diteruskan ke Roblox. Key tidak disimpan di server dan tidak dicetak ke log.
"""
import json
import uuid
import urllib.request
import urllib.error

BASE = "https://apis.roblox.com/assets/v1"
MAX_BYTES = 20 * 1024 * 1024  # batas aman untuk audio


class RobloxError(Exception):
    pass


def _friendly(code, body):
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


def _call(req):
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as e:
        raise RobloxError(_friendly(e.code, e.read().decode("utf-8", "ignore")))
    except urllib.error.URLError as e:
        raise RobloxError("Tidak bisa terhubung ke Roblox: %s" % e.reason)


def upload_audio(api_key, group_id, name, filename, data, content_type="audio/wav"):
    """Kirim audio ke grup. Mengembalikan operation id (asset ID baru ada setelah selesai diproses)."""
    if not api_key:
        raise RobloxError("API key kosong.")
    if not str(group_id).isdigit():
        raise RobloxError("ID grup harus angka.")
    if len(data) > MAX_BYTES:
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
         "Content-Type: %s\r\n\r\n" % (b, filename.replace('"', ""), content_type)).encode("utf-8"),
        data,
        ("\r\n--%s--\r\n" % b).encode("utf-8"),
    ]
    req = urllib.request.Request(
        BASE + "/assets",
        data=b"".join(parts),
        method="POST",
        headers={"x-api-key": api_key, "Content-Type": "multipart/form-data; boundary=" + b},
    )
    res = _call(req)
    path = res.get("path", "")  # contoh: "operations/abc123"
    if not path:
        raise RobloxError("Balasan Roblox tidak berisi operation id.")
    return path.split("/")[-1]


def get_status(api_key, op_id):
    """Cek hasil upload. Mengembalikan {done, assetId?, error?}."""
    if not op_id or not all(c.isalnum() or c in "-_" for c in op_id):
        raise RobloxError("Operation id tidak valid.")
    req = urllib.request.Request(BASE + "/operations/" + op_id, headers={"x-api-key": api_key})
    res = _call(req)
    if not res.get("done"):
        return {"done": False}
    if res.get("error"):
        return {"done": True, "error": res["error"].get("message", "Upload gagal (kemungkinan ditolak moderasi).")}
    asset_id = (res.get("response") or {}).get("assetId")
    if not asset_id:
        return {"done": True, "error": "Selesai, tapi asset ID tidak ditemukan di balasan."}
    return {"done": True, "assetId": str(asset_id)}


def register_flask(app):
    from flask import request, jsonify

    @app.post("/api/roblox/upload")
    def _rb_upload():
        f = request.files.get("file")
        if not f:
            return jsonify(error="File tidak ada."), 400
        try:
            op = upload_audio(
                request.headers.get("X-Roblox-Key", "").strip(),
                request.form.get("groupId", "").strip(),
                request.form.get("name", "").strip(),
                f.filename or "audio.wav",
                f.read(),
                f.mimetype or "audio/wav",
            )
            return jsonify(operationId=op, name=request.form.get("name", ""))
        except RobloxError as e:
            return jsonify(error=str(e)), 400

    @app.get("/api/roblox/status")
    def _rb_status():
        try:
            return jsonify(get_status(request.headers.get("X-Roblox-Key", "").strip(), request.args.get("op", "")))
        except RobloxError as e:
            return jsonify(error=str(e)), 400