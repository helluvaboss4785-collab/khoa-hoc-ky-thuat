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
- Trong thực tế, laser đi-ốt rất dễ bị **trôi nhiệt** (thermal beam drift), tay cầm điện thoại bị **rung lắc**, hoặc giá đỡ bị nghiêng làm vạch sáng trên màn bị dời một lượng $\delta y_{drift}$.
- **Nguyên lí vi sai**: Vì chùm laser chiếu đồng thời qua cả hai ngăn, sự rung lắc cơ học và trôi dạt nguồn sáng sẽ tác động như nhau lên cả hai vạch:
  $$y_{mẫu} = y_{mẫu, 0} + \delta y_{drift}$$
  $$y_{tc} = y_{tc, 0} + \delta y_{drift}$$
  Tín hiệu đo là **khoảng cách thẳng đứng $\Delta y$ giữa hai vạch**:
  $$\Delta y = y_{mẫu} - y_{tc} = (y_{mẫu, 0} + \delta y_{drift}) - (y_{tc, 0} + \delta y_{drift}) = y_{mẫu, 0} - y_{tc, 0}$$
  $\implies$ **Triệt tiêu hoàn toàn sai số trôi nguồn và rung lắc bậc 1!**

### 1.3. Thuật toán định vị tâm vạch dưới pixel (Sub-pixel Beam Centroid)
- Profile cường độ theo phương thẳng đứng của laser tuân theo hàm Gauss:
  $$I(y) = I_{bg} + A \cdot \exp\left(-\frac{(y - \mu)^2}{2\sigma^2}\right)$$
- Sử dụng thuật toán khớp phi tuyến Levenberg-Marquardt (`scipy.optimize.curve_fit`) kết hợp khớp đường thẳng có trọng số qua hàng trăm cột ảnh, giúp đạt độ chính xác tâm vạch $< 0{,}02\text{ pixel}$ (vượt xa độ phân giải mắt thường).

### 1.4. Đánh giá độ đục tương đối
- Khi nước bị đục do phù sa hoặc chất lơ lửng, hiện tượng **tán xạ Mie/Rayleigh** làm chùm laser bị mở rộng (tăng độ rộng nửa cực đại $FWHM$) và suy giảm cường độ đỉnh theo định luật Beer-Lambert.
- Thiết bị tính toán **Chỉ số độ đục tương đối** ($0{,}0 - 1{,}0$). *Lưu ý khoa học: Đây là chỉ số tương đối, không được tự ý quy đổi ra đơn vị NTU khi chưa có dung dịch chuẩn Formazin.*

---

## 2. HƯỚNG DẪN CÀI ĐẶT & CHẠY ỨNG DỤNG

### 2.1. Yêu cầu môi trường
- Hệ điều hành: Windows, macOS hoặc Linux.
- Python 3.10 trở lên (khuyến nghị Python 3.11 - 3.15).

### 2.2. Cài đặt các thư viện phụ thuộc
Mở terminal / PowerShell tại thư mục dự án và chạy lệnh:
```bash
python -m pip install numpy scipy pandas matplotlib opencv-python-headless streamlit pyyaml pytest
```

### 2.3. Khởi chạy giao diện người dùng Streamlit
Chạy lệnh sau từ thư mục `salinity/`:
```bash
python -m streamlit run app/streamlit_app.py
```
Trình duyệt sẽ tự động mở trang web tại địa chỉ: `http://localhost:8501`.

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
1. Pha tối thiểu 5–8 dung dịch muối chuẩn NaCl bằng cân phân tích chính xác ($\pm 0{,}01\text{ g}$) và bình định mức:
   - Các mức gợi ý: $0\text{ ‰}$ (nước cất), $5\text{ ‰}$, $10\text{ ‰}$, $15\text{ ‰}$, $20\text{ ‰}$, $25\text{ ‰}$, $30\text{ ‰}$, $35\text{ ‰}$.
2. Đo lặp lại mỗi mẫu 3 lần ở các dải nhiệt độ phòng (ví dụ buổi sáng $22^\circ\text{C}$, trưa $28^\circ\text{C}$).
3. Nhập số liệu vào file `data/mau_hieu_chuan.csv` và chạy dựng đường chuẩn tại Tab 4 của ứng dụng.

---

## 4. CHẠY KIỂM THỬ TỰ ĐỘNG (UNIT TESTS)

Để kiểm tra toàn diện tính toàn vẹn của mã nguồn, độ chính xác thuật toán và thử nghiệm lặp lại Monte Carlo 100 ảnh:
```bash
python -m pytest tests -v
```
Toàn bộ 48 bài kiểm thử chuyên sâu (Optics, Tìm tâm vạch, Đo vi sai, Bộ sinh mô phỏng Monte Carlo, Hiệu chuẩn & Bù nhiệt, Ngưỡng sinh học) đều phải vượt qua (`PASSED 100%`).

