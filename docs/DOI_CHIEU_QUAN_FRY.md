# ĐỐI CHIẾU HỆ SỐ CÔNG THỨC QUAN–FRY (CHƯA XÁC NHẬN TỰ ĐỘNG)

> **Lưu ý quan trọng:** Trợ lí phần mềm **không có bản PDF bài báo gốc**, nên 10 hệ số dưới đây trong `core/optics.py` (`HE_SO_QUAN_FRY_TRONG_MA`) **chưa được xác nhận** với bài gốc. Người dùng (học sinh/GVHD) bắt buộc phải tự tra bài gốc, điền cột trống rồi chạy công cụ kiểm tra trước khi đưa vào báo cáo KHKT.

## 1. Thông tin bài báo & điều kiện áp dụng

- **Tài liệu gợi ý cần tự tra và kiểm chứng lại đầy đủ trích dẫn (tập, số trang, DOI):**
  Quan & Fry, *Applied Optics*, 1995 (người dùng phải tự mở bài gốc để kiểm tra tên đầy đủ, năm, tập, trang và công thức gốc).
- **Dải hiệu lực được khai báo trong mã (`core/optics.py`):**
  - Nhiệt độ: `0 – 30 °C`
  - Độ mặn: `0 – 35 ‰`
  - Bước sóng ánh sáng: `400 – 700 nm`
- **Lưu ý quy đổi chiết suất:** Công thức `chiet_suat_quan_fry` trả về giá trị chiết suất trực tiếp dùng trong chuỗi Snell của `core/optics.py` (không nhân thêm `n_khong_khi`). Hãy kiểm tra kĩ bài gốc xem bộ hệ số tương ứng là chiết suất tuyệt đối hay chiết suất tương đối trong không khí chuẩn (nếu khác định nghĩa phải thống nhất công thức trong `core/optics.py`, không tự nhân ghép tùy tiện).

---

## 2. Bảng đối chiếu 10 hệ số `a0…a9`

Số hạng công thức trong `core/optics.py`:

$$n(S, T, \lambda) = a_0 + (a_1 + a_2 T + a_3 T^2) S + a_4 T^2 + \frac{a_5 + a_6 S + a_7 T}{\lambda} + \frac{a_8}{\lambda^2} + \frac{a_9}{\lambda^3}$$

| Hệ số | Giá trị hiện có trong `core/optics.py` | Giá trị trong bài gốc (người dùng điền) | Trang / Bảng trong bài gốc | Khớp? [ ] |
|---|---|---|---|---|
| `a0` | `1.31405` | | | [ ] |
| `a1` | `0.0001779` (`1.779e-4`) | | | [ ] |
| `a2` | `-1.05e-06` (`-1.05e-6`) | | | [ ] |
| `a3` | `1.6e-08` (`1.6e-8`) | | | [ ] |
| `a4` | `-2.02e-06` (`-2.02e-6`) | | | [ ] |
| `a5` | `15.868` | | | [ ] |
| `a6` | `0.01155` | | | [ ] |
| `a7` | `-0.00423` | | | [ ] |
| `a8` | `-4382.0` | | | [ ] |
| `a9` | `1145500.0` (`1.1455e6`) | | | [ ] |

---

## 3. Cách kiểm tra tự động và gỡ cảnh báo trên giao diện web

1. Tạo một file CSV (ví dụ `data/doi_chieu_quan_fry_nguoi_dung.csv`) gồm 3 cột:
   ```csv
   he_so,gia_tri_bai_goc,trang_bang
   a0,1.31405,Eq.(1) p.xxxx
   a1,1.779e-4,Eq.(1) p.xxxx
   ...
   ```
2. Chạy kiểm tra (chỉ in bảng sai khác, chưa ghi file xác nhận):
   ```powershell
   .\.venv\Scripts\python.exe scripts/kiem_tra_quan_fry.py --csv data/doi_chieu_quan_fry_nguoi_dung.csv
   ```
3. Nếu toàn bộ 10 hệ số đều khớp (`mã thoát 0`) và bạn đã điền **đầy đủ cột `trang_bang` cho tất cả 10 dòng**, để lưu xác nhận cục bộ cần truyền thêm `--nguoi-doi-chieu`, `--trich-dan` (và tùy chọn `--nguoi-xac-nhan-2` cho GVHD/người kiểm chéo):
   ```powershell
   .\.venv\Scripts\python.exe scripts/kiem_tra_quan_fry.py `
     --csv data/doi_chieu_quan_fry_nguoi_dung.csv `
     --luu-xac-nhan `
     --nguoi-doi-chieu "Tên Học Sinh" `
     --nguoi-xac-nhan-2 "Tên Giáo Viên HD" `
     --trich-dan "Quan, X., & Fry, E. S. (1995), Applied Optics, ..."
   ```
   Lệnh trên tạo file cục bộ `data/xac_nhan_quan_fry.json`. Nếu giá trị bạn nhập chép y hệt từ mã hoặc từ tài liệu hướng dẫn thì **không phải đối chiếu bài gốc**. Nếu thiếu `trang_bang`, thiếu người/trích dẫn hoặc lệch hệ số nào, script thoát mã `1` và **không** tạo file xác nhận.
