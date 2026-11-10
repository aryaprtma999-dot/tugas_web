import csv
import io
import os
import secrets
import sqlite3
import threading
from datetime import date, datetime, time, timedelta
from functools import wraps
from xml.sax.saxutils import escape as xml_escape

import qrcode
from flask import (
    Blueprint,
    Flask,
    abort,
    current_app,
    flash,
    g,
    jsonify,
    redirect,
    render_template,
    request,
    Response,
    send_file,
    send_from_directory,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DEFAULT_DB = os.path.join(BASE_DIR, "instance", "idb_rooms.db")
DEFAULT_UPLOADS = os.path.join(BASE_DIR, "uploads")

ROLES = ("mahasiswa", "dosen", "sarpras", "superadmin")
ACTIVE_STATUSES = ("processing", "confirmed")
ALLOWED_EXTENSIONS = {"pdf", "png", "jpg", "jpeg", "doc", "docx"}
MAX_DOC_BYTES = 8 * 1024 * 1024

ROLE_LABELS = {
    "mahasiswa": "Mahasiswa",
    "dosen": "Dosen / Staf",
    "sarpras": "Petugas Sarpras",
    "superadmin": "Super Admin",
}

STATUS_META = {
    "confirmed": {"label": "Terkonfirmasi", "tone": "success", "icon": "check"},
    "processing": {"label": "Menunggu Verifikasi", "tone": "warning", "icon": "clock"},
    "failed": {"label": "Gagal / Konflik", "tone": "danger", "icon": "x"},
    "cancelled": {"label": "Dibatalkan", "tone": "muted", "icon": "minus"},
}

BULAN = {
    1: "Januari", 2: "Februari", 3: "Maret", 4: "April", 5: "Mei", 6: "Juni",
    7: "Juli", 8: "Agustus", 9: "September", 10: "Oktober", 11: "November", 12: "Desember",
}
HARI = {0: "Senin", 1: "Selasa", 2: "Rabu", 3: "Kamis", 4: "Jumat", 5: "Sabtu", 6: "Minggu"}
ROMAWI = {1: "I", 2: "II", 3: "III", 4: "IV", 5: "V", 6: "VI",
          7: "VII", 8: "VIII", 9: "IX", 10: "X", 11: "XI", 12: "XII"}

SEED_PASSWORD = "idb1"

ROOM_PHOTOS = {
    "A.1.1": "lab-fashion-design-mode-idb.jpg",
    "A.1.2": "ruang-kelas-idbbali.jpg",
    "A.1.3": "lab-komputer-baru-idb-1.jpg",
    "A.1.4": "studio-foto-idb-new.jpg",
    "B.1.1": "lab-imac-terbaru-idb-1.jpg",
    "B.1.2": "ruang-meeting-idb.jpg",
    "B.1.3": "studio-maket-idb.jpg",
    "B.1.4": "lab-desain-mode-idb.jpg",
    "A.2.1": "lab-komputer-baru-idb-1.jpg",
    "A.2.2": "ruang-lab-stib.jpg",
    "A.2.3": "ruang-kelas-idbbali.jpg",
    "A.2.4": "lobby-idb-bali.jpg",
    "B.2.1": "ruang-kelas-idbbali.jpg",
    "B.2.2": "462893-Small.jpg",
    "Kantin": "cafe-kantin-idb.jpg",
    "Musholla": "lobby-idb-bali.jpg",
    "Perpustakaan": "new-perpustakaan-idb.jpg",
    "Ruang Asistensi": "ruang-asistensi-idb.jpg",
    "Aula": "aula-idb-bali.jpg",
    "C.1.1": "ruang-kelas-idbbali.jpg",
    "C.1.2": "lab-komputer-baru-idb-1.jpg",
    "Ruang Dosen & Admin": "ruang-dosen-idb.jpg",
    "C.2.1": "ruang-kelas-idbbali.jpg",
    "C.2.2": "ruang-kelas-idbbali.jpg",
    "C.2.3": "studio-gambar-idb-1-scaled.jpg",
    "C.3.1": "studio-gambar-idb-1-scaled.jpg",
    "C.3.2": "studio-maket-idb.jpg",
    "C.3.3": "studio-produksi-idb.jpg",
}

CATEGORY_PHOTOS = {
    "Ruang Teori": "ruang-kelas-idbbali.jpg",
    "Lab Komputer": "lab-komputer-baru-idb-1.jpg",
    "Lab Multimedia": "lab-imac-terbaru-idb-1.jpg",
    "Lab Fashion": "lab-desain-mode-idb.jpg",
    "Studio": "studio-gambar-idb-1-scaled.jpg",
    "Studio Foto": "studio-foto-idb-new.jpg",
    "Ruang Rapat": "ruang-meeting-idb.jpg",
    "Aula": "aula-idb-bali.jpg",
    "Literasi": "new-perpustakaan-idb.jpg",
    "Asistensi": "ruang-asistensi-idb.jpg",
    "Area Publik": "cafe-kantin-idb.jpg",
    "Fasilitas Ibadah": "lobby-idb-bali.jpg",
    "Administrasi": "ruang-dosen-idb.jpg",
    "Kesehatan": "lobby-idb-bali.jpg",
}

SEED_ROOMS = [
    ("A.1.1", "Studio Pola", "Gedung A", 1, 30, "Studio", "Studio praktikum pola. Diperlukan izin dosen pembimbing.", 1, 0, 0),
    ("A.1.2", "R Lecture", "Gedung A", 1, 40, "Ruang Teori", "Ruang teori perkuliahan.", 0, 0, 0),
    ("A.1.3", "Lab Komputer", "Gedung A", 1, 36, "Lab Komputer", "Lab software dengan beban listrik tinggi.", 1, 0, 0),
    ("A.1.4", "Studio Foto", "Gedung A", 1, 12, "Studio Foto", "Studio fotografi & lighting.", 1, 0, 0),
    ("B.1.1", "Lab iMac", "Gedung A", 1, 30, "Lab Multimedia", "Lab multimedia & desain grafis.", 1, 0, 0),
    ("B.1.2", "R Meeting Inbis", "Gedung A", 1, 16, "Ruang Rapat", "Ruang rapat Inkubator Bisnis.", 0, 0, 0),
    ("B.1.3", "Studio Karya", "Gedung A", 1, 25, "Studio", "Studio karya multiguna.", 0, 0, 0),
    ("B.1.4", "Lab Fashion", "Gedung A", 1, 24, "Lab Fashion", "Lab perancangan busana.", 1, 0, 0),
    ("A.2.1", "Lab Komputer 2A", "Gedung A", 2, 36, "Lab Komputer", "Lab software / komputer umum.", 1, 0, 0),
    ("A.2.2", "Lab Komputer 2B", "Gedung A", 2, 36, "Lab Komputer", "Lab software / komputer umum.", 1, 0, 0),
    ("A.2.3", "R Lecture 2A", "Gedung A", 2, 40, "Ruang Teori", "Ruang teori perkuliahan.", 0, 0, 0),
    ("A.2.4", "UKS", "Gedung A", 2, 4, "Kesehatan", "Unit Kesehatan Kampus, hanya untuk kondisi darurat.", 0, 0, 1),
    ("B.2.1", "R Lecture 2B", "Gedung A", 2, 40, "Ruang Teori", "Ruang teori perkuliahan.", 0, 0, 0),
    ("B.2.2", "Ruang Magister", "Gedung A", 2, 24, "Ruang Teori", "Ruang kuliah pascasarjana.", 0, 0, 0),
    ("Kantin", "Kantin", "Gedung A", 2, 100, "Area Publik", "Area publik untuk kegiatan terbuka.", 0, 0, 0),
    ("Musholla", "Musholla", "Gedung A", 2, 30, "Fasilitas Ibadah", "Fasilitas ibadah dengan akses bebas.", 0, 0, 0),
    ("Perpustakaan", "Perpustakaan", "Gedung A", 3, 60, "Literasi", "Area literasi & hening.", 0, 0, 0),
    ("Ruang Asistensi", "Ruang Asistensi", "Gedung A", 3, 12, "Asistensi", "Konsultasi dosen & mahasiswa.", 0, 0, 0),
    ("Aula", "Aula Utama", "Gedung A", 3, 300, "Aula", "Acara besar. Memerlukan dokumen dan approval Sarpras.", 1, 1, 0),
    ("C.1.1", "R Lecture Barito", "Gedung A Barito", 1, 40, "Ruang Teori", "Ruang teori kampus Barito.", 0, 0, 0),
    ("C.1.2", "Lab Komputer Barito", "Gedung A Barito", 1, 30, "Lab Komputer", "Lab komputer kampus Barito.", 1, 0, 0),
    ("Ruang Dosen & Admin", "Ruang Dosen & Administrasi", "Gedung A Barito", 1, 20, "Administrasi", "Area terbatas, dikecualikan dari peminjaman rutin mahasiswa.", 0, 0, 1),
    ("C.2.1", "R Lecture 2C", "Gedung A Barito", 2, 40, "Ruang Teori", "Ruang teori kampus Barito.", 0, 0, 0),
    ("C.2.2", "R Lecture 2D", "Gedung A Barito", 2, 40, "Ruang Teori", "Ruang teori kampus Barito.", 0, 0, 0),
    ("C.2.3", "Studio Praktikum Desain", "Gedung A Barito", 2, 30, "Studio", "Studio praktikum desain.", 1, 0, 0),
    ("C.3.1", "Studio Desain 3A", "Gedung A Barito", 3, 25, "Studio", "Studio desain / kerja kelompok.", 0, 0, 0),
    ("C.3.2", "Studio Desain 3B", "Gedung A Barito", 3, 25, "Studio", "Studio desain / kerja kelompok.", 0, 0, 0),
    ("C.3.3", "Studio Desain 3C", "Gedung A Barito", 3, 25, "Studio", "Studio desain / kerja kelompok.", 0, 0, 0),
]

SEED_USERS = [
    ("Rani Prameswari", "mahasiswa@idb.ac.id", "mahasiswa", "22101001", "Desain Komunikasi Visual"),
    ("Dedi Kurniawan", "sarpras@idb.ac.id", "sarpras", "SAR-001", "Sarana & Prasarana"),
    ("Dr. Ayu Pradnyani", "dosen@idb.ac.id", "dosen", "5101018701250001", "Desain Interior"),
    ("Super Admin IDB", "superadmin@idb.ac.id", "superadmin", "ADM-000", "Administrator Sistem"),
]

bp = Blueprint("main", __name__)
_write_lock = threading.Lock()


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"], timeout=30)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
        g.db.execute("PRAGMA busy_timeout = 30000")
    return g.db


def close_db(_exc=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db(app):
    os.makedirs(os.path.dirname(app.config["DATABASE"]), exist_ok=True)
    os.makedirs(app.config["UPLOAD_DIR"], exist_ok=True)
    schema_path = os.path.join(BASE_DIR, "schema.sql")
    with open(schema_path, "r", encoding="utf-8") as handle:
        schema = handle.read()

    db = sqlite3.connect(app.config["DATABASE"])
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode = WAL")
    db.executescript(schema)

    user_columns = {row["name"] for row in db.execute("PRAGMA table_info(users)").fetchall()}
    if "prodi" not in user_columns:
        db.execute("ALTER TABLE users ADD COLUMN prodi TEXT")

    if db.execute("SELECT COUNT(*) AS n FROM rooms").fetchone()["n"] == 0:
        db.executemany(
            """INSERT INTO rooms
               (kode, nama, gedung, lantai, kapasitas, kategori, deskripsi,
                butuh_dokumen, butuh_approval, terbatas)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            SEED_ROOMS,
        )

    if db.execute("SELECT COUNT(*) AS n FROM users").fetchone()["n"] == 0:
        for nama, email, role, nim, prodi in SEED_USERS:
            db.execute(
                """INSERT INTO users (nama, email, password_hash, role, nim_nip, prodi)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (nama, email, generate_password_hash(SEED_PASSWORD, method="pbkdf2:sha256"),
                 role, nim, prodi),
            )
    else:
        for nama, email, role, nim, prodi in SEED_USERS:
            row = db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
            if not row:
                continue
            if check_password_hash(row["password_hash"], "demo123"):
                db.execute(
                    "UPDATE users SET password_hash = ? WHERE id = ?",
                    (generate_password_hash(SEED_PASSWORD, method="pbkdf2:sha256"), row["id"]),
                )
            if not row["prodi"]:
                db.execute("UPDATE users SET prodi = ? WHERE id = ?", (prodi, row["id"]))
    db.commit()
    db.close()


def log_audit(db, reservation_id, actor_id, action, detail=None):
    db.execute(
        "INSERT INTO audit_logs (reservation_id, actor_id, action, detail) VALUES (?, ?, ?, ?)",
        (reservation_id, actor_id, action, detail),
    )


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------
def current_user():
    if "user" not in g:
        g.user = None
        user_id = session.get("user_id")
        if user_id:
            g.user = get_db().execute(
                "SELECT * FROM users WHERE id = ?", (user_id,)
            ).fetchone()
    return g.user


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if current_user() is None:
            flash("Silakan masuk terlebih dahulu.", "warning")
            return redirect(url_for("main.login", next=request.path))
        return view(*args, **kwargs)

    return wrapped


def roles_required(*roles):
    def decorator(view):
        @wraps(view)
        @login_required
        def wrapped(*args, **kwargs):
            if current_user()["role"] not in roles:
                abort(403)
            return view(*args, **kwargs)

        return wrapped

    return decorator


def is_admin(user=None):
    user = user or current_user()
    return bool(user and user["role"] in ("sarpras", "superadmin"))


def safe_next(target, fallback_endpoint="main.dashboard"):
    if target and target.startswith("/") and not target.startswith("//"):
        return target
    return url_for(fallback_endpoint)


# ---------------------------------------------------------------------------
# Formatting & validation helpers
# ---------------------------------------------------------------------------
def parse_iso_date(value, fallback=None):
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return fallback


def parse_hhmm(value, fallback=None):
    try:
        return datetime.strptime(value, "%H:%M").time()
    except (TypeError, ValueError):
        return fallback


def combine(day, clock):
    return datetime.combine(day, clock)


def slot_conflict(db, room_id, tanggal, mulai, selesai, exclude_id=None):
    query = """SELECT r.*, u.nama AS pemohon FROM reservations r
               JOIN users u ON u.id = r.user_id
               WHERE r.room_id = ? AND r.tanggal = ?
                 AND r.status IN ('processing', 'confirmed')
                 AND r.mulai < ? AND r.selesai > ?"""
    params = [room_id, tanggal, selesai, mulai]
    if exclude_id:
        query += " AND r.id != ?"
        params.append(exclude_id)
    query += " ORDER BY r.mulai LIMIT 1"
    return db.execute(query, params).fetchone()


def hero_room_availability(db):
    """Status ruang hari ini, tanpa data pribadi pemesan."""
    now = datetime.now()
    today = now.date().isoformat()
    current_hm = now.strftime("%H:%M")

    rooms = db.execute(
        """SELECT id, kode, nama, gedung, lantai, kapasitas
           FROM rooms WHERE aktif = 1 ORDER BY gedung, lantai, kode"""
    ).fetchall()
    bookings = db.execute(
        """SELECT room_id, mulai, selesai FROM reservations
           WHERE tanggal = ? AND status IN ('processing', 'confirmed')
             AND selesai > ?
           ORDER BY mulai""",
        (today, current_hm),
    ).fetchall()

    by_room = {}
    for booking in bookings:
        by_room.setdefault(booking["room_id"], []).append(booking)

    result = []
    for room in rooms:
        slots = by_room.get(room["id"], [])
        current_slot = next(
            (slot for slot in slots if slot["mulai"] <= current_hm < slot["selesai"]),
            None,
        )
        next_slot = next(
            (slot for slot in slots if slot["mulai"] > current_hm),
            None,
        )
        if current_slot:
            status, label = "terisi", "Terisi"
            detail = f"Terisi s.d. {current_slot['selesai']}"
        else:
            status, label = "kosong", "Kosong"
            detail = f"Berikutnya {next_slot['mulai']}" if next_slot else "Siap dipakai"

        result.append({
            "id": room["id"],
            "kode": room["kode"],
            "nama": room["nama"],
            "gedung": room["gedung"],
            "lantai": room["lantai"],
            "kapasitas": room["kapasitas"],
            "status": status,
            "label": label,
            "detail": detail,
        })

    result.sort(key=lambda item: (
        item["status"] != "kosong",
        item["gedung"],
        item["lantai"],
        item["kode"],
    ))
    return result


def new_booking_code():
    return "IDB-" + datetime.now().strftime("%y%m%d") + "-" + secrets.token_hex(3).upper()


def allowed_document(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def save_document(file_storage):
    original = secure_filename(file_storage.filename or "")
    if not original or not allowed_document(original):
        return None, "Format dokumen harus PDF, JPG, PNG, DOC, atau DOCX."
    file_storage.stream.seek(0, os.SEEK_END)
    size = file_storage.stream.tell()
    file_storage.stream.seek(0)
    if size > MAX_DOC_BYTES:
        return None, "Ukuran dokumen maksimal 8 MB."
    ext = original.rsplit(".", 1)[1].lower()
    name = secrets.token_hex(16) + "." + ext
    file_storage.save(os.path.join(current_app.config["UPLOAD_DIR"], name))
    return name, None


def user_can_manage(user, reservation):
    return is_admin(user) or reservation["user_id"] == user["id"]


def cancel_deadline(reservation):
    return combine(
        date.fromisoformat(reservation["tanggal"]),
        parse_hhmm(reservation["mulai"], time(0, 0)),
    )


def letter_number(reservation):
    day = date.fromisoformat(reservation["tanggal"])
    return f"{reservation['id']:04d}/IDB-SARPAS/{ROMAWI[day.month]}/{day.year}"


def build_reservation_pdf(reservation, verify_url):
    """Surat izin peminjaman resmi dalam PDF, tanpa tanda tangan fiktif."""
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_LEFT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        HRFlowable, Image as RLImage, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
    )

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=16 * mm,
        bottomMargin=18 * mm,
        title=f"Surat Peminjaman Ruangan {reservation['kode_booking']}",
        author="IDB Bali",
    )

    teal = colors.HexColor("#0A7386")
    teal_soft = colors.HexColor("#E2F1F3")
    orange = colors.HexColor("#EF9018")
    ink = colors.HexColor("#123238")
    muted = colors.HexColor("#5C7378")

    style_org = ParagraphStyle(
        "org", fontName="Helvetica-Bold", fontSize=14.5, leading=17,
        textColor=teal, alignment=TA_LEFT,
    )
    style_sub = ParagraphStyle(
        "sub", fontName="Helvetica-Bold", fontSize=8, leading=11,
        textColor=ink, spaceBefore=2,
    )
    style_addr = ParagraphStyle(
        "addr", fontName="Helvetica", fontSize=7.6, leading=10, textColor=muted,
    )
    style_title = ParagraphStyle(
        "title", fontName="Helvetica-Bold", fontSize=13, leading=16,
        alignment=TA_CENTER, textColor=ink,
    )
    style_number = ParagraphStyle(
        "number", fontName="Helvetica", fontSize=9.5, leading=13,
        alignment=TA_CENTER, textColor=muted,
    )
    style_body = ParagraphStyle(
        "body", fontName="Helvetica", fontSize=9.4, leading=14, textColor=ink,
    )
    style_small = ParagraphStyle(
        "small", fontName="Helvetica", fontSize=8, leading=11, textColor=muted,
    )
    style_label = ParagraphStyle(
        "label", fontName="Helvetica-Bold", fontSize=8.8, leading=12, textColor=ink,
    )
    style_value = ParagraphStyle(
        "value", fontName="Helvetica", fontSize=8.8, leading=12, textColor=ink,
    )

    logo_path = os.path.join(BASE_DIR, "static", "img", "logo-mark.png")
    logo = RLImage(logo_path, width=21 * mm, height=21 * mm)
    header_text = [
        Paragraph("INSTITUT DESAIN &amp; BISNIS BALI", style_org),
        Paragraph("SISTEM INFORMASI PEMINJAMAN RUANGAN", style_sub),
        Paragraph(
            "Jl. Tukad Batanghari No. 29, Denpasar, Bali &nbsp;·&nbsp; "
            "Jl. Tukad Barito No. 5X, Panjer<br/>www.idbbali.ac.id",
            style_addr,
        ),
    ]
    header = Table([[logo, header_text]], colWidths=[27 * mm, 143 * mm])
    header.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))

    story = [
        header,
        Spacer(1, 3 * mm),
        HRFlowable(width="100%", thickness=1.6, color=teal, spaceAfter=1.5 * mm),
        HRFlowable(width="100%", thickness=0.5, color=orange, spaceAfter=5 * mm),
        Paragraph("SURAT IZIN PEMINJAMAN RUANGAN", style_title),
        Paragraph(f"Nomor: {letter_number(reservation)}", style_number),
        Spacer(1, 6 * mm),
        Paragraph(
            "Unit Sarana &amp; Prasarana Institut Desain &amp; Bisnis Bali dengan ini "
            "memberikan izin peminjaman ruangan kepada:",
            style_body,
        ),
        Spacer(1, 3 * mm),
    ]

    prodi = reservation["prodi"] or "Sesuai data akademik"
    identity_rows = [
        [Paragraph("Nama Peminjam", style_label), Paragraph(xml_escape(reservation["pemohon"]), style_value)],
        [Paragraph("NIM / NIK", style_label), Paragraph(xml_escape(reservation["nim_nip"] or "-"), style_value)],
        [Paragraph("Program Studi / Unit", style_label), Paragraph(xml_escape(prodi), style_value)],
        [Paragraph("Peran", style_label), Paragraph(xml_escape(ROLE_LABELS.get(reservation["role_pemohon"], reservation["role_pemohon"])), style_value)],
        [Paragraph("Ruang", style_label), Paragraph(
            f"{xml_escape(reservation['nama_ruang'])} ({xml_escape(reservation['kode'])})", style_value)],
        [Paragraph("Lokasi", style_label), Paragraph(
            f"{xml_escape(reservation['gedung'])}, Lantai {reservation['lantai']}", style_value)],
        [Paragraph("Tanggal", style_label), Paragraph(tanggal_id(reservation["tanggal"]), style_value)],
        [Paragraph("Waktu", style_label), Paragraph(
            f"{reservation['mulai']}–{reservation['selesai']} WITA", style_value)],
        [Paragraph("Jumlah Peserta", style_label), Paragraph(
            f"{reservation['jumlah_peserta']} orang (kapasitas {reservation['kapasitas']})", style_value)],
        [Paragraph("Keperluan", style_label), Paragraph(xml_escape(reservation["keperluan"]), style_value)],
        [Paragraph("Kode Booking", style_label), Paragraph(xml_escape(reservation["kode_booking"]), style_value)],
    ]
    identity = Table(identity_rows, colWidths=[40 * mm, 130 * mm])
    identity.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), teal_soft),
        ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#B9D3D7")),
        ("INNERGRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#D8E6E8")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 4.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4.5),
    ]))
    story.extend([
        identity,
        Spacer(1, 5 * mm),
        Paragraph(
            "Peminjaman wajib digunakan sesuai keperluan yang tercantum, menjaga kebersihan dan "
            "fasilitas ruangan, serta menaati ketentuan kampus. Perubahan atau pembatalan jadwal "
            "harus dilakukan melalui Sistem Peminjaman Ruangan IDB Bali.",
            style_body,
        ),
        Spacer(1, 4 * mm),
    ])

    approver_name = reservation["approver_nama"]
    approver_role = ROLE_LABELS.get(reservation["approver_role"] or "", "")
    if approver_name:
        approver_line = f"{xml_escape(approver_name)}"
        if approver_role:
            approver_line += f" ({xml_escape(approver_role)})"
    else:
        approver_line = "Unit Sarana &amp; Prasarana IDB Bali"
    approved_at = reservation["approved_at"] or reservation["updated_at"]
    approval = Table(
        [[
            Paragraph("Status Persetujuan", style_label),
            Paragraph(
                f"<b>DISETUJUI</b><br/>Oleh: {approver_line}"
                f"<br/>Pada: {datetime_id(approved_at)} WITA",
                style_value,
            ),
        ]],
        colWidths=[40 * mm, 130 * mm],
    )
    approval.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, 0), teal_soft),
        ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#B9D3D7")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.extend([
        approval,
        Spacer(1, 6 * mm),
        Paragraph(
            "Demikian surat izin peminjaman ini dibuat untuk dipergunakan sebagaimana mestinya.",
            style_body,
        ),
        Spacer(1, 3 * mm),
        Paragraph(
            f"Denpasar, {tanggal_id(date.today().isoformat())}<br/>"
            "Unit Sarana &amp; Prasarana IDB Bali",
            style_body,
        ),
        Spacer(1, 8 * mm),
    ])

    qr_image = qrcode.make(verify_url)
    qr_buffer = io.BytesIO()
    qr_image.save(qr_buffer, format="PNG")
    qr_buffer.seek(0)
    qr_flow = RLImage(qr_buffer, width=24 * mm, height=24 * mm)
    verification = Table(
        [[
            qr_flow,
            [
                Paragraph("<b>Verifikasi keaslian surat</b>", style_value),
                Paragraph(
                    "Pindai QR untuk membuka halaman verifikasi publik. Surat ini diterbitkan "
                    "secara elektronik oleh sistem dan tidak memerlukan tanda tangan basah.",
                    style_small,
                ),
                Paragraph(xml_escape(verify_url), style_small),
            ],
        ]],
        colWidths=[28 * mm, 142 * mm],
    )
    verification.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(verification)

    def draw_footer(canvas, _doc):
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor("#D8E6E8"))
        canvas.line(20 * mm, 14 * mm, 190 * mm, 14 * mm)
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(muted)
        canvas.drawString(20 * mm, 10 * mm, "Sistem Peminjaman Ruangan IDB Bali · Unit Sarana & Prasarana")
        canvas.drawRightString(190 * mm, 10 * mm, f"Surat {reservation['kode_booking']}")
        canvas.restoreState()

    doc.build(story, onFirstPage=draw_footer, onLaterPages=draw_footer)
    buffer.seek(0)
    return buffer


# ---------------------------------------------------------------------------
# Template helpers
# ---------------------------------------------------------------------------
@bp.app_template_filter("tanggal_id")
def tanggal_id(value):
    if not value:
        return "-"
    if isinstance(value, str):
        try:
            value = date.fromisoformat(value)
        except ValueError:
            return value
    return f"{HARI[value.weekday()]}, {value.day} {BULAN[value.month]} {value.year}"


@bp.app_template_filter("tanggal_short")
def tanggal_short(value):
    if not value:
        return "-"
    if isinstance(value, str):
        value = date.fromisoformat(value)
    return f"{value.day} {BULAN[value.month][:3]} {value.year}"


@bp.app_template_filter("datetime_id")
def datetime_id(value):
    if not value:
        return "-"
    try:
        parsed = datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
    except (TypeError, ValueError):
        return value
    return f"{parsed.day} {BULAN[parsed.month][:3]} {parsed.year}, {parsed:%H:%M}"


def room_photo(kode=None, kategori=None):
    filename = ROOM_PHOTOS.get(kode) or CATEGORY_PHOTOS.get(kategori) or "gedung-idb-baru.jpg"
    return url_for("static", filename=f"img/rooms/{filename}")


@bp.context_processor
def inject_globals():
    return {
        "current_user": current_user(),
        "role_labels": ROLE_LABELS,
        "status_meta": STATUS_META,
        "today_iso": date.today().isoformat(),
        "now": datetime.now(),
        "is_admin_user": is_admin(),
        "room_photo": room_photo,
    }


# ---------------------------------------------------------------------------
# Public & auth routes
# ---------------------------------------------------------------------------
@bp.route("/")
def index():
    db = get_db()
    user = current_user()

    default_day = date.today()
    now = datetime.now()
    start_dt = (now + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
    if start_dt.hour >= 22:
        default_day = default_day + timedelta(days=1)
        start_dt = datetime.combine(default_day, time(8, 0))
    end_dt = start_dt + timedelta(hours=2)
    if end_dt.hour > 23 or (end_dt.hour == 23 and end_dt.minute > 0):
        end_dt = datetime.combine(start_dt.date(), time(23, 0))

    tanggal = parse_iso_date(request.args.get("tanggal"), default_day)
    mulai = parse_hhmm(request.args.get("mulai"), start_dt.time())
    selesai = parse_hhmm(request.args.get("selesai"), end_dt.time())
    gedung = request.args.get("gedung", "").strip()
    kategori = request.args.get("kategori", "").strip()
    kapasitas = request.args.get("kapasitas", type=int) or 0
    q = request.args.get("q", "").strip()

    time_valid = combine(tanggal, mulai) < combine(tanggal, selesai)

    sql = "SELECT * FROM rooms WHERE aktif = 1"
    params = []
    if gedung:
        sql += " AND gedung = ?"
        params.append(gedung)
    if kategori:
        sql += " AND kategori = ?"
        params.append(kategori)
    if kapasitas:
        sql += " AND kapasitas >= ?"
        params.append(kapasitas)
    if q:
        sql += " AND (nama LIKE ? OR kode LIKE ? OR kategori LIKE ?)"
        like = f"%{q}%"
        params.extend([like, like, like])
    sql += " ORDER BY gedung, lantai, kode"
    rooms = [dict(row) for row in db.execute(sql, params).fetchall()]

    busy_map = {}
    if time_valid:
        rows = db.execute(
            """SELECT room_id, mulai, selesai, status FROM reservations
               WHERE tanggal = ? AND status IN ('processing', 'confirmed')
                 AND mulai < ? AND selesai > ?
               ORDER BY mulai""",
            (tanggal.isoformat(), selesai.strftime("%H:%M"), mulai.strftime("%H:%M")),
        ).fetchall()
        for row in rows:
            busy_map.setdefault(row["room_id"], []).append(dict(row))

    for room in rooms:
        room["busy"] = busy_map.get(room["id"], [])
        room["available"] = time_valid and not room["busy"]
        room["locked"] = bool(room["terbatas"]) and not is_admin(user)

    buildings = [r["gedung"] for r in db.execute(
        "SELECT DISTINCT gedung FROM rooms WHERE aktif = 1 ORDER BY gedung"
    ).fetchall()]
    categories = [r["kategori"] for r in db.execute(
        "SELECT DISTINCT kategori FROM rooms WHERE aktif = 1 ORDER BY kategori"
    ).fetchall()]

    stats = {
        "rooms": db.execute("SELECT COUNT(*) AS n FROM rooms WHERE aktif = 1").fetchone()["n"],
        "buildings": len(buildings),
        "confirmed": db.execute(
            "SELECT COUNT(*) AS n FROM reservations WHERE status = 'confirmed'"
        ).fetchone()["n"],
        "pending": db.execute(
            "SELECT COUNT(*) AS n FROM reservations WHERE status = 'processing'"
        ).fetchone()["n"],
    }

    return render_template(
        "index.html",
        rooms=rooms,
        buildings=buildings,
        categories=categories,
        filters={
            "tanggal": tanggal.isoformat(),
            "mulai": mulai.strftime("%H:%M"),
            "selesai": selesai.strftime("%H:%M"),
            "gedung": gedung,
            "kategori": kategori,
            "kapasitas": kapasitas,
            "q": q,
        },
        time_valid=time_valid,
        stats=stats,
        hero_rooms=hero_room_availability(db),
        hero_updated=datetime.now().strftime("%H:%M"),
    )


@bp.route("/api/hero-availability")
def api_hero_availability():
    response = jsonify({
        "rooms": hero_room_availability(get_db()),
        "generated_at": datetime.now().strftime("%H:%M"),
    })
    response.headers["Cache-Control"] = "no-store"
    return response


@bp.route("/kalender")
def calendar_view():
    db = get_db()
    today = date.today()
    month_raw = request.args.get("bulan", "").strip()
    try:
        year, month = [int(part) for part in month_raw.split("-", 1)]
        first = date(year, month, 1)
    except (TypeError, ValueError):
        first = date(today.year, today.month, 1)
    if not 1 <= first.month <= 12:
        first = date(today.year, today.month, 1)
    last = (date(first.year + (1 if first.month == 12 else 0),
                 1 if first.month == 12 else first.month + 1, 1) - timedelta(days=1))
    grid_start = first - timedelta(days=first.weekday())
    grid_end = last + timedelta(days=6 - last.weekday())

    room_id = request.args.get("room", type=int)
    rooms = db.execute(
        "SELECT id, kode, nama, gedung, lantai FROM rooms WHERE aktif = 1 ORDER BY gedung, lantai, kode"
    ).fetchall()

    sql = """SELECT r.tanggal, r.mulai, r.selesai, r.status, rm.kode, rm.nama AS nama_ruang
             FROM reservations r JOIN rooms rm ON rm.id = r.room_id
             WHERE r.tanggal BETWEEN ? AND ? AND r.status IN ('processing', 'confirmed')"""
    params = [grid_start.isoformat(), grid_end.isoformat()]
    if room_id:
        sql += " AND r.room_id = ?"
        params.append(room_id)
    sql += " ORDER BY r.tanggal, r.mulai"
    bookings = db.execute(sql, params).fetchall()

    by_day = {}
    for booking in bookings:
        by_day.setdefault(booking["tanggal"], []).append(booking)

    days = []
    cursor = grid_start
    while cursor <= grid_end:
        days.append({
            "date": cursor,
            "iso": cursor.isoformat(),
            "day": cursor.day,
            "in_month": cursor.month == first.month,
            "is_today": cursor == today,
            "bookings": by_day.get(cursor.isoformat(), []),
        })
        cursor += timedelta(days=1)
    weeks = [days[index:index + 7] for index in range(0, len(days), 7)]

    prev_month = (first - timedelta(days=1)).replace(day=1)
    next_month = (last + timedelta(days=1)).replace(day=1)
    selected_room = next((room for room in rooms if room["id"] == room_id), None)
    return render_template(
        "calendar.html",
        weeks=weeks,
        month_label=f"{BULAN[first.month]} {first.year}",
        first_iso=first.isoformat(),
        prev_month=prev_month.strftime("%Y-%m"),
        next_month=next_month.strftime("%Y-%m"),
        rooms=rooms,
        selected_room=selected_room,
        room_id=room_id,
        total_bookings=len(bookings),
    )


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user():
        return redirect(url_for("main.dashboard"))

    if request.method == "POST":
        identifier = (
            request.form.get("identifier")
            or request.form.get("nim_nip")
            or request.form.get("email")
            or ""
        ).strip()
        password = request.form.get("password", "")
        user = get_db().execute(
            """SELECT * FROM users
               WHERE lower(COALESCE(nim_nip, '')) = lower(?)
                  OR lower(email) = lower(?)
               LIMIT 1""",
            (identifier, identifier),
        ).fetchone()
        if not user or not check_password_hash(user["password_hash"], password):
            flash("NIM/NIK atau kata sandi belum tepat.", "danger")
        else:
            session.clear()
            session["user_id"] = user["id"]
            flash(f"Selamat datang, {user['nama'].split()[0]}!", "success")
            return redirect(safe_next(request.args.get("next")))

    return render_template("login.html")


@bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user():
        return redirect(url_for("main.dashboard"))

    if request.method == "POST":
        nama = request.form.get("nama", "").strip()
        nim = request.form.get("nim_nip", "").strip()
        email = request.form.get("email", "").strip().lower()
        prodi = request.form.get("prodi", "").strip()
        role = request.form.get("role", "mahasiswa")
        password = request.form.get("password", "")
        confirm = request.form.get("confirm", "")

        errors = []
        if len(nama) < 3:
            errors.append("Nama minimal 3 karakter.")
        if len(nim) < 3 or len(nim) > 40:
            errors.append("NIM/NIK wajib diisi (3–40 karakter).")
        if email and ("@" not in email or "." not in email.split("@")[-1]):
            errors.append("Alamat email tidak valid.")
        if role not in ("mahasiswa", "dosen"):
            errors.append("Peran pendaftaran tidak valid.")
        if len(password) < 4:
            errors.append("Kata sandi minimal 4 karakter.")
        if password != confirm:
            errors.append("Konfirmasi kata sandi belum sama.")

        db = get_db()
        if not errors:
            if db.execute("SELECT 1 FROM users WHERE lower(nim_nip) = lower(?)", (nim,)).fetchone():
                errors.append("NIM/NIK sudah terdaftar. Silakan masuk.")
            if email and db.execute("SELECT 1 FROM users WHERE lower(email) = lower(?)", (email,)).fetchone():
                errors.append("Email sudah terdaftar. Silakan masuk.")

        if errors:
            for message in errors:
                flash(message, "danger")
        else:
            stored_email = email or f"{nim.lower().replace(' ', '')}@idb.local"
            try:
                db.execute(
                    """INSERT INTO users (nama, email, password_hash, role, nim_nip, prodi)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (nama, stored_email,
                     generate_password_hash(password, method="pbkdf2:sha256"),
                     role, nim, prodi or None),
                )
            except sqlite3.IntegrityError:
                db.rollback()
                flash("NIM/NIK atau email sudah terdaftar. Silakan masuk.", "danger")
                return render_template("register.html")
            db.commit()
            user = db.execute(
                "SELECT * FROM users WHERE lower(nim_nip) = lower(?)", (nim,)
            ).fetchone()
            session.clear()
            session["user_id"] = user["id"]
            flash("Akun berhasil dibuat. Selamat datang di IDB Bali.", "success")
            return redirect(url_for("main.dashboard"))

    return render_template("register.html")


@bp.post("/logout")
def logout():
    session.clear()
    flash("Anda telah keluar.", "success")
    return redirect(url_for("main.index"))


# ---------------------------------------------------------------------------
# Booking flow (FR-01, FR-02, FR-03, BR-01, BR-02)
# ---------------------------------------------------------------------------
@bp.route("/book/<int:room_id>", methods=["GET", "POST"])
@login_required
def book(room_id):
    db = get_db()
    room = db.execute("SELECT * FROM rooms WHERE id = ? AND aktif = 1", (room_id,)).fetchone()
    if not room:
        abort(404)
    user = current_user()
    if room["terbatas"] and not is_admin(user):
        abort(403)

    selected_day = parse_iso_date(
        request.args.get("tanggal"), date.today()
    )
    selected_mulai = parse_hhmm(request.args.get("mulai"), time(9, 0))
    selected_selesai = parse_hhmm(request.args.get("selesai"), time(11, 0))

    form = {
        "tanggal": selected_day.isoformat(),
        "mulai": selected_mulai.strftime("%H:%M"),
        "selesai": selected_selesai.strftime("%H:%M"),
        "keperluan": "",
        "jumlah_peserta": min(room["kapasitas"], 10),
    }
    errors = []

    if request.method == "POST":
        form = {
            "tanggal": request.form.get("tanggal", "").strip(),
            "mulai": request.form.get("mulai", "").strip(),
            "selesai": request.form.get("selesai", "").strip(),
            "keperluan": request.form.get("keperluan", "").strip(),
            "jumlah_peserta": request.form.get("jumlah_peserta", type=int) or 0,
        }
        day = parse_iso_date(form["tanggal"])
        mulai = parse_hhmm(form["mulai"])
        selesai = parse_hhmm(form["selesai"])
        upload = request.files.get("dokumen")

        if day is None:
            errors.append("Tanggal reservasi tidak valid.")
        if mulai is None or selesai is None:
            errors.append("Jam mulai dan jam selesai wajib diisi.")
        if day and mulai and selesai:
            if not (mulai < selesai):
                errors.append("Jam mulai harus lebih awal dari jam selesai (BR-01).")
            elif combine(day, mulai) <= datetime.now():
                errors.append("Waktu mulai reservasi sudah terlewat.")
            elif mulai < time(6, 0) or selesai > time(23, 0):
                errors.append("Reservasi hanya tersedia antara pukul 06:00 dan 23:00.")
        if len(form["keperluan"]) < 10:
            errors.append("Tuliskan keperluan minimal 10 karakter agar mudah diverifikasi.")
        if form["jumlah_peserta"] < 1:
            errors.append("Jumlah peserta minimal 1 orang.")
        elif form["jumlah_peserta"] > room["kapasitas"]:
            errors.append(f"Jumlah peserta melebihi kapasitas ruang ({room['kapasitas']} orang).")
        if room["butuh_dokumen"] and (not upload or not upload.filename):
            errors.append("Ruang ini membutuhkan dokumen permohonan / rekomendasi dosen.")

        document_name = None
        if upload and upload.filename:
            document_name, doc_error = save_document(upload)
            if doc_error:
                errors.append(doc_error)

        if not errors:
            day_iso = day.isoformat()
            mulai_s = mulai.strftime("%H:%M")
            selesai_s = selesai.strftime("%H:%M")
            user_id = user["id"]

            _write_lock.acquire()
            try:
                db.execute("BEGIN IMMEDIATE")

                duplicate = db.execute(
                    """SELECT id FROM reservations
                       WHERE user_id = ? AND room_id = ? AND tanggal = ?
                         AND mulai = ? AND selesai = ?
                         AND status IN ('processing', 'confirmed')
                       ORDER BY id DESC LIMIT 1""",
                    (user_id, room_id, day_iso, mulai_s, selesai_s),
                ).fetchone()
                if duplicate:
                    db.rollback()
                    flash("Reservasi yang sama sudah tercatat. Tidak ada duplikasi dibuat.", "warning")
                    return redirect(url_for("main.reservation_detail", reservation_id=duplicate["id"]))

                conflict = slot_conflict(db, room_id, day_iso, mulai_s, selesai_s)
                code = new_booking_code()

                if conflict:
                    cur = db.execute(
                        """INSERT INTO reservations
                           (kode_booking, user_id, room_id, tanggal, mulai, selesai, status,
                            keperluan, jumlah_peserta, dokumen, alasan_gagal)
                           VALUES (?, ?, ?, ?, ?, ?, 'failed', ?, ?, ?, ?)""",
                        (code, user_id, room_id, day_iso, mulai_s, selesai_s,
                         form["keperluan"], form["jumlah_peserta"], document_name,
                         f"Slot bertabrakan dengan reservasi {conflict['kode_booking']}."),
                    )
                    reservation_id = cur.lastrowid
                    log_audit(
                        db, reservation_id, user_id, "booking_failed",
                        f"Konflik slot dengan {conflict['kode_booking']} pada {day_iso} "
                        f"{mulai_s}-{selesai_s}. Tepat satu alokasi dipertahankan.",
                    )
                    db.commit()
                    flash(
                        "Maaf, slot tersebut baru saja dialokasikan ke pemesan lain. "
                        "Silakan pilih slot berbeda.",
                        "danger",
                    )
                    return redirect(url_for("main.reservation_detail", reservation_id=reservation_id))

                status = "processing" if room["butuh_approval"] else "confirmed"
                cur = db.execute(
                    """INSERT INTO reservations
                       (kode_booking, user_id, room_id, tanggal, mulai, selesai, status,
                        keperluan, jumlah_peserta, dokumen)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (code, user_id, room_id, day_iso, mulai_s, selesai_s, status,
                     form["keperluan"], form["jumlah_peserta"], document_name),
                )
                reservation_id = cur.lastrowid
                log_audit(
                    db, reservation_id, user_id, "booking_created",
                    f"Reservasi {code} dibuat dengan status {status} untuk {room['kode']} "
                    f"pada {day_iso} {mulai_s}-{selesai_s}.",
                )
                db.commit()
            except Exception:
                db.rollback()
                raise
            finally:
                _write_lock.release()

            if status == "processing":
                flash("Reservasi diterima dan menunggu verifikasi Petugas Sarpras.", "warning")
            else:
                flash("Slot berhasil dialokasikan. Bukti peminjaman siap digunakan.", "success")
            return redirect(url_for("main.reservation_detail", reservation_id=reservation_id))

        for message in errors:
            flash(message, "danger")

    schedule_day = parse_iso_date(form["tanggal"], date.today())
    schedule = db.execute(
        """SELECT mulai, selesai, status FROM reservations
           WHERE room_id = ? AND tanggal = ? AND status IN ('processing', 'confirmed')
           ORDER BY mulai""",
        (room_id, schedule_day.isoformat()),
    ).fetchall()
    return render_template(
        "book.html", room=room, form=form, errors=errors, schedule=schedule,
        schedule_day=schedule_day,
    )


@bp.route("/reservations/<int:reservation_id>")
@login_required
def reservation_detail(reservation_id):
    db = get_db()
    reservation = db.execute(
        """SELECT r.*, u.nama AS pemohon, u.email AS email_pemohon, u.role AS role_pemohon,
                  u.nim_nip, u.prodi, rm.kode, rm.nama AS nama_ruang, rm.gedung, rm.lantai, rm.kategori,
                  rm.kapasitas
           FROM reservations r
           JOIN users u ON u.id = r.user_id
           JOIN rooms rm ON rm.id = r.room_id
           WHERE r.id = ?""",
        (reservation_id,),
    ).fetchone()
    if not reservation:
        abort(404)
    user = current_user()
    if not user_can_manage(user, reservation):
        abort(403)

    audits = db.execute(
        """SELECT a.*, u.nama AS actor, u.role AS actor_role FROM audit_logs a
           LEFT JOIN users u ON u.id = a.actor_id
           WHERE a.reservation_id = ? ORDER BY a.id ASC""",
        (reservation_id,),
    ).fetchall()
    can_cancel = (
        reservation["status"] in ACTIVE_STATUSES
        and datetime.now() < cancel_deadline(reservation)
    )
    return render_template(
        "reservation.html",
        reservation=reservation,
        audits=audits,
        can_cancel=can_cancel,
        verify_url=url_for("main.verify", kode=reservation["kode_booking"], _external=True),
    )


@bp.post("/reservations/<int:reservation_id>/cancel")
@login_required
def cancel_reservation(reservation_id):
    db = get_db()
    reservation = db.execute(
        "SELECT * FROM reservations WHERE id = ?", (reservation_id,)
    ).fetchone()
    if not reservation:
        abort(404)
    user = current_user()
    if not user_can_manage(user, reservation):
        abort(403)

    reason = request.form.get("alasan", "").strip()
    if len(reason) < 3:
        flash("Alasan pembatalan wajib diisi (minimal 3 karakter).", "danger")
        return redirect(url_for("main.reservation_detail", reservation_id=reservation_id))
    if reservation["status"] not in ACTIVE_STATUSES:
        flash("Reservasi ini tidak dapat dibatalkan pada status saat ini.", "danger")
        return redirect(url_for("main.reservation_detail", reservation_id=reservation_id))
    if datetime.now() >= cancel_deadline(reservation):
        flash("Pembatalan hanya dapat dilakukan sebelum waktu mulai (BR-03).", "danger")
        return redirect(url_for("main.reservation_detail", reservation_id=reservation_id))

    with _write_lock:
        try:
            db.execute("BEGIN IMMEDIATE")
            fresh = db.execute(
                "SELECT * FROM reservations WHERE id = ?", (reservation_id,)
            ).fetchone()
            if fresh["status"] not in ACTIVE_STATUSES:
                db.rollback()
                flash("Status reservasi sudah berubah. Muat ulang halaman.", "warning")
                return redirect(url_for("main.reservation_detail", reservation_id=reservation_id))
            db.execute(
                """UPDATE reservations
                   SET status = 'cancelled', alasan_batal = ?, updated_at = datetime('now', 'localtime')
                   WHERE id = ?""",
                (reason, reservation_id),
            )
            log_audit(
                db, reservation_id, user["id"], "reservation_cancelled",
                f"Dibatalkan oleh {user['nama']} ({user['role']}). Alasan: {reason}. Slot kembali tersedia.",
            )
            db.commit()
        except Exception:
            db.rollback()
            raise
    flash("Reservasi dibatalkan dan slot kembali terbuka.", "success")
    return redirect(url_for("main.reservation_detail", reservation_id=reservation_id))


@bp.route("/verify/<kode>")
def verify(kode):
    reservation = get_db().execute(
        """SELECT r.*, u.nama AS pemohon, rm.kode, rm.nama AS nama_ruang, rm.gedung, rm.lantai
           FROM reservations r
           JOIN users u ON u.id = r.user_id
           JOIN rooms rm ON rm.id = r.room_id
           WHERE r.kode_booking = ?""",
        (kode,),
    ).fetchone()
    if not reservation:
        abort(404)
    return render_template("verify.html", reservation=reservation)


@bp.route("/download")
def download_zip():
    zip_path = os.path.join(BASE_DIR, "idb-bali.zip")
    if not os.path.isfile(zip_path):
        abort(404)
    return send_file(zip_path, as_attachment=True, download_name="idb-bali.zip")


@bp.route("/reservations/<int:reservation_id>/qr.png")
@login_required
def reservation_qr(reservation_id):
    db = get_db()
    reservation = db.execute(
        "SELECT * FROM reservations WHERE id = ?", (reservation_id,)
    ).fetchone()
    if not reservation:
        abort(404)
    if not user_can_manage(current_user(), reservation):
        abort(403)
    target = url_for("main.verify", kode=reservation["kode_booking"], _external=True)
    image = qrcode.make(target)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    buffer.seek(0)
    return (
        buffer.getvalue(),
        200,
        {
            "Content-Type": "image/png",
            "Cache-Control": "no-store",
            "Content-Disposition": f'inline; filename="qr-{reservation["kode_booking"]}.png"',
        },
    )


@bp.route("/reservations/<int:reservation_id>/surat.pdf")
@login_required
def reservation_letter(reservation_id):
    db = get_db()
    reservation = db.execute(
        """SELECT r.*, u.nama AS pemohon, u.nim_nip, u.prodi, u.role AS role_pemohon,
                  rm.kode, rm.nama AS nama_ruang, rm.gedung, rm.lantai, rm.kategori, rm.kapasitas,
                  a.nama AS approver_nama, a.role AS approver_role
           FROM reservations r
           JOIN users u ON u.id = r.user_id
           JOIN rooms rm ON rm.id = r.room_id
           LEFT JOIN users a ON a.id = r.approved_by
           WHERE r.id = ?""",
        (reservation_id,),
    ).fetchone()
    if not reservation:
        abort(404)
    if not user_can_manage(current_user(), reservation):
        abort(403)
    if reservation["status"] != "confirmed":
        flash("Surat peminjaman hanya tersedia untuk reservasi yang telah dikonfirmasi.", "warning")
        return redirect(url_for("main.reservation_detail", reservation_id=reservation_id))

    verify_url = url_for("main.verify", kode=reservation["kode_booking"], _external=True)
    pdf = build_reservation_pdf(reservation, verify_url)
    download = request.args.get("download") == "1"
    return send_file(
        pdf,
        mimetype="application/pdf",
        as_attachment=download,
        download_name=f"Surat-Peminjaman-{reservation['kode_booking']}.pdf",
    )


@bp.route("/uploads/<path:filename>")
@login_required
def download_document(filename):
    db = get_db()
    reservation = db.execute(
        "SELECT * FROM reservations WHERE dokumen = ? LIMIT 1", (filename,)
    ).fetchone()
    if not reservation:
        abort(404)
    if not user_can_manage(current_user(), reservation):
        abort(403)
    return send_from_directory(current_app.config["UPLOAD_DIR"], filename, as_attachment=True)


# ---------------------------------------------------------------------------
# Student / lecturer dashboard
# ---------------------------------------------------------------------------
@bp.route("/dashboard")
@login_required
def dashboard():
    db = get_db()
    user = current_user()
    reservations = db.execute(
        """SELECT r.*, rm.kode, rm.nama AS nama_ruang, rm.gedung, rm.lantai
           FROM reservations r JOIN rooms rm ON rm.id = r.room_id
           WHERE r.user_id = ?
           ORDER BY r.tanggal DESC, r.mulai DESC""",
        (user["id"],),
    ).fetchall()
    upcoming = [
        r for r in reservations
        if r["status"] in ACTIVE_STATUSES
        and combine(date.fromisoformat(r["tanggal"]), parse_hhmm(r["mulai"], time(0, 0))) >= datetime.now()
    ]
    stats = {
        "upcoming": len(upcoming),
        "confirmed": sum(1 for r in reservations if r["status"] == "confirmed"),
        "processing": sum(1 for r in reservations if r["status"] == "processing"),
        "history": sum(1 for r in reservations if r["status"] in ("cancelled", "failed")),
    }
    return render_template("dashboard.html", reservations=reservations, stats=stats)


# ---------------------------------------------------------------------------
# Admin / Sarpras
# ---------------------------------------------------------------------------
@bp.route("/admin")
@roles_required("sarpras", "superadmin")
def admin_dashboard():
    db = get_db()
    stats = {
        "rooms": db.execute("SELECT COUNT(*) AS n FROM rooms WHERE aktif = 1").fetchone()["n"],
        "today": db.execute(
            "SELECT COUNT(*) AS n FROM reservations WHERE tanggal = ? AND status IN ('processing','confirmed')",
            (date.today().isoformat(),),
        ).fetchone()["n"],
        "pending": db.execute(
            "SELECT COUNT(*) AS n FROM reservations WHERE status = 'processing'"
        ).fetchone()["n"],
        "confirmed": db.execute(
            "SELECT COUNT(*) AS n FROM reservations WHERE status = 'confirmed'"
        ).fetchone()["n"],
        "cancelled": db.execute(
            "SELECT COUNT(*) AS n FROM reservations WHERE status = 'cancelled'"
        ).fetchone()["n"],
    }
    pending = db.execute(
        """SELECT r.*, u.nama AS pemohon, u.role AS role_pemohon, u.nim_nip,
                  rm.kode, rm.nama AS nama_ruang, rm.gedung
           FROM reservations r JOIN users u ON u.id = r.user_id JOIN rooms rm ON rm.id = r.room_id
           WHERE r.status = 'processing'
           ORDER BY r.created_at ASC LIMIT 12"""
    ).fetchall()
    recent = db.execute(
        """SELECT r.*, u.nama AS pemohon, rm.kode, rm.nama AS nama_ruang
           FROM reservations r JOIN users u ON u.id = r.user_id JOIN rooms rm ON rm.id = r.room_id
           ORDER BY r.id DESC LIMIT 8"""
    ).fetchall()
    busiest = db.execute(
        """SELECT rm.kode, rm.nama, COUNT(r.id) AS total
           FROM rooms rm LEFT JOIN reservations r
             ON r.room_id = rm.id AND r.status = 'confirmed'
           GROUP BY rm.id ORDER BY total DESC, rm.kode LIMIT 5"""
    ).fetchall()
    return render_template(
        "admin_dashboard.html", stats=stats, pending=pending, recent=recent, busiest=busiest
    )


@bp.route("/admin/reservations")
@roles_required("sarpras", "superadmin")
def admin_reservations():
    db = get_db()
    status = request.args.get("status", "").strip()
    gedung = request.args.get("gedung", "").strip()
    tanggal = request.args.get("tanggal", "").strip()
    q = request.args.get("q", "").strip()

    sql = """SELECT r.*, u.nama AS pemohon, u.role AS role_pemohon, u.nim_nip,
                    rm.kode, rm.nama AS nama_ruang, rm.gedung, rm.lantai
             FROM reservations r JOIN users u ON u.id = r.user_id JOIN rooms rm ON rm.id = r.room_id
             WHERE 1 = 1"""
    params = []
    if status:
        sql += " AND r.status = ?"
        params.append(status)
    if gedung:
        sql += " AND rm.gedung = ?"
        params.append(gedung)
    if tanggal:
        sql += " AND r.tanggal = ?"
        params.append(tanggal)
    if q:
        sql += " AND (r.kode_booking LIKE ? OR u.nama LIKE ? OR rm.kode LIKE ? OR r.keperluan LIKE ?)"
        like = f"%{q}%"
        params.extend([like, like, like, like])
    sql += " ORDER BY r.tanggal DESC, r.mulai DESC, r.id DESC LIMIT 200"
    reservations = db.execute(sql, params).fetchall()
    buildings = [r["gedung"] for r in db.execute(
        "SELECT DISTINCT gedung FROM rooms ORDER BY gedung"
    ).fetchall()]

    return render_template(
        "admin_reservations.html",
        reservations=reservations,
        buildings=buildings,
        filters={"status": status, "gedung": gedung, "tanggal": tanggal, "q": q},
    )


@bp.post("/admin/reservations/<int:reservation_id>/approve")
@roles_required("sarpras", "superadmin")
def approve_reservation(reservation_id):
    db = get_db()
    user = current_user()
    with _write_lock:
        try:
            db.execute("BEGIN IMMEDIATE")
            reservation = db.execute(
                "SELECT * FROM reservations WHERE id = ?", (reservation_id,)
            ).fetchone()
            if not reservation or reservation["status"] != "processing":
                db.rollback()
                flash("Reservasi tidak berada pada status menunggu verifikasi.", "warning")
                return redirect(url_for("main.admin_reservations"))

            conflict = slot_conflict(
                db, reservation["room_id"], reservation["tanggal"],
                reservation["mulai"], reservation["selesai"], exclude_id=reservation_id,
            )
            if conflict:
                db.execute(
                    """UPDATE reservations SET status = 'failed', alasan_gagal = ?,
                       approved_by = ?, approved_at = datetime('now','localtime'),
                       updated_at = datetime('now','localtime') WHERE id = ?""",
                    (f"Konflik slot dengan {conflict['kode_booking']}.", user["id"], reservation_id),
                )
                log_audit(
                    db, reservation_id, user["id"], "approval_failed",
                    f"Approval gagal: slot bertabrakan dengan {conflict['kode_booking']}.",
                )
                db.commit()
                flash("Approval gagal karena slot sudah dipakai reservasi lain.", "danger")
            else:
                db.execute(
                    """UPDATE reservations SET status = 'confirmed', approved_by = ?,
                       approved_at = datetime('now','localtime'),
                       updated_at = datetime('now','localtime') WHERE id = ?""",
                    (user["id"], reservation_id),
                )
                log_audit(
                    db, reservation_id, user["id"], "reservation_approved",
                    f"Disetujui oleh {user['nama']}. Status kini confirmed.",
                )
                db.commit()
                flash("Reservasi berhasil disetujui dan dikonfirmasi.", "success")
        except Exception:
            db.rollback()
            raise
    return redirect(url_for("main.admin_reservations"))


@bp.post("/admin/reservations/<int:reservation_id>/reject")
@roles_required("sarpras", "superadmin")
def reject_reservation(reservation_id):
    reason = request.form.get("alasan", "").strip()
    if len(reason) < 3:
        flash("Alasan penolakan wajib diisi (minimal 3 karakter).", "danger")
        return redirect(url_for("main.admin_reservations"))

    db = get_db()
    user = current_user()
    with _write_lock:
        try:
            db.execute("BEGIN IMMEDIATE")
            reservation = db.execute(
                "SELECT * FROM reservations WHERE id = ?", (reservation_id,)
            ).fetchone()
            if not reservation or reservation["status"] != "processing":
                db.rollback()
                flash("Reservasi tidak berada pada status menunggu verifikasi.", "warning")
                return redirect(url_for("main.admin_reservations"))
            db.execute(
                """UPDATE reservations SET status = 'failed', alasan_gagal = ?,
                   approved_by = ?, approved_at = datetime('now','localtime'),
                   updated_at = datetime('now','localtime') WHERE id = ?""",
                (reason, user["id"], reservation_id),
            )
            log_audit(
                db, reservation_id, user["id"], "reservation_rejected",
                f"Ditolak oleh {user['nama']}. Alasan: {reason}",
            )
            db.commit()
        except Exception:
            db.rollback()
            raise
    flash("Reservasi ditolak dan pemohon dapat melihat alasannya.", "success")
    return redirect(url_for("main.admin_reservations"))


@bp.route("/admin/users")
@roles_required("sarpras", "superadmin")
def admin_users():
    db = get_db()
    q = request.args.get("q", "").strip()
    role = request.args.get("role", "").strip()
    sql = """SELECT u.*,
                    COUNT(r.id) AS total_reservasi,
                    COALESCE(SUM(CASE WHEN r.status = 'confirmed' THEN 1 ELSE 0 END), 0) AS total_konfirmasi
             FROM users u
             LEFT JOIN reservations r ON r.user_id = u.id
             WHERE 1 = 1"""
    params = []
    if q:
        sql += " AND (u.nama LIKE ? OR u.email LIKE ? OR u.nim_nip LIKE ? OR u.prodi LIKE ?)"
        like = f"%{q}%"
        params.extend([like, like, like, like])
    if role:
        sql += " AND u.role = ?"
        params.append(role)
    sql += " GROUP BY u.id ORDER BY CASE u.role WHEN 'superadmin' THEN 0 WHEN 'sarpras' THEN 1 WHEN 'dosen' THEN 2 ELSE 3 END, u.nama"
    users = db.execute(sql, params).fetchall()
    stats = {
        "total": db.execute("SELECT COUNT(*) AS n FROM users").fetchone()["n"],
        "mahasiswa": db.execute("SELECT COUNT(*) AS n FROM users WHERE role = 'mahasiswa'").fetchone()["n"],
        "dosen": db.execute("SELECT COUNT(*) AS n FROM users WHERE role = 'dosen'").fetchone()["n"],
        "petugas": db.execute("SELECT COUNT(*) AS n FROM users WHERE role IN ('sarpras','superadmin')").fetchone()["n"],
    }
    return render_template(
        "admin_users.html", users=users, stats=stats,
        filters={"q": q, "role": role},
    )


@bp.post("/admin/users/<int:user_id>/role")
@roles_required("superadmin")
def admin_update_user_role(user_id):
    db = get_db()
    target = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if not target:
        abort(404)
    role = request.form.get("role", "").strip()
    if role not in ROLES:
        flash("Peran pengguna tidak valid.", "danger")
        return redirect(url_for("main.admin_users"))
    actor = current_user()
    if target["id"] == actor["id"] and role != "superadmin":
        flash("Super Admin tidak dapat menurunkan perannya sendiri.", "danger")
        return redirect(url_for("main.admin_users"))
    if target["role"] == "superadmin" and role != "superadmin":
        count = db.execute("SELECT COUNT(*) AS n FROM users WHERE role = 'superadmin'").fetchone()["n"]
        if count <= 1:
            flash("Minimal satu Super Admin harus tetap aktif.", "danger")
            return redirect(url_for("main.admin_users"))

    if role != target["role"]:
        db.execute("UPDATE users SET role = ? WHERE id = ?", (role, user_id))
        log_audit(
            db, None, actor["id"], "user_role_updated",
            f"Peran {target['nama']} ({target['nim_nip'] or target['email']}) diubah "
            f"dari {target['role']} menjadi {role} oleh {actor['nama']}.",
        )
        db.commit()
        flash(f"Peran {target['nama']} diperbarui menjadi {ROLE_LABELS[role]}.", "success")
    else:
        flash("Tidak ada perubahan peran.", "warning")
    return redirect(url_for("main.admin_users"))


def report_data(db):
    status_counts = {
        row["status"]: row["n"]
        for row in db.execute(
            "SELECT status, COUNT(*) AS n FROM reservations GROUP BY status"
        ).fetchall()
    }
    total = sum(status_counts.values())
    per_room = db.execute(
        """SELECT rm.kode, rm.nama, rm.gedung, COUNT(r.id) AS total,
                  COALESCE(SUM(CASE WHEN r.status = 'confirmed' THEN 1 ELSE 0 END), 0) AS confirmed,
                  COALESCE(SUM(CASE WHEN r.status = 'processing' THEN 1 ELSE 0 END), 0) AS processing,
                  COALESCE(SUM(CASE WHEN r.status IN ('failed','cancelled') THEN 1 ELSE 0 END), 0) AS gagal
           FROM rooms rm LEFT JOIN reservations r ON r.room_id = rm.id
           GROUP BY rm.id ORDER BY total DESC, rm.kode"""
    ).fetchall()
    per_building = db.execute(
        """SELECT rm.gedung, COUNT(r.id) AS total,
                  COALESCE(SUM(CASE WHEN r.status = 'confirmed' THEN 1 ELSE 0 END), 0) AS confirmed
           FROM rooms rm LEFT JOIN reservations r ON r.room_id = rm.id
           GROUP BY rm.gedung ORDER BY total DESC"""
    ).fetchall()
    monthly = db.execute(
        """SELECT substr(tanggal, 1, 7) AS bulan, COUNT(*) AS total,
                  SUM(CASE WHEN status = 'confirmed' THEN 1 ELSE 0 END) AS confirmed
           FROM reservations GROUP BY bulan ORDER BY bulan DESC LIMIT 6"""
    ).fetchall()
    top_users = db.execute(
        """SELECT u.nama, u.role, u.nim_nip, COUNT(r.id) AS total
           FROM users u JOIN reservations r ON r.user_id = u.id
           GROUP BY u.id ORDER BY total DESC LIMIT 8"""
    ).fetchall()
    return {
        "status_counts": status_counts,
        "total": total,
        "confirmed": status_counts.get("confirmed", 0),
        "processing": status_counts.get("processing", 0),
        "failed": status_counts.get("failed", 0),
        "cancelled": status_counts.get("cancelled", 0),
        "per_room": per_room,
        "per_building": per_building,
        "monthly": monthly,
        "top_users": top_users,
    }


@bp.route("/admin/reports")
@roles_required("sarpras", "superadmin")
def admin_reports():
    return render_template("admin_reports.html", report=report_data(get_db()))


@bp.route("/admin/reports.csv")
@roles_required("sarpras", "superadmin")
def admin_reports_csv():
    rows = get_db().execute(
        """SELECT r.kode_booking, r.tanggal, r.mulai, r.selesai, r.status,
                  u.nama AS pemohon, u.nim_nip, u.prodi, rm.kode AS kode_ruang,
                  rm.nama AS nama_ruang, rm.gedung, r.keperluan, r.jumlah_peserta,
                  r.created_at, r.approved_at
           FROM reservations r
           JOIN users u ON u.id = r.user_id
           JOIN rooms rm ON rm.id = r.room_id
           ORDER BY r.tanggal, r.mulai"""
    ).fetchall()
    stream = io.StringIO()
    writer = csv.writer(stream)
    writer.writerow([
        "Kode Booking", "Tanggal", "Mulai", "Selesai", "Status", "Pemohon",
        "NIM/NIK", "Program Studi", "Kode Ruang", "Ruang", "Gedung",
        "Keperluan", "Peserta", "Diajukan", "Disetujui",
    ])
    for row in rows:
        writer.writerow([row[key] for key in row.keys()])
    response = Response(stream.getvalue(), mimetype="text/csv; charset=utf-8")
    response.headers["Content-Disposition"] = (
        f"attachment; filename=laporan-reservasi-idb-{date.today().isoformat()}.csv"
    )
    return response


@bp.route("/admin/audit")
@roles_required("sarpras", "superadmin")
def admin_audit():
    logs = get_db().execute(
        """SELECT a.*, u.nama AS actor, u.role AS actor_role,
                  r.kode_booking, rm.kode AS room_kode
           FROM audit_logs a
           LEFT JOIN users u ON u.id = a.actor_id
           LEFT JOIN reservations r ON r.id = a.reservation_id
           LEFT JOIN rooms rm ON rm.id = r.room_id
           ORDER BY a.id DESC LIMIT 300"""
    ).fetchall()
    return render_template("admin_audit.html", logs=logs)


@bp.route("/admin/rooms")
@roles_required("sarpras", "superadmin")
def admin_rooms():
    rooms = get_db().execute(
        "SELECT * FROM rooms ORDER BY gedung, lantai, kode"
    ).fetchall()
    return render_template("admin_rooms.html", rooms=rooms)


@bp.post("/admin/rooms/<int:room_id>")
@roles_required("sarpras", "superadmin")
def admin_update_room(room_id):
    db = get_db()
    room = db.execute("SELECT * FROM rooms WHERE id = ?", (room_id,)).fetchone()
    if not room:
        abort(404)
    kapasitas = request.form.get("kapasitas", type=int) or room["kapasitas"]
    if kapasitas < 1:
        flash("Kapasitas minimal 1 orang.", "danger")
        return redirect(url_for("main.admin_rooms"))
    butuh_dokumen = 1 if request.form.get("butuh_dokumen") else 0
    butuh_approval = 1 if request.form.get("butuh_approval") else 0
    terbatas = 1 if request.form.get("terbatas") else 0
    aktif = 1 if request.form.get("aktif") else 0

    changes = []
    for label, old, new in (
        ("kapasitas", room["kapasitas"], kapasitas),
        ("butuh_dokumen", room["butuh_dokumen"], butuh_dokumen),
        ("butuh_approval", room["butuh_approval"], butuh_approval),
        ("terbatas", room["terbatas"], terbatas),
        ("aktif", room["aktif"], aktif),
    ):
        if old != new:
            changes.append(f"{label}: {old} -> {new}")

    user = current_user()
    with _write_lock:
        try:
            db.execute("BEGIN IMMEDIATE")
            db.execute(
                """UPDATE rooms SET kapasitas = ?, butuh_dokumen = ?, butuh_approval = ?,
                   terbatas = ?, aktif = ? WHERE id = ?""",
                (kapasitas, butuh_dokumen, butuh_approval, terbatas, aktif, room_id),
            )
            log_audit(
                db, None, user["id"], "room_updated",
                f"Aturan ruang {room['kode']} diubah. " + ("; ".join(changes) or "Tanpa perubahan nilai."),
            )
            db.commit()
        except Exception:
            db.rollback()
            raise
    flash(f"Pengaturan ruang {room['kode']} disimpan.", "success")
    return redirect(url_for("main.admin_rooms"))


# ---------------------------------------------------------------------------
# Error handlers
# ---------------------------------------------------------------------------
@bp.app_errorhandler(403)
def forbidden(_error):
    return render_template("error.html", code=403,
                           title="Akses ditolak",
                           message="Anda tidak memiliki hak untuk membuka halaman atau aksi ini."), 403


@bp.app_errorhandler(404)
def not_found(_error):
    return render_template("error.html", code=404,
                           title="Halaman tidak ditemukan",
                           message="Tautan yang Anda buka tidak tersedia atau sudah dipindahkan."), 404


@bp.app_errorhandler(413)
def too_large(_error):
    flash("Dokumen terlalu besar. Maksimal 8 MB.", "danger")
    return redirect(request.referrer or url_for("main.index"))


@bp.app_errorhandler(500)
def server_error(_error):
    db = g.get("db")
    if db is not None:
        db.rollback()
    return render_template("error.html", code=500,
                           title="Terjadi gangguan",
                           message="Sistem belum dapat memproses permintaan. Silakan coba lagi."), 500


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------
def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY", "idb-space-dev-secret-change-me"),
        DATABASE=os.environ.get("DATABASE_PATH", DEFAULT_DB),
        UPLOAD_DIR=os.environ.get("UPLOAD_DIR", DEFAULT_UPLOADS),
        MAX_CONTENT_LENGTH=MAX_DOC_BYTES,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
    )
    if test_config:
        app.config.update(test_config)

    os.makedirs(os.path.dirname(app.config["DATABASE"]), exist_ok=True)
    os.makedirs(app.config["UPLOAD_DIR"], exist_ok=True)
    app.teardown_appcontext(close_db)
    app.register_blueprint(bp)

    with app.app_context():
        init_db(app)

    return app


app = create_app()


if __name__ == "__main__":
    app.run(
        host=os.environ.get("HOST", "0.0.0.0"),
        port=int(os.environ.get("PORT", "8080")),
        debug=os.environ.get("FLASK_DEBUG") == "1",
    )
