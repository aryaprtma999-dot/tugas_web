# Panduan Skill OpenCode — IDB Bali Room Booking

Dokumen ini mencatat skill yang terpasang untuk proyek **Sistem Peminjaman Ruangan IDB Bali**, lokasi pemasangannya, cara memakai, dan cara memverifikasi bahwa OpenCode benar-benar memuatnya.

## Status verifikasi

Diperiksa pada lingkungan kerja ini:

| Skill | Lokasi aktif | Status |
| --- | --- | --- |
| UI/UX Pro Max | `~/.opencode/skills/ui-ux-pro-max` dan `~/.config/opencode/skills/ui-ux-pro-max` | Terbaca oleh agent; script `search.py` berjalan |
| Vercel Agent Browser | `~/.config/opencode/skills/agent-browser` | Terbaca; CLI `agent-browser 0.39.4` tersedia |
| Impeccable | `~/.config/opencode/skills/impeccable` | Terbaca; launcher skill tersedia |
| OpenCode Skills (osmontero) | `~/.config/opencode/skills/*` (33 skill) | Terbaca; termasuk `designing-frontend-interfaces`, `designing-user-experience`, `building-accessible-interfaces`, `reviewing-interface-quality` |

Konfigurasi global OpenCode ada di `~/.config/opencode/opencode.jsonc` dan tidak diubah. Proyek ini memakai skill global; belum ada folder skill khusus proyek.

## Cara OpenCode menemukan skill

OpenCode memindai folder skill dan membaca frontmatter `name` + `description` pada setiap `SKILL.md`. Skill otomatis muncul di daftar `available_skills` dan dipanggil dengan tool `skill`.

Lokasi yang dipakai:

```text
~/.config/opencode/skills/<nama-skill>/SKILL.md   # global, semua proyek
~/.opencode/skills/<nama-skill>/SKILL.md           # koleksi global tambahan
<project>/.opencode/skills/<nama-skill>/SKILL.md  # opsional, khusus proyek ini
```

## Perintah instalasi resmi (untuk pemasangan ulang)

```bash
# UI/UX Pro Max — CLI resmi
npm install -g ui-ux-pro-max-cli
uipro init --ai opencode
uipro update

# Vercel Agent Browser
npm install -g agent-browser
agent-browser install

# Impeccable — installer resmi
npx impeccable install --providers=opencode
npx impeccable update

# OpenCode Skills (osmontero)
# Salin folder skill dari repo ke ~/.config/opencode/skills/ atau ~/.opencode/skills/
```

Catatan: jangan menjalankan installer yang menimpa konfigurasi global tanpa memeriksa `--dry-run` atau `--help`. Skill yang sudah ada tidak perlu dipasang ulang.

## Cara memakai

### UI/UX Pro Max

```bash
python3 ~/.opencode/skills/ui-ux-pro-max/scripts/search.py \
  "campus room booking dashboard institutional teal orange" \
  --design-system -p "IDB Space"

python3 ~/.opencode/skills/ui-ux-pro-max/scripts/search.py \
  "form validation error focus accessibility" --domain ux
```

Gunakan hasil pencarian sebagai rekomendasi, lalu sesuaikan dengan warna resmi IDB Bali (`#0A7386` teal, `#EF9018` oranye) dan aturan proyek.

### Vercel Agent Browser

```bash
agent-browser open http://127.0.0.1:8080/
agent-browser set viewport 390 844
agent-browser screenshot /tmp/idb-mobile.png
agent-browser snapshot
agent-browser close --all
```

Dipakai untuk smoke test login, pemesanan, kalender, dashboard admin, dan tampilan mobile.

### Impeccable

```bash
npx impeccable install --providers=opencode
npx impeccable update
```

Setelah terpasang, panggil skill `impeccable` dari OpenCode. Fokusnya audit visual, hierarki, tipografi, warna, motion, dan kualitas UI.

### OpenCode Skills

Panggil lewat tool `skill`, misalnya:

- `designing-frontend-interfaces` — arah visual dan tipografi.
- `designing-user-experience` — state kosong/loading/error dan formulir.
- `building-accessible-interfaces` — label, fokus, ARIA, kontras.
- `reviewing-interface-quality` — audit UI sebelum rilis.

## Verifikasi cepat

```bash
# Daftar folder skill global
ls ~/.config/opencode/skills

# Cek CLI browser
agent-browser --version

# Cek script UI/UX Pro Max
python3 ~/.opencode/skills/ui-ux-pro-max/scripts/search.py "teal orange dashboard" --domain color -n 2

# Cek skill terbaca OpenCode
# Di sesi OpenCode, skill muncul pada daftar available_skills dan dapat dipanggil dengan tool skill.
```

## Troubleshooting

- **Skill tidak muncul:** pastikan file bernama tepat `SKILL.md`, berada di folder skill, dan frontmatter berisi `name` serta `description`.
- **Duplikat skill:** OpenCode dapat memuat skill global dan proyek. Jika nama sama, gunakan satu sumber saja agar tidak ambigu.
- **Agent Browser gagal membuka halaman lokal:** pastikan server berjalan di `127.0.0.1` dan tidak ada blokir jaringan privat.
- **UI/UX Pro Max error:** butuh Python 3; jalankan `python3 --version` lalu ulangi perintah.
