# Deployment Plan: Ticketing API (Track C, Serverless)

Target: Sandbox Environment AWS Academy Cloud Foundations, region us-east-1. Estimasi waktu 30 sampai 45 menit.
Tanda 📸 berarti ambil screenshot dan simpan ke `docs/evidence/` dengan nama file yang tertera.

## 0. Persiapan

1. Login AWS Academy, buka course AWS Academy Cloud Foundations, masuk ke Modules, lalu buka Sandbox Environment.
2. Klik Start Lab dan tunggu sampai indikator AWS berwarna hijau.
3. Klik AWS untuk membuka console. Pastikan region di kanan atas adalah N. Virginia (us-east-1).
4. 📸 `00-sandbox.png`: halaman sandbox dengan status hijau dan budget yang terlihat.

## 1. Bucket S3

1. Console, buka S3, lalu Create bucket.
2. Bucket name harus unik secara global, misalnya `ticketing-535223-nabil`.
3. Biarkan Block all public access tetap aktif dan enkripsi default (SSE-S3).
4. Create bucket.
5. 📸 `01-s3-bucket.png`: detail bucket (nama, region, Block Public Access aktif).

## 2. Fungsi Lambda

1. Console, buka Lambda, lalu Create function dan pilih Author from scratch.
   - Function name: `ticket-api`
   - Runtime: Python 3.12
   - Execution role: Use an existing role, lalu pilih role yang tersedia (misalnya `LabRole`). Jika pilihan ini tidak ada, gunakan opsi default yang diizinkan sandbox.
2. Create function.
3. Di tab Code, ganti seluruh isi `lambda_function.py` dengan isi `src/lambda_function.py`, lalu Deploy.
4. Configuration, Environment variables, Edit, tambahkan `BUCKET_NAME` dengan nama bucket dari langkah 1, lalu Save.
5. Configuration, General configuration, ubah Timeout menjadi 10 detik, lalu Save.
6. 📸 `02-lambda-function.png`: overview fungsi (runtime dan execution role).

### 2a. Pengujian di console Lambda

1. Tab Test, Create new event, beri nama `create-ticket`, tempel isi `tests/events/create-ticket.json`, lalu Test.
2. Hasil yang diharapkan: `statusCode: 201` dan body berisi `ticketId`. Salin nilai `ticketId`.
3. 📸 `03-lambda-test.png`: hasil eksekusi yang sukses.
4. Opsional: uji `list-tickets.json` dan `get-ticket.json` (ganti `GANTI_DENGAN_TICKET_ID` dengan ticketId tadi).
5. Buka bucket S3, masuk ke folder `tickets/`, dan pastikan file `{ticketId}.json` muncul.
   📸 `04-s3-objects.png`.

Jika muncul `AccessDenied` saat menulis ke S3, berarti execution role belum mempunyai izin S3. Catat pesan errornya dan cek role lain yang tersedia di sandbox.

## 3. Lambda Function URL

1. Di halaman fungsi `ticket-api`, buka Configuration, Function URL, lalu Create function URL.
2. Auth type: NONE. Biarkan CORS nonaktif.
3. Save, lalu salin Function URL (contoh: `https://abcdefg.lambda-url.us-east-1.on.aws/`).
4. 📸 `05-function-url.png`: konfigurasi Function URL.

## 4. Pengujian konektivitas (end-to-end)

Dari terminal lokal (macOS atau Linux):

```bash
./scripts/test_api.sh https://<url-id>.lambda-url.us-east-1.on.aws
```

Hasil yang diharapkan: CREATE menghasilkan 201 dan `ticketId`, READ ALL menghasilkan `count` minimal 1, READ ONE menampilkan tiket, UPDATE mengubah `status` menjadi `closed`, DELETE menampilkan pesan berhasil, dan VERIFY menghasilkan `HTTP 404`.

📸 `06-curl-test.png`: seluruh output terminal.

## 5. Monitoring

1. Lambda, `ticket-api`, Monitor, View CloudWatch logs, lalu buka log stream terbaru.
2. 📸 `07-cloudwatch-logs.png`: entri log seperti `{"method": "POST", "path": "/tickets"}`.

## 6. Pembersihan dan budget

- Lambda, Function URL, dan S3 tidak ditagih per jam, jadi aman dibiarkan untuk minggu berikutnya.
- Setelah selesai, klik End Lab.
- Jangan membuat EC2, RDS, NAT Gateway, atau Load Balancer untuk track ini karena ditagih per jam walaupun tidak dipakai.
- Untuk menghapus semua resource: hapus Function URL dan fungsi Lambda, kosongkan lalu hapus bucket S3, dan hapus log group `/aws/lambda/ticket-api` di CloudWatch.

## Troubleshooting

| Gejala | Penyebab dan solusi |
|---|---|
| `AccessDenied` saat membuat Lambda | Pilih execution role yang sudah ada, jangan membuat role baru |
| Lambda mengembalikan 500 dan log berisi `AccessDenied` | Role tidak punya izin S3, cek role lain yang tersedia |
| Lambda mengembalikan 500 dan log berisi `NoSuchBucket` | Nilai env `BUCKET_NAME` salah |
| Response `Endpoint '...' tidak dikenal` | Path salah, gunakan `/tickets` atau `/tickets/{id}` |
| Function URL mengembalikan `Forbidden` | Auth type bukan NONE, atau Function URL diblokir sandbox. Gunakan pengujian di console Lambda sebagai bukti |
