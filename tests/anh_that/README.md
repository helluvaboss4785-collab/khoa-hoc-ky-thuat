# Thư mục kiểm thử hồi quy bằng ảnh chụp thật (`tests/anh_that/`)

Hiện tại dự án **chưa có ảnh thật từ thiết bị phần cứng**, nên `test_hoi_quy_anh_that` trong [test_anh_that.py](../test_anh_that.py) sẽ tự động `skip` với lí do `"chưa có ảnh thật"`.

## Cách bổ sung ảnh thật để kích hoạt kiểm thử hồi quy
1. Chụp ảnh từ thiết bị thật theo đúng quy trình trong `HUONG_DAN_NGUOI_DUNG.md` (khóa phơi sáng AE/AF, giữ máy cố định, tránh bão hòa vạch laser).
2. Chép các file ảnh (`.jpg` / `.png`) vào ngay thư mục `tests/anh_that/`.
3. Tạo file `tests/anh_that/nhan_chuan.csv` mã hóa UTF-8 gồm các cột:
   - Bắt buộc: `ten_file,delta_y_chuan_px,dung_sai_px`
   - Tùy chọn: `roi_tc,roi_mau` (chuỗi 4 số `"y0;y1;x0;x1"` nếu muốn cố định vùng ROI cho ảnh đó).
4. Chạy lại `python -m pytest tests/test_anh_that.py -v` để xác nhận thuật toán đạt sai số nằm trong dung sai trên ảnh thiết bị thật.
5. Để biến bộ ảnh thực nghiệm thành file CSV hiệu chuẩn nạp vào phần mềm, chạy công cụ hàng loạt:
   ```bash
   python scripts/xu_ly_thu_muc_anh.py --thu-muc <thu_muc_anh> --nguon THUC_TE --metadata <metadata.csv>
   ```
