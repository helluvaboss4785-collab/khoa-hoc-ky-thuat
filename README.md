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
- **Chọn kênh màu & kiểm bão hòa RGB gốc (`Q1`, `R5`):** Hỗ trợ chọn kênh tối ưu `xu_ly_anh.kenh_laser` (`auto | R | G | B | xam | Y`, mặc định `auto` chọn kênh tương phản cao nhất, hòa ưu tiên `R` cho laser 650 nm; `"Y"` trích kênh sáng của không gian `YCrCb` để đối chiếu ảnh JPEG 4:2:0) và kiểm tra bão hòa trực tiếp trên từng kênh gốc B/G/R. *Nhóm phải tự chạy `python scripts/so_sanh_kenh.py --nguon THUC_TE --thu-muc <thu_muc_anh_that>` trên chính ảnh chụp từ điện thoại của mình trước khi kết luận chọn kênh cho ảnh thật.*
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
*(Ghi chú: `requirements.txt` đã ghim sẵn `httpx==0.28.1` để chạy trọn vẹn kiểm thử tích hợp ASGI qua Starlette `TestClient` bên cạnh bộ chạy web thực tế).*

### 2.2. Khởi chạy Web 2.5D & Giới hạn tải lên
```bash
python app/web_app.py
```
Truy cập `http://127.0.0.1:8000`.
- **Giới hạn đầu vào (`config.yaml` mục `gioi_han`):** Mặc định giới hạn mỗi ảnh tối đa `25 MB`, `60 MP` và chuỗi đa khung tối đa `60` ảnh (vượt ngưỡng trả HTTP `413` mã `ANH_QUA_LON`; file hỏng/không phải ảnh trả HTTP `400` mã `ANH_KHONG_HOP_LE`). Tên file tải lên được làm sạch, truy vấn SQLite dùng tham số hóa.
- **Tab 5 (Mô phỏng quang học):** Cho phép chuyển đổi mô hình chiết suất **Tuyến tính** (mặc định, với `dn_dT_moi_do_C = -1.1e-4` tại `quang_hoc.nhiet_do_chuan_chiet_suat_C`) hoặc **Quan–Fry** ($\lambda$ cấu hình được) kèm cảnh báo tự động khi vượt dải hiệu lực Quan–Fry. *(Lưu ý: `quang_hoc.nhiet_do_chuan_chiet_suat_C` là nhiệt độ chuẩn của công thức chiết suất nước ngọt, khác với cột CSV `nhiet_do_tham_chieu_C` vốn là nhiệt độ ngăn nước cất tham chiếu).*
- **Đóng gói mã nguồn sạch để nộp bài (R10):** Chỉ đóng gói và nộp bài bằng lệnh dưới đây (tự động loại trừ `.venv`, `.git`, `__pycache__`, `.pytest_cache`, `*.db*`, `*.zip` và xác nhận dung lượng `< 20 MB`; **tuyệt đối không** nén thủ công cả thư mục dự án):
  ```bash
  python scripts/dong_goi.py --kiem-tra
  ```

---

## 3. QUY TRÌNH THU DỮ LIỆU THẬT, CHỤP ẢNH & HIỆU CHUẨN

> **Tài liệu hướng dẫn đầy đủ cho học sinh & biểu mẫu ghi chép thực nghiệm (`V5`):**  
> - Quy trình thu thập dữ liệu từng bước: [`docs/QUY_TRINH_THU_DU_LIEU.md`](docs/QUY_TRINH_THU_DU_LIEU.md)  
> - Biểu mẫu cặp đọc hiệu chuẩn chéo nhiệt kế (trống, 0 dòng giả lập): [`data/mau_cap_nhiet_ke.csv`](data/mau_cap_nhiet_ke.csv)  
> - Biểu mẫu nhật kí pha mẫu & chụp ảnh thí nghiệm (trống, 0 dòng giả lập): [`data/mau_ghi_chep_thi_nghiem.csv`](data/mau_ghi_chep_thi_nghiem.csv)

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

### 3.4. Chống gắn nhãn sai nguồn dữ liệu (`V0`), Hiệu chuẩn chéo nhiệt kế (`V1`), Thiết kế thí nghiệm (`V4`) & Xuất báo cáo
- **Chống gắn nhãn sai nguồn dữ liệu (`V0`):** Mọi ảnh sinh từ `sim/synth.py` đều nhúng dấu `SIMULATED` ngay trong file ảnh (chunk `tEXt` PNG, đoạn `COM` JPEG, file `.json` cạnh ảnh) và nhận diện tên file chứa `MO_PHONG`/`SIMULATED`. Lệnh `scripts/xu_ly_thu_muc_anh.py --nguon THUC_TE` sẽ từ chối (mã thoát `2`, không ghi CSV) nếu gặp ảnh có dấu mô phỏng; Web App `/api/measure`, `/api/measure-multi` tự gắn `la_mo_phong = True`, `khong_danh_gia_duoc = True` và ép lưu nhật kí thành `MÔ PHỎNG`.
- **Hiệu chuẩn chéo hai nhiệt kế (`V1`):** Ngâm chung hai đầu đo trong cùng một cốc nước khuấy đều ở nhiều mức nhiệt (điểm `0 °C` kiểm bằng nước đá xay + nước cất, không đo trực tiếp đá cục), ghi bảng theo [`data/mau_cap_nhiet_ke.csv`](data/mau_cap_nhiet_ke.csv) rồi chạy:
  ```bash
  python scripts/hieu_chuan_cheo_nhiet_ke.py --csv data/cap_nhiet_ke_cua_nhom.csv --nguoi-thuc-hien "<Ten_HS>" --nguon THUC_TE
  ```
  Công cụ kiểm định độ dốc tuyến tính `offset(T) = a + b·T`, lưu `data/hieu_chuan_nhiet_ke.json` và tự cộng bất định `σ_offset` vào `σ_Dđo` khi đo mặn (nếu chưa hiệu chuẩn chéo, phần mềm bật cảnh báo nhắc trong kết quả đo và panel R7).
- **Kiểm tra thiết kế thí nghiệm (`V4` — không chặn dựng đường chuẩn):** Trước hoặc song song khi dựng đường chuẩn trên Tab 4 hoặc CLI, kiểm nhanh số mức nồng độ, điểm gốc `0‰`, độ phủ dải, cân bằng mẫu, số mẻ pha `ma_me_pha`, biên độ nhiệt độ, biến thiên `D` (khi học `D`), tỉ lệ `px/mm` và tính đồng nhất `nguon_du_lieu` bằng:
  ```bash
  python scripts/kiem_tra_thiet_ke_thi_nghiem.py --csv data/hieu_chuan_cua_toi.csv
  ```
- **Bảng trạng thái giả định (`R7`/`V6`):** Trên giao diện web có nút *"Các tham số còn là giả định"* (và endpoint `GET /api/trang-thai-cau-hinh`) liệt kê trung thực mọi tham số còn mang giá trị giả định (bao gồm cả thông số hiệu chuẩn chéo nhiệt kế `V1` và `thiet_ke_thi_nghiem.*` `V4`), còn `null`, thiếu nguồn sinh học, hoặc trạng thái đối chiếu Quan–Fry 3 mức.
- **Đối chiếu 10 hệ số Quan–Fry 2 người độc lập (`R8`/`V2`):** Mở [`docs/DOI_CHIEU_QUAN_FRY.md`](docs/DOI_CHIEU_QUAN_FRY.md), điền số trang/bảng cho đủ 10 hệ số từ bài báo gốc Quan & Fry (*Applied Optics*, 1995) rồi chạy:
  ```bash
  python scripts/kiem_tra_quan_fry.py --csv <file_csv_cua_ban.csv> --luu-xac-nhan --nguoi-doi-chieu "<Nguoi_1>" --nguoi-xac-nhan-2 "<Nguoi_2>" --trich-dan "Quan & Fry (1995), Applied Optics ..."
  ```
- **Xuất tài liệu báo cáo & poster (`R9`):** Dùng [`scripts/xuat_bao_cao.py`](scripts/xuat_bao_cao.py) để xuất 6 tài liệu vào `outputs/bao_cao/` (đồ thị đường chuẩn kèm phần dư & vùng bất định, bảng sai số theo mức, Bland–Altman khi có `--so-sanh`, ngân sách sai số lí thuyết, bảng giả định R7, Markdown tổng hợp). Mọi hình/bảng tự động đóng dấu bắt buộc `DỮ LIỆU MÔ PHỎNG / CHƯA XÁC NHẬN` nếu chưa đủ nhãn `THUC_TE`:
  ```bash
  python scripts/xuat_bao_cao.py --csv data/hieu_chuan_cua_toi.csv --so-sanh data/so_sanh.csv
  ```
- **Kiểm tra thủ công trên điện thoại thật (`R10`):** Làm theo từng bước trong bảng [`docs/KIEM_TRA_THU_CONG_TREN_DIEN_THOAI.md`](docs/KIEM_TRA_THU_CONG_TREN_DIEN_THOAI.md) để nghiệm thu PWA, chạy ngoại tuyến, camera, vẽ ROI và xuất CSV trên điện thoại thật.

---

## 4. CHẠY KIỂM THỬ TỰ ĐỘNG & KẾT QUẢ MÔ PHỎNG

### 4.1. Kiểm thử đơn vị, tích hợp và nghiệm thu Vòng 3
```bash
python -m pytest tests -q
python scripts/kiem_tra_chap_nhan_vong3.py
```
Kết quả thực tế sau Vòng 3 (`R0–R10`): **`111 passed, 1 skipped`** (`test_hoi_quy_anh_that` trong `tests/test_anh_that.py` chủ động skip với lí do `"chưa có ảnh thật"`). Toàn bộ các con số dưới đây đến từ ảnh/dữ liệu **MÔ PHỎNG**, **KHÔNG phải độ chính xác của thiết bị thật**.

### 4.2. Bảng độ bền vững thuật toán trên 100 seed ảnh MÔ PHỎNG (`R2`)
> **Lưu ý:** Bảng dưới đây đo **độ bền vững thuật toán xử lí ảnh trên dữ liệu MÔ PHỎNG** (`sim/synth.py`, ảnh `600×400`, `y_tham_chieu_goc = 100`), **KHÔNG phải độ chính xác của thiết bị thật**.

Lệnh tái lập:
```bash
python scripts/danh_gia_do_ben_vung.py
```
Kết quả chạy thực tế tại $S = 20{,}0\,‰$, $T = 25{,}0\,^\circ\text{C}$, trên **100 seed cố định (`1000..1099`)** mỗi mức (xuất ra `outputs/do_ben_vung_nhieu_seed_MO_PHONG.csv`):

| Hiệu ứng mô phỏng | Mức tham số | Đạt chất lượng [Wilson 95% CI] | Tỉ lệ `< 0,15 px` (trong hợp lệ) | RMS (px) | Trung vị \|err\| (px) | P95 \|err\| (px) | Tối đa \|err\| (px) |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| Cơ sở (không hiệu ứng phụ) | `0.0` | 100/100 (100% [96.3–100%]) | 100% [96.3–100%] | 0.0047 | 0.0031 | 0.0095 | 0.0127 |
| Đốm laser (`speckle_cuong_do`) | `0.1` | 100/100 (100% [96.3–100%]) | 100% [96.3–100%] | 0.0375 | 0.0272 | 0.0729 | 0.1018 |
| Đốm laser (`speckle_cuong_do`) | `0.2` | 96/100 (96.0% [90.2–98.4%]) | 95.8% [89.8–98.4%] | 0.0732 | 0.0571 | 0.1448 | 0.1787 |
| Đốm laser + gradient nền | `spk=0.1, grad=40` | 95/100 (95.0% [88.8–97.8%]) | 100% [96.1–100%] | 0.0445 | 0.0353 | 0.0853 | 0.1045 |
| Gradient nền (`gradient_nen_y`) | `40.0` / `90.0`\* | 100/100, 0/100\* | 100%, 100% | 0.0052 / 0.0052 | 0.0036 / 0.0035 | 0.0094 / 0.0102 | 0.0155 / 0.0151 |
| Méo ống kính (`meo_ong_kinh_k1`) | `-0.1` / `0.1` | 100/100, 100/100 | 0%, 0% (lệch hệ thống) | 0.4496 / 0.7081 | 0.4497 / 0.7084 | 0.4582 / 0.7157 | 0.4645 / 0.7201 |
| Độ cong vạch (`do_cong_vach` px) | `1.5` / `3.0` | 100/100 | 100% | 0.0075 / 0.0120 | 0.0054 / 0.0105 | 0.0146 / 0.0190 | 0.0172 / 0.0257 |
| Chênh sáng hai nửa | `0.4` / `0.6` | 100/100 | 100% | 0.0059 / 0.0064 | 0.0043 / 0.0047 | 0.0113 / 0.0125 | 0.0138 / 0.0169 |
| Phi tuyến cảm biến (`gamma`) | `0.7` / `2.0` | 100/100 | 100% | 0.0054 / 0.0046 | 0.0038 / 0.0034 | 0.0093 / 0.0086 | 0.0170 / 0.0121 |
| Nén JPEG (`chat_luong_jpeg`) | `70` / `50` | 100/100 | 100% | 0.0043 / 0.0059 | 0.0029 / 0.0041 | 0.0086 / 0.0113 | 0.0119 / 0.0154 |

*\*Tại `gradient_nen_y = 90.0`, phép trừ nền hình thái vẫn định vị đúng tâm hai vạch (`RMS = 0.0052 px`, `max = 0.0151 px`), nhưng cộng hưởng nền cao + biên độ gốc `200` làm đỉnh vạch mẫu thực sự chạm bão hòa `255` nên cổng chất lượng bật đúng cả `NEN_KHONG_DEU` lẫn `BAO_HOA_NGHIEM_TRONG`.*
