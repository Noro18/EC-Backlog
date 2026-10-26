# Runbook — Clean-Slate Import (RNF04)

## Kapan menjalankan ini

Hanya ketika sistem sudah selesai dan data sejarah 48 EC (2026) benar-benar harus masuk ke
database. Sebelum itu, database berisi data uji coba — dibiarkan.

## Perintahnya

```bash
bash scripts/import_history_clean_slate.sh
```

Path CSV default: `~/Documents/ec_cleaning/` → `ec_clean.csv`, `releases_clean.csv`,
`ec_release_map.csv`. Untuk sumber lain:

```bash
bash scripts/import_history_clean_slate.sh /path/ec_clean.csv /path/releases_clean.csv /path/ec_release_map.csv
```

## Langkah yang terjadi otomatis

| # | Aksi | Konfirmasi |
|---|---|---|
| 1 | Backup database → `backups/backup_<tanggal>.db` | selalu, tanpa tanya |
| 2 | Tampilkan kondisi DB saat ini (`EC`, `Release`, `DocumentVersion`) | read-only |
| 3 | Hapus semua EC & Release uji coba | tanya, ketik `ya` |
| 4 | Dry-run EC: laporan 48 baris → tanya tulis `--commit` | tanya, ketik `ya` |
| 5 | Dry-run Release: laporan 27 baris (25 Release unik) + 46 relasi → tanya tulis `--commit` | tanya, ketik `ya` |
| 6 | Verifikasi angka akhir | otomatis |

Angka yang diverifikasi langkah 6:

- `EC.objects.count() == 48`
- `next_ec_number(2026) == 49`
- `Release.objects.count() == 25`
- EC tergantung Release: **46**, tanpa Release: **2**

Verifikasi gagal → skrip berteriak dan mencetak perintah restore backup:

```bash
cp backups/backup_<tanggal>.db db.sqlite3
```

## Prasyarat sebelum dijalankan

1. Kode import sudah ada di `main` (PR `feat/historical-import` sudah digabung).
2. Tiga file CSV ada dan kolomnya sesuai kontrak — regenerasi lewat notebook bila file lama
   berubah: `ec_clean.csv` (`year, number_sequence, reference, description, status`),
   `releases_clean.csv` (`year_release, number_sequence_release, go_live`),
   `ec_release_map.csv` (`year, number_sequence, year_release, number_sequence_release`).
3. Tidak ada pekerjaan penting di database yang belum terbackup.

## Angka yang tertulis di skrip (perlu diupdate saat CSV berubah)

- 48 (baris EC), 49 (nomor EC berikutnya), 25 (Release unik), 46/2 (EC tergantung / bebas)
- Semuanya di blok `=== Verification ===` dalam `scripts/import_history_clean_slate.sh`.

## Babak 2 (impor Release) — sudah aktif

Perintah `import_releases` (dua file: arsip Release + peta EC↔Release) sudah jadi bagian dari
skrip di atas. Aturannya di spec `.opencode/specs/RNF04_IMPORT.md` → *Deferred → Babak 2*:
kode `TT_ON_YYYY-NNN`, tanggal go-live terakhir yang valid (boleh kosong), kapasitas tidak
dipakai untuk data historis, status Release mengikuti status EC yang dilekatkan.
