# Runbook — Clean-Slate Import (RNF04)

## Kapan menjalankan ini

Hanya ketika sistem sudah selesai dan data sejarah 48 EC (2026) benar-benar harus masuk ke
database. Sebelum itu, database berisi data uji coba — dibiarkan.

## Perintahnya

```bash
bash scripts/import_history_clean_slate.sh
```

Path CSV default: `~/Documents/ec_cleaning/ec_clean.csv`. Untuk sumber lain:

```bash
bash scripts/import_history_clean_slate.sh /path/ec_clean.csv
```

## Langkah yang terjadi otomatis

| # | Aksi | Konfirmasi |
|---|---|---|
| 1 | Backup database → `backups/backup_<tanggal>.db` | selalu, tanpa tanya |
| 2 | Tampilkan kondisi DB saat ini (`EC`, `DocumentVersion`) | read-only |
| 3 | Hapus semua EC uji coba | tanya, ketik `ya` |
| 4 | Dry-run: laporan 48 baris → tanya tulis `--commit` | tanya, ketik `ya` |
| 5 | Tulis 48 EC → verifikasi: `EC.objects.count() == 48`, `next_ec_number(2026) == 49` | otomatis |

Verifikasi gagal → skrip berteriak dan mencetak perintah restore backup:

```bash
cp backups/backup_<tanggal>.db db.sqlite3
```

## Prasyarat sebelum dijalankan

1. Kode import sudah ada di `main` (PR `feat/historical-import` sudah digabung).
2. File `ec_clean.csv` ada dan 5 kolom kontraknya pas: `year, number_sequence, reference,
   description, status` (regenerasi lewat notebook bila file lama berubah).
3. Tidak ada pekerjaan penting di database yang belum terbackup.

## Angka yang tertulis di skrip (perlu diupdate saat CSV berubah)

- Target baris: **48** (dibloc `=== Verification ===` dalam skrip).
- Nomor EC berikutnya: **49**.

Kalau file CSV bertambah/berkurang barisnya atau tahun data membedakannya, dua angka itu harus
diupdate juga di `scripts/import_history_clean_slate.sh` (blok `=== Verification ===`).

## Sumber data lain (ditunda)

- `~/Documents/ec_cleaning/releases_clean.csv` (27 Release unik) dan
  `ec_release_map.csv` (46 relasi EC↔Release) — arsip untuk **Babak 2** (impor Release),
  ditangani per spec `.opencode/specs/RNF04_IMPORT.md` → *Deferred → Babak 2*.
