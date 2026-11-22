# ĐỐI CHIẾU HỆ SỐ CÔNG THỨC QUAN–FRY (CHƯA XÁC NHẬN TỰ ĐỘNG)

> **Lưu ý quan trọng:** Trợ lí phần mềm **không có bản PDF bài báo gốc**, nên 10 hệ số `a0..a9` trong `core/optics.py` (`HE_SO_QUAN_FRY_TRONG_MA`) **chưa được xác nhận** với bài gốc. Các giá trị hiện dùng nằm trong `core/optics.py`, **KHÔNG đọc hay chép từ mã nguồn khi đối chiếu**; người dùng (học sinh/GVHD) bắt buộc phải đọc trực tiếp từ bài báo gốc Quan & Fry (*Applied Optics*, 1995), điền số liệu và vị trí trang/bảng vào CSV rồi chạy công cụ kiểm tra trước khi đưa vào báo cáo KHKT.

## 1. Thông tin bài báo & điều kiện áp dụng

- **Tài liệu cần tự tra và kiểm chứng lại đầy đủ trích dẫn (tác giả, năm, tạp chí, tập, số trang/DOI):**
  Quan & Fry, *Applied Optics*, 1995 (tự mở bản gốc bài báo để ghi đầy đủ trích dẫn khi chạy `--luu-xac-nhan`).
- **Dải hiệu lực được khai báo trong mã (`core/optics.py`):**
  - Nhiệt độ: `0 – 30 °C`
  - Độ mặn: `0 – 35 ‰`
  - Bước sóng ánh sáng: `400 – 700 nm`
- **Lưu ý quy đổi chiết suất:** Công thức `chiet_suat_quan_fry` trả về giá trị chiết suất trực tiếp dùng trong chuỗi Snell của `core/optics.py` (không nhân thêm `n_khong_khi`). Hãy kiểm tra kĩ bài gốc xem bộ hệ số tương ứng là chiết suất tuyệt đối hay chiết suất tương đối trong không khí chuẩn (nếu khác định nghĩa phải thống nhất công thức trong `core/optics.py`, không tự nhân ghép tùy tiện).

---

## 2. Bảng đối chiếu 10 hệ số `a0…a9`

Số hạng công thức trong `core/optics.py`:

$$n(S, T, \lambda) = a_0 + (a_1 + a_2 T + a_3 T^2) S + a_4 T^2 + \frac{a_5 + a_6 S + a_7 T}{\lambda} + \frac{a_8}{\lambda^2} + \frac{a_9}{\lambda^3}$$

> **Hướng dẫn:** Giá trị hiện dùng nằm trong `core/optics.py`, **KHÔNG** đọc từ mã nguồn khi đối chiếu; hãy đọc trực tiếp từ bài báo gốc Quan & Fry (1995) rồi điền vào cột bên dưới.

| Hệ số | Giá trị trong bài gốc (tự đọc và điền) | Trang / Bảng trong bài gốc (ví dụ `tr. 3478, Bảng 2`) | Khớp? [ ] |
|---|---|---|---|
| `a0` | | | [ ] |
| `a1` | | | [ ] |
| `a2` | | | [ ] |
| `a3` | | | [ ] |
| `a4` | | | [ ] |
| `a5` | | | [ ] |
| `a6` | | | [ ] |
| `a7` | | | [ ] |
| `a8` | | | [ ] |
| `a9` | | | [ ] |

---

## 3. Cách kiểm tra tự động và lưu xác nhận do người dùng tự khai

1. Tạo một file CSV (ví dụ `data/doi_chieu_quan_fry_nguoi_dung.csv`) gồm đúng 3 cột `he_so,gia_tri_bai_goc,trang_bang` với các giá trị bạn đọc trực tiếp từ bài gốc:
   ```csv
   he_so,gia_tri_bai_goc,trang_bang
   a0,<gia_tri_doc_tu_bai_goc>,tr. 3478 Bảng 2
   a1,<gia_tri_doc_tu_bai_goc>,tr. 3478 Bảng 2
   ...
   ```
2. Chạy kiểm tra (chỉ in bảng sai khác, chưa ghi file xác nhận):
   ```powershell
   .\.venv\Scripts\python.exe scripts/kiem_tra_quan_fry.py --csv data/doi_chieu_quan_fry_nguoi_dung.csv
   ```
3. Khi 10/10 hệ số khớp, để lưu file xác nhận `data/xac_nhan_quan_fry.json`, bắt buộc đáp ứng:
   - Mọi dòng `trang_bang` (`a0..a9`) dài `>= 3` ký tự, có ít nhất 1 chữ số và không dùng chữ giữ chỗ vô nghĩa (`x`, `na`, `n/a`, `-`, `...`).
   - `--trich-dan` dài `>= 25` ký tự và chứa năm xuất bản 4 chữ số (`19xx` hoặc `20xx`).
   - `--nguoi-doi-chieu` và `--nguoi-xac-nhan-2` (sau khi bỏ dấu tiếng Việt, hạ chữ thường, gom khoảng trắng) đều dài `>= 3` ký tự và phải khác nhau.
   ```powershell
   .\.venv\Scripts\python.exe scripts/kiem_tra_quan_fry.py `
     --csv data/doi_chieu_quan_fry_nguoi_dung.csv `
     --luu-xac-nhan `
     --nguoi-doi-chieu "Nguyen Van An" `
     --nguoi-xac-nhan-2 "Tran Thi Binh (GVHD)" `
     --trich-dan "Quan, X., & Fry, E. S. (1995), Applied Optics 34(18), tr. 3477-3483"
   ```
   *(Giới hạn trung thực: Xác nhận do người dùng tự khai, hệ thống không kiểm chứng độc lập nội dung bài báo gốc.)*
