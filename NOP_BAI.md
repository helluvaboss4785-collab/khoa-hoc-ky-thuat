# HƯỚNG DẪN ĐÓNG GÓI SẠCH ĐỂ NỘP BÀI KHKT (`W4`)

> **CẢNH BÁO QUAN TRỌNG:**  
> **KHÔNG nén cả thư mục. Chạy dong_goi.bat** (trên Windows) hoặc `./dong_goi.sh` (trên macOS/Linux).  
> Việc bấm chuột phải → *Compress/Zip* cả thư mục dự án sẽ kéo theo `.venv` (hàng trăm MB), `.git`, file cơ sở dữ liệu `*.db*` cá nhân và ảnh thử nghiệm tạm.

---

## 1. Cách tạo gói `.zip` sạch trong 1 bước

- **Windows:** Nháy đúp hoặc chạy trong terminal tại thư mục gốc dự án:
  ```bat
  dong_goi.bat
  ```
- **macOS / Linux:**
  ```bash
  chmod +x dong_goi.sh
  ./dong_goi.sh
  ```
- **Hoặc gọi trực tiếp qua Python:**
  ```bash
  python scripts/dong_goi.py --kiem-tra
  ```

Mặc định, tệp `khkt_do_man_vi_sai_<YYYYMMDD_HHMMSS>.zip` được lưu ở **thư mục cha (`..`)** nằm ngoài thư mục dự án để tránh nhầm lẫn khi nộp bài. Nếu truyền `--out <đường_dẫn>`, tránh đặt đầu ra nằm bên trong thư mục dự án.

---

## 2. Những gì tự động được GIỮ LẠI và LOẠI TRỪ

- **Tự động GIỮ LẠI (nếu nhóm đã tạo xong khi làm thực nghiệm):**
  - Toàn bộ mã nguồn (`core/`, `sim/`, `app/`, `scripts/`, `tests/`), cấu hình (`config.yaml`), tài liệu (`docs/`, `README.md`, `BAO_CAO_THAY_DOI.md`).
  - Biểu mẫu trống `data/mau_*.csv`.
  - Các tệp xác nhận/nhật kí nguồn do nhóm tự tạo: `data/xac_nhan_quan_fry.json`, `data/hieu_chuan_nhiet_ke.json`, `data/so_anh_da_xu_ly.csv`.
- **Tự động LOẠI TRỪ & KIỂM TRA `< 20 MB`:**
  - `.venv/`, `venv/`, `env/`, `.git/`, `__pycache__/`, `.pytest_cache/`
  - `*.db*` (kể cả `data/nhat_ki_do.db`, `-wal`, `-shm`)
  - Mọi file `*.zip` cũ
  - Sổ theo dõi riêng ảnh mô phỏng `outputs/so_anh_mo_phong.csv` (chỉ phục vụ chống nhầm nguồn trên máy phát triển).

Khi kết thúc, công cụ in **`KIỂM TRA ĐẠT`** nếu gói hợp lệ và nhỏ hơn `20 MB`.
