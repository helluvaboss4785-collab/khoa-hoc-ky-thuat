# HỆ THỐNG ĐO ĐỘ MẶN NƯỚC BẰNG KHÚC XẠ LASER & CAMERA ĐIỆN THOẠI
## Cấu trúc vi sai hai ngăn quang học khử trôi

> **Dự án dự thi Khoa học Kỹ thuật (KHKT) dành cho học sinh THPT**  
> *Lĩnh vực: Kỹ thuật Môi trường / Phần mềm Hệ thống & Vật lí Ứng dụng*  
> **Hướng dẫn sử dụng ngắn gọn cho người nuôi:** Xem [`HUONG_DAN_NGUOI_DUNG.md`](HUONG_DAN_NGUOI_DUNG.md).

---

## 1. NGUYÊN LÍ VẬT LÍ & CÔNG NGHỆ (Dành cho học sinh thuyết minh phỏng vấn)

### 1.1. Hiện tượng khúc xạ qua lăng kính hai ngăn
- **Cấu hình lăng kính**: Lăng kính rỗng tam giác có góc đỉnh $A = 40^\circ$ (cấu hình linh hoạt từ $25^\circ - 47^\circ$), chia làm hai ngăn độc lập:
  1. *Ngăn tham chiếu*: Chứa nước cất tinh khiết ($S = 0\text{ ‰}$), được niêm phong kín.
  2. *Ngăn mẫu*: Chứa nước cần đo độ mặn ($S\text{ ‰}$).
- **Đường đi của tia sáng**: Module laser vạch ($\lambda = 650\text{ nm}$, công suất an toàn $\le 1\text{ mW}$) chiếu vuông góc với mặt vào của lăng kính $\implies$ tia sáng **không bị lệch** ở mặt vào.
- Tại mặt đáy nghiêng thứ hai, tia sáng đi từ môi trường chất lỏng (chiết suất $n$) ra không khí ($n_{kk} \approx 1{,}000$) theo **định luật khúc xạ Snell chính xác** (không dùng xấp xỉ lăng kính mỏng):
  $$\sin(\theta_{ra}) = n \cdot \sin(A)$$
  Góc lệch tổng cộng của tia sáng:
  $$\delta = \theta_{ra} - A$$
  *(Lưu ý: Thành kính acrylic có 2 mặt phẳng song song nên theo định luật khúc xạ chỉ dịch tia song song một lượng vi lượng không đáng kể, hoàn toàn không làm đổi góc lệch $\delta$).*

### 1.2. Tại sao phải dùng cấu trúc vi sai hai ngăn & kiểm soát chênh nhiệt $D$?
- Trong thực tế, laser đi-ốt rất dễ bị **trôi nhiệt** (thermal beam drift), tay cầm điện thoại bị **rung lắc**, hoặc giá đỡ bị nghiêng làm vạch sáng trên màn bị dời một lượng $\delta y_{\text{drift}}$.
- **Nguyên lí vi sai**: Tín hiệu đo là **khoảng cách thẳng đứng $\Delta y = y_{\text{mẫu}} - y_{\text{tc}}$**. Phép trừ vi sai giúp triệt phần nhiễu chung, tuy nhiên phần lọt qua (`he_so_triet_chung` trong `config.yaml`) hiện **chưa đo** và phải xác định bằng thực nghiệm.
- **Chênh lệch nhiệt độ giữa hai ngăn ($D = T_{\text{mẫu}} - T_{\text{tham chiếu}}$):** Nếu nước mẫu nóng/lạnh hơn ngăn nước cất chuẩn, sự chênh chiết suất giữa hai ngăn gây lệch $\Delta y$ lớn ngay cả khi chưa đổi độ mặn. Phần mềm buộc tính vào bất định thành phần `chenh_nhiet_chua_do` khi chưa nhập $T_{\text{tc}}$, khóa phân loại (`khong_danh_gia_duoc = True`) khi $|D|$ vượt ngưỡng mà đường chuẩn chưa học số hạng $D$, và hỗ trợ chế độ **Theo dõi cân bằng nhiệt $\Delta y(t) = \Delta y_\infty + A e^{-t/\tau}$** để kiểm tra tốc độ trôi đã ổn định hay chưa.

### 1.3. Xử lí ảnh màu, lọc đốm speckle, trừ nền và méo ống kính
- **Chọn kênh màu & kiểm bão hòa RGB gốc (`Q1`):** Thay vì trộn ảnh xám ngay từ đầu, hệ thống hỗ trợ chọn kênh tối ưu `xu_ly_anh.kenh_laser` (`auto | R | G | B | xam`, mặc định `auto` chọn kênh tương phản cao nhất, hòa ưu tiên `R` cho laser 650 nm) và kiểm tra bão hòa trực tiếp trên từng kênh gốc B/G/R.
- **Phân biệt đốm speckle và bẹt đỉnh rộng (`Q2`):** Hạt đốm laser cục bộ (ít cột rời rạc chạm 250) chỉ cảnh báo mức cẩn thận (`co_dom_bao_hoa_cuc_bo = True`); chỉ khi tỉ lệ cột bão hòa vượt `ti_le_cot_bao_hoa_nghiem_trong` hoặc đoạn cột bão hòa liên tiếp $\ge$ `so_cot_lien_tiep_bao_hoa` mới loại ảnh (`bao_hoa = True, hop_le = False`).
- **Tách ROI bền vững trên nền không đều & ảnh 12MP (`Q3`):** Dùng phép mở hình thái ước lượng nền chậm và trừ nền trước khi phân ngưỡng tìm ROI (cờ `nen_khong_deu`), thu gọn bản dò ROI để đo ảnh `4000×3000` trong $\le 3\text{ s}$, kèm chức năng kéo chuột vẽ ROI thủ công trực tiếp trên ảnh web khi nền phức tạp.
- **Định vị tâm dưới pixel & đa khung (`T8`, `Q5`):** Khớp Gauss 1D từng cột kèm cắt ngoại lai 3σ lặp và centroid dự phòng; hỗ trợ đo đa khung (trung vị theo `MAD`) và khớp hàm mũ cân bằng nhiệt. Mọi số liệu độ lặp lại sub-pixel hiện nay chỉ đo được trên **ảnh MÔ PHỎNG**, chưa phải độ chính xác thiết bị thật.
- **Méo ống kính xuyên tâm tùy chọn (`Q6`):** Cảnh báo khi vạch lệch xa tâm ảnh vào vùng méo rìa (`nguong_lech_tam_meo_ti_le`), và hỗ trợ khử méo `cv2.undistort` (**TẮT mặc định** tại `bat_sua_meo_ong_kinh: false`) khi người dùng hiệu chuẩn bàn cờ qua `scripts/hieu_chuan_ong_kinh.py`.

### 1.4. Đánh giá độ đục tương đối
- Từ mở rộng bề rộng $FWHM$ (tán xạ Mie/Rayleigh) và suy giảm cường độ đỉnh (Beer–Lambert), hệ thống xuất **Chỉ số độ đục tương đối** ($0{,}0 - 1{,}0$). *Đây là chỉ số tương đối, KHÔNG quy ra đơn vị NTU khi chưa hiệu chuẩn riêng bằng dung dịch chuẩn Formazin.*

---

## 2. HƯỚNG DẪN CÀI ĐẶT, CHẠY WEB & GIỚI HẠN AN TOÀN

### 2.1. Yêu cầu môi trường & Cài đặt
- Hệ điều hành: Windows, macOS hoặc Linux; Python 3.10+ (khuyến nghị Python 3.11 với `.venv`).
```bash
python -m pip install -r requirements.txt
```

### 2.2. Khởi chạy Web 2.5D & Giới hạn tải lên
```bash
python app/web_app.py
```
Truy cập `http://127.0.0.1:8000`.
- **Giới hạn đầu vào (`config.yaml` mục `gioi_han`):** Mặc định giới hạn mỗi ảnh tối đa `25 MB`, `60 MP` và chuỗi đa khung tối đa `60` ảnh (vượt ngưỡng trả HTTP `413` mã `ANH_QUA_LON`; file hỏng/không phải ảnh trả HTTP `400` mã `ANH_KHONG_HOP_LE`). Tên file tải lên được làm sạch, truy vấn SQLite dùng tham số hóa.
- **Tab 5 (Mô phỏng quang học):** Cho phép chuyển đổi mô hình chiết suất **Tuyến tính** (mặc định, với `dn_dT_moi_do_C = -1.1e-4`) hoặc **Quan–Fry** ($\lambda$ cấu hình được) kèm cảnh báo tự động khi vượt dải hiệu lực Quan–Fry.
- **Đóng gói mã nguồn sạch:** Chạy `python scripts/dong_goi.py` (tự động loại trừ `.venv`, `.git`, `__pycache__`, `.pytest_cache`, `*.db*`, `*.zip`).

---

## 3. QUY TRÌNH THU DỮ LIỆU THẬT, CHỤP ẢNH & HIỆU CHUẨN

### 3.1. Thiết lập phần cứng & Chụp ảnh
1. Đặt cuvet hai ngăn cách màn hứng trắng mờ một khoảng $D$ ổn định; laser 650 nm vuông góc mặt kính vào.
2. Ngăn trái chứa nước cất $0\,‰$ đóng kín; ngăn phải tráng 2 lần bằng nước mẫu trước khi đo.
3. Che bớt ánh sáng môi trường chói, tựa máy cố định, **khóa phơi sáng và lấy nét (AE/AF lock)**, đặt thước chuẩn nếu đo theo `mm`, và **chờ cân bằng nhiệt** hai ngăn (dùng chức năng *Chờ cân bằng nhiệt* để kiểm tra tốc độ trôi thực tế).

### 3.2. Thu thập dữ liệu hiệu chuẩn chuẩn xác
1. Pha tối thiểu 5–8 mức độ mặn chuẩn NaCl từ **từ 2 mẻ pha trở lên** (ghi `ma_me_pha` để `GroupKFold` không rò rỉ dữ liệu lặp). Khai báo bất định dung dịch chuẩn (`sai_so_dung_dich_chuan_ppt`) và sai số nhiệt kế thật (`sai_so_nhiet_ke_C`) trong `config.yaml`.
2. Đo lặp ở nhiều mức nhiệt độ phủ hết dải nhiệt độ ao thực tế (nên tới $\ge 35\,^\circ\text{C}$), ghi rõ cả `nhiet_do_C` và `nhiet_do_tham_chieu_C`, `khoa_ae_af = 1`, `nguon_du_lieu = THUC_TE`.
3. Lưu ý giới hạn vật lí:
   - Công thức chiết suất **Quan–Fry** có hiệu lực trong $0\text{–}30\,^\circ\text{C}$, $0\text{–}35\text{ PSU}$, $\lambda = 400\text{–}700\text{ nm}$. **Các hệ số $a_0 \dots a_9$ trong `core/optics.py` do nhóm cung cấp và BẮT BUỘC phải đối chiếu trực tiếp với bài báo gốc Quan & Fry (*Applied Optics*, 1995) trước khi đưa vào báo cáo chính thức.**
   - Nước ao tự nhiên chứa nhiều ion khác NaCl nên kết quả là **độ mặn tương đương NaCl (ước lượng)**.

### 3.3. Quy trình đưa thư mục ảnh thật vào phần mềm & kiểm thử hồi quy (`Q4`)
Sau khi chụp xong bộ ảnh thật ngoài phòng thí nghiệm hoặc ao nuôi, dùng công cụ CLI hàng loạt [`scripts/xu_ly_thu_muc_anh.py`](scripts/xu_ly_thu_muc_anh.py):

```bash
# Cách 1: Kèm file metadata.csv (chứa ten_file, do_man_chuan_ppt, nhiet_do_C, nhiet_do_tham_chieu_C, ma_me_pha...)
python scripts/xu_ly_thu_muc_anh.py --thu-muc data/anh_that --nguon THUC_TE --metadata data/anh_that/metadata.csv

# Cách 2: Đọc độ mặn, nhiệt độ, lần đo từ tên file chuẩn <độmặn>_<nhiệtđộ>_<lầnđo>.jpg (ví dụ 20_28_01.jpg)
python scripts/xu_ly_thu_muc_anh.py --thu-muc data/anh_that --nguon THUC_TE --tu-ten-file --roi data/anh_that/roi.csv
```
- Tham số `--nguon` (`THUC_TE` hoặc `MO_PHONG`) là **bắt buộc**, không có giá trị mặc định.
- Script xuất đồng thời file CSV 13 cột nạp thẳng vào Tab 4 (Hiệu chuẩn) hoặc `scripts/dung_duong_chuan.py`, kèm file báo cáo chất lượng (`*_bao_cao_chat_luong.csv`, gồm cả thông tin EXIF phơi sáng/ISO và lí do loại từng ảnh hỏng).
- Để hiệu chuẩn méo ống kính riêng cho từng máy điện thoại bằng ảnh bàn cờ, dùng [`scripts/hieu_chuan_ong_kinh.py`](scripts/hieu_chuan_ong_kinh.py).
- Để kích hoạt kiểm thử hồi quy trên ảnh chụp thật của nhóm, đặt ảnh và `nhan_chuan.csv` vào `tests/anh_that/` theo hướng dẫn trong [`tests/anh_that/README.md`](tests/anh_that/README.md).

---

## 4. CHẠY KIỂM THỬ TỰ ĐỘNG & KẾT QUẢ MÔ PHỎNG

### 4.1. Kiểm thử đơn vị và tích hợp (`pytest`)
```bash
python -m pytest tests -q
```
Kết quả thực tế sau Vòng 2 (Q0–Q8): **`94 passed, 1 skipped`** (`test_hoi_quy_anh_that` trong `tests/test_anh_that.py` chủ động skip với lí do `"chưa có ảnh thật"`). Toàn bộ các con số dưới đây đến từ ảnh/dữ liệu **MÔ PHỎNG**, chưa phải số đo thiết bị thật.

### 4.2. Bảng độ bền vững thuật toán trên ảnh MÔ PHỎNG (`T9` cập nhật sau `Q1–Q7`)
> **Lưu ý:** Bảng dưới đây đo **độ bền vững thuật toán xử lí ảnh trên dữ liệu MÔ PHỎNG** (`sim/synth.py`), **KHÔNG phải độ chính xác của thiết bị thật**.

Lệnh tái lập:
```bash
python scripts/danh_gia_do_ben_vung.py
```
Kết quả chạy thực tế tại $S = 20{,}0\,‰$, $T = 25{,}0\,^\circ\text{C}$, $N = 10$ ảnh/mức (xuất ra `outputs/danh_gia_do_ben_vung_MO_PHONG.csv`):

| Hiệu ứng mô phỏng | Mức tham số | Đạt chất lượng | Sai lệch TB (px) | ĐLC (px) | Sai lệch TB (‰) | ĐLC (‰) |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| Cơ sở (không hiệu ứng phụ) | `0.0` | 10/10 | +0.0036 | 0.0061 | +0.0007 | 0.0012 |
| Đốm laser (`speckle_cuong_do`) | `0.05` / `0.1` / `0.2` | 10/10, 10/10, 10/10 | +0.0011 / +0.0045 / +0.0051 | 0.0207 / 0.0383 / 0.0838 | +0.0002 / +0.0009 / +0.0010 | 0.0041 / 0.0076 / 0.0165 |
| Méo ống kính (`meo_ong_kinh_k1`) | `-0.1` / `-0.05` / `0.05` / `0.1` | 10/10 | +0.6007 / +0.3422 / -0.3889 / -0.8211 | 0.0238 / 0.0070 / 0.0038 / 0.0073 | +0.1186 / +0.0676 / -0.0768 / -0.1622 | 0.0047 / 0.0014 / 0.0007 / 0.0014 |
| Gradient nền (`gradient_nen_y`) | `20.0` / `50.0` / `90.0` | 10/10, 10/10, 0/10\* | -0.0013 / -0.0041 / 0.0000 | 0.0044 / 0.0088 / 0.0076 | -0.0003 / -0.0008 / 0.0000 | 0.0009 / 0.0017 / 0.0015 |
| Độ cong vạch (`do_cong_vach` px) | `0.5` / `1.5` / `3.0` | 10/10 | +0.0075 / +0.0103 / +0.0193 | 0.0066 / 0.0061 / 0.0066 | +0.0015 / +0.0020 / +0.0038 | 0.0013 / 0.0012 / 0.0013 |
| Chênh sáng hai nửa (`chenh_sang_hai_nua`) | `0.2` / `0.4` / `0.6` | 10/10 | +0.0001 / +0.0045 / +0.0025 | 0.0058 / 0.0085 / 0.0084 | +0.0000 / +0.0009 / +0.0005 | 0.0011 / 0.0017 / 0.0017 |
| Phi tuyến cảm biến (`gamma_cam_bien`) | `0.7` / `1.4` / `2.0` | 10/10 | +0.0025 / +0.0032 / +0.0030 | 0.0077 / 0.0057 / 0.0042 | +0.0005 / +0.0006 / +0.0006 | 0.0015 / 0.0011 / 0.0008 |
| Nén mất dữ liệu (`chat_luong_jpeg`) | `90` / `70` / `50` | 10/10 | +0.0035 / +0.0006 / +0.0012 | 0.0035 / 0.0039 / 0.0051 | +0.0007 / +0.0001 / +0.0002 | 0.0007 / 0.0008 / 0.0010 |

*\*Tại `gradient_nen_y = 90.0`, phép trừ nền hình thái vẫn định vị đúng tâm hai vạch (`sai_lech_tb_px = 0.0000 px` thay vì `-185.99 px` trước đây), nhưng cộng hưởng nền cao + biên độ gốc `200` làm đỉnh vạch mẫu thực sự chạm bão hòa `255` nên cổng chất lượng bật đúng cả `NEN_KHONG_DEU` lẫn `BAO_HOA_NGHIEM_TRONG`.*
