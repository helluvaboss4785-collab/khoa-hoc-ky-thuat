# HỆ THỐNG ĐO ĐỘ MẶN NƯỚC BẰNG KHÚC XẠ LASER & CAMERA ĐIỆN THOẠI
## Cấu trúc vi sai hai ngăn quang học khử trôi

> **Dự án dự thi Khoa học Kỹ thuật (KHKT) dành cho học sinh THPT**  
> *Lĩnh vực: Kỹ thuật Môi trường / Phần mềm Hệ thống & Vật lí Ứng dụng*

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

### 1.2. Tại sao phải dùng cấu trúc vi sai hai ngăn?
- Trong thực tế, laser đi-ốt rất dễ bị **trôi nhiệt** (thermal beam drift), tay cầm điện thoại bị **rung lắc**, hoặc giá đỡ bị nghiêng làm vạch sáng trên màn bị dời một lượng $\delta y_{\text{drift}}$.
- **Nguyên lí vi sai**: Vì chùm laser chiếu đồng thời qua cả hai ngăn, phần nhiễu **CHUNG** tác động lên cả hai vạch:
  $$y_{\text{mẫu}} = y_{\text{mẫu}, 0} + \delta y_{\text{drift, mẫu}}$$
  $$y_{\text{tc}} = y_{\text{tc}, 0} + \delta y_{\text{drift, tc}}$$
  Tín hiệu đo là **khoảng cách thẳng đứng $\Delta y$ giữa hai vạch**:
  $$\Delta y = y_{\text{mẫu}} - y_{\text{tc}}$$
  Đo vi sai giúp **triệt phần nhiễu CHUNG** giữa hai vạch; tuy nhiên mức triệt thực tế (`he_so_triet_chung` trong `config.yaml`) hiện **chưa đo** và bắt buộc phải xác định bằng thực nghiệm (bộ phận không triệt tiêu hết như độ nghiêng khác nhau, trôi nhiệt riêng từng ngăn vẫn đi vào sai số).

### 1.3. Thuật toán định vị tâm vạch dưới pixel (Sub-pixel Beam Centroid)
- Profile cường độ theo phương thẳng đứng của laser được xấp xỉ theo hàm Gauss:
  $$I(y) = I_{\text{bg}} + A \cdot \exp\left(-\frac{(y - \mu)^2}{2\sigma^2}\right)$$
- Sử dụng thuật toán khớp phi tuyến Levenberg–Marquardt (`scipy.optimize.curve_fit`) kết hợp khớp đường thẳng có trọng số qua nhiều cột ảnh. Độ lệch chuẩn lặp lại ở mức dưới pixel đo được trên bộ ảnh kiểm thử là **độ lặp lại do nhiễu ngẫu nhiên trên ảnh MÔ PHỎNG, không phải độ chính xác của thiết bị thật**.

### 1.4. Đánh giá độ đục tương đối
- Khi nước bị đục do phù sa hoặc chất lơ lửng, hiện tượng **tán xạ Mie/Rayleigh** làm chùm laser bị mở rộng (tăng độ rộng nửa cực đại $FWHM$) và suy giảm cường độ đỉnh theo định luật Beer-Lambert.
- Thiết bị tính toán **Chỉ số độ đục tương đối** ($0{,}0 - 1{,}0$). *Lưu ý khoa học: Đây là chỉ số tương đối, không được tự ý quy đổi ra đơn vị NTU khi chưa có dung dịch chuẩn Formazin.*

---

## 2. HƯỚNG DẪN CÀI ĐẶT & CHẠY ỨNG DỤNG

### 2.1. Yêu cầu môi trường
- Hệ điều hành: Windows, macOS hoặc Linux.
- Python 3.10 trở lên (khuyến nghị Python 3.11; môi trường kiểm thử hiện tại dùng Python 3.11 với `.venv`).

### 2.2. Cài đặt các thư viện phụ thuộc
Mở terminal / PowerShell tại thư mục dự án, kích hoạt môi trường ảo (nếu có) và chạy lệnh:
```bash
python -m pip install -r requirements.txt
```
*(Khuyến nghị tạo `.venv` trước bằng `python -m venv .venv` để không làm lẫn thư viện hệ thống.)*

### 2.3. Khởi chạy giao diện Web 2.5D
Chạy lệnh sau từ thư mục dự án:
```bash
python app/web_app.py
```
Trình duyệt sẽ tự động mở tại địa chỉ: `http://127.0.0.1:8000`.
*(Khi cần đóng gói mã nguồn nộp bài mà bỏ qua `.venv`, `.git`, `__pycache__`, `.pytest_cache`, `*.db*`, chạy: `python scripts/dong_goi.py`.)*

---

## 3. QUY TRÌNH THU THẬP DỮ LIỆU & CHỤP ẢNH CHUẨN XÁC

### 3.1. Thiết lập phần cứng
1. Đặt cuvet lăng kính hai ngăn cách màn hứng màu trắng mờ một khoảng $D \approx 1{,}0\text{ m}$ (hoặc dùng gương phẳng gấp đường quang trong hộp kín kích thước nhỏ gọn $30 \times 40\text{ cm}$).
2. Bật laser vạch đỏ 650 nm, căn chỉnh sao cho vạch laser đi vuông góc với mặt kính vào của cuvet.
3. Ngăn trái đổ nước cất đóng kín; ngăn phải tráng sạch 2 lần bằng nước mẫu cần đo trước khi châm đầy.

### 3.2. Cách chụp ảnh đúng kỹ thuật
- **Tránh cháy sáng (bão hòa)**: Không để vạch sáng bị bệt trắng ở mức 255. Nếu giao diện báo "Vạch sáng bị bão hòa", hãy dán thêm một lớp giấy mờ hoặc giảm độ phơi sáng (EV) của máy ảnh.
- **Tránh rung nhòe**: Đặt điện thoại lên giá đỡ hoặc tựa chắc tay khi bấm chụp.
- **Góc chụp**: Ống kính điện thoại hướng trực diện, vuông góc với màn hứng vạch.

### 3.3. Quy trình thu thập dữ liệu hiệu chuẩn (Calibration)
1. Pha tối thiểu 5–8 dung dịch muối chuẩn NaCl bằng cân phân tích chính xác (tách thành các **mẻ pha riêng biệt** gắn mã `ma_me_pha` để tránh rò rỉ lặp giữa tập huấn luyện và kiểm tra; khai báo bất định của dung dịch chuẩn tại `hieu_chuan.sai_so_dung_dich_chuan_ppt` trong `config.yaml`) và bình định mức:
   - Các mức gợi ý: $0\,‰$ (nước cất), $5\,‰$, $10\,‰$, $15\,‰$, $20\,‰$, $25\,‰$, $30\,‰$, $35\,‰$.
2. Đo lặp lại mỗi mẫu ở nhiều mức nhiệt độ phủ hết **dải nhiệt độ ao nuôi thực tế** (nên phủ tới $\ge 35\,^\circ\text{C}$ nếu có thể, không chỉ giới hạn ở $22\text{–}28\,^\circ\text{C}$), ghi rõ nhiệt độ cả **ngăn mẫu** (`nhiet_do_C`) và **ngăn tham chiếu** (`nhiet_do_tham_chieu_C`), khóa phơi sáng/lấy nét (`khoa_ae_af = 1`) và đặt thước chuẩn để quy đổi `px_per_mm` nếu dựng đường chuẩn theo `mm`.
3. Cấu trúc đầy đủ 13 cột của file `data/mau_hieu_chuan.csv`:
   - Bắt buộc: `do_man_chuan_ppt`, `nhiet_do_C`, `delta_y_px`, `do_duc_tuong_doi`, `ghi_chu`, `id_thiet_bi`, `id_dien_thoai`.
   - Tùy chọn nhưng khuyến nghị ghi đầy đủ: `nhiet_do_tham_chieu_C`, `px_per_mm`, `ma_me_pha`, `ngay_do`, `nguon_du_lieu` (ghi tường minh `THUC_TE` cho phép đo thật; thiếu cột hoặc bỏ trống sẽ bị gắn nhãn `CHUA_XAC_DINH`), `khoa_ae_af`.
4. Lưu ý giới hạn vật lí:
   - Công thức chiết suất Quan–Fry (tùy chọn `quang_hoc.mo_hinh_chiet_suat: "quan_fry"`, hệ số cần đối chiếu lại với bài gốc Quan & Fry, *Applied Optics*, 1995) chỉ có hiệu lực trong khoảng $0\text{–}30\,^\circ\text{C}$, $0\text{–}35\text{ PSU}$, bước sóng $400\text{–}700\text{ nm}$.
   - Nước ao/nước tự nhiên chứa nhiều ion khác ($\text{Mg}^{2+}, \text{Ca}^{2+}, \text{K}^+, \text{SO}_4^{2-}, \text{HCO}_3^-\dots$) và chất hữu cơ hòa tan nên khác với dung dịch NaCl tinh khiết; kết quả đo chỉ là **độ mặn tương đương NaCl**.
5. Nhập số liệu thật vào file CSV theo đúng định dạng trên và chạy dựng đường chuẩn tại Tab 4 của ứng dụng (mặc định đánh giá bằng kiểm định chéo theo nhóm `ma_me_pha` khi có đủ cột mẻ pha).

---

## 4. CHẠY KIỂM THỬ TỰ ĐỘNG & ĐỘ BỀN VỮNG MÔ PHỎNG

### 4.1. Kiểm thử đơn vị và tích hợp (`pytest`)
Để kiểm tra toàn diện mã nguồn (quang học + Quan–Fry, tìm tâm vạch + 3σ outlier, đo vi sai + đa khung hình, thang `px/mm`, mô phỏng Monte Carlo 100 ảnh, hiệu chuẩn GroupKFold & bù nhiệt 2 ngăn, ngưỡng sinh học theo khoảng `[S-U, S+U]` và API web):
```bash
python -m pytest tests -q
```
Kết quả chạy thực tế sau nâng cấp T1–T11: **79 bài kiểm thử đều đạt (`79 passed`, 0 bỏ qua)**.

### 4.2. Bảng độ bền vững thuật toán trên ảnh MÔ PHỎNG (`T9`)
> **Lưu ý:** Bảng dưới đây đo **độ bền vững của thuật toán xử lí ảnh trên dữ liệu MÔ PHỎNG** (bài toán lý tưởng hóa từ `sim/synth.py`), **KHÔNG phải độ chính xác của thiết bị phần cứng thật**.

Lệnh tái lập:
```bash
python scripts/danh_gia_do_ben_vung.py
```
Kết quả thực tế khi chạy tại $S = 20{,}0\,‰$, $T = 25{,}0\,^\circ\text{C}$, $N = 10$ ảnh/mức (xuất ra `outputs/danh_gia_do_ben_vung_MO_PHONG.csv`):

| Hiệu ứng mô phỏng | Mức tham số | Đạt chất lượng | Sai lệch TB (px) | ĐLC (px) | Sai lệch TB (‰) | ĐLC (‰) |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| Cơ sở (không hiệu ứng phụ) | `0.0` | 10/10 | +0.0027 | 0.0070 | +0.0005 | 0.0014 |
| Đốm laser (`speckle_cuong_do`) | `0.05` / `0.1` / `0.2` | 10/10, 0/10, 0/10 | +0.0030 / +0.0019 / +0.0058 | 0.0204 / 0.0391 / 0.0837 | +0.0006 / +0.0004 / +0.0012 | 0.0040 / 0.0077 / 0.0165 |
| Méo ống kính (`meo_ong_kinh_k1`) | `-0.1` / `-0.05` / `0.05` / `0.1` | 10/10 | +0.5950 / +0.3415 / -0.3885 / -0.8230 | 0.0189 / 0.0071 / 0.0056 / 0.0062 | +0.1175 / +0.0674 / -0.0767 / -0.1625 | 0.0037 / 0.0014 / 0.0011 / 0.0012 |
| Gradient nền (`gradient_nen_y`) | `20.0` / `50.0` / `90.0` | 10/10, 0/10, 0/10 | -0.0007 / -0.0059 / -185.9863 | 0.0063 / 0.0075 / 65.0207 | -0.0001 / -0.0012 / -36.7259 | 0.0012 / 0.0015 / 12.8393 |
| Độ cong vạch (`do_cong_vach` px) | `0.5` / `1.5` / `3.0` | 10/10 | +0.0053 / +0.0115 / +0.0213 | 0.0044 / 0.0039 / 0.0048 | +0.0011 / +0.0023 / +0.0042 | 0.0009 / 0.0008 / 0.0010 |
| Chênh sáng hai nửa (`chenh_sang_hai_nua`) | `0.2` / `0.4` / `0.6` | 10/10 | +0.0004 / +0.0033 / +0.0023 | 0.0060 / 0.0087 / 0.0094 | +0.0001 / +0.0006 / +0.0005 | 0.0012 / 0.0017 / 0.0019 |
| Phi tuyến cảm biến (`gamma_cam_bien`) | `0.7` / `1.4` / `2.0` | 10/10 | +0.0020 / +0.0049 / +0.0045 | 0.0089 / 0.0058 / 0.0056 | +0.0004 / +0.0010 / +0.0009 | 0.0017 / 0.0011 / 0.0011 |
| Nén mất dữ liệu (`chat_luong_jpeg`) | `90` / `70` / `50` | 10/10 | +0.0006 / -0.0010 / -0.0062 | 0.0067 / 0.0038 / 0.0098 | +0.0001 / -0.0002 / -0.0012 | 0.0013 / 0.0007 / 0.0019 |

