# Giải thích Mã nguồn & Chuẩn bị Phỏng vấn KHKT

> [!IMPORTANT]
> Tài liệu này tổng hợp kiến trúc phần mềm, công thức vật lí – toán học và hướng dẫn trả lời phỏng vấn cho dự án **"Đo độ mặn nước bằng khúc xạ laser qua lăng kính hai ngăn (vi sai) + camera điện thoại"**. Mọi ví dụ số bên dưới chạy trên dữ liệu **MÔ PHỎNG** (`seed=42`), không phải kết quả đo của thiết bị thật.

---

## 1. Bản đồ kiến trúc & Vật lí từng module trong `core/`

### 1.1. Quang học lăng kính hai ngăn (`core/optics.py`)
- **Nguyên lí vật lí:** Hai ngăn lăng kính góc đỉnh $A$ đặt cạnh nhau: một ngăn chứa nước cất tham chiếu ($S = 0\,‰$, nhiệt độ $T_{\text{tc}}$), một ngăn chứa mẫu nước ($S$, nhiệt độ $T_{\text{mẫu}}$). Tia laser đi qua mỗi ngăn bị lệch góc $\delta(n, A) = \arcsin(n\sin A_1) + \dots$ theo định luật Snell (`goc_lech` dùng `chiet_suat` và tham số trong `CauHinhQuangHoc`).
- **Đo vi sai trên màn hứng:** Khoảng cách theo phương đứng giữa hai vạch trên cảm biến tại khoảng cách $D$:
  $$\Delta y = y_{\text{mẫu}} - y_{\text{tc}}$$
  Hàm `delta_y_vi_sai_px` tính độ dịch chuyển tương đối theo `pixel_mm` và `pixel_moi_phan_nghin` tính độ nhạy $\partial(\Delta y)/\partial S$ (px/‰).
- **Ngân sách sai số lí thuyết:** `ngan_sach_sai_so` (trả về `KetQuaNganSachSaiSo`) quy đổi 4 nguồn nhiễu về đơn vị ‰ (`tim_tam`, `nhiet_do`, `goc_A`, `troi_laser`) rồi tổng hợp theo RSS (`tong_RSS`), đồng thời ưu tiên lấy tham số đã đo thật từ `doc_tham_so_do_duoc` nếu có và gắn nhãn "đo được" hoặc "giả định" trong `nguon`.

### 1.2. Định vị tâm vạch laser dưới-pixel (`core/spot.py`)
- **Hàm Gauss 1D theo cột:** Theo phương đứng $y$, cường độ chùm laser $\text{TEM}_{00}$ tuân theo `ham_gauss_1d`:
  $$I(y) = \text{bg} + A \exp\left(-\frac{(y - \mu)^2}{2\sigma^2}\right)$$
  Hàm `uoc_luong_tam_gauss_cot` (tăng tốc nhờ Jacobian giải tích `_jac_gauss_1d`) khớp từng cột ảnh, trả về `KetQuaCotGauss` với sai số chuẩn `sai_so_mu` từ ma trận hiệp phương sai. Nếu cột bị phi Gauss hoặc không hội tụ, `uoc_luong_tam_centroid_cot` đóng vai trò dự phòng.
- **Khớp đường thẳng toàn vạch:** `uoc_luong_duong_vach` cắt ngoại lai 3σ theo MAD, chặn tỉ lệ trọng số cực đoan và khớp đường thẳng có trọng số $y(x) = ax + b$ để nội suy vị trí tại `x_ref`, trả về `KetQuaUocLuongVach` gồm `y_tam` và `sai_so_y`.

### 1.3. Đo Δy và kiểm soát chất lượng ảnh (`core/measure.py`)
- **Kiểm tra định dạng & giải mã:** `nhan_dien_dinh_dang_anh_bytes` và `giai_ma_anh_tu_bytes` nhận diện chữ kí byte HEIC/HEIF/WebP để ném `AnhKhongHoTroDinhDangError` (HTTP 415) thay vì im lặng hoặc crash.
- **Chọn kênh & kiểm tra chất lượng:** `chon_kenh_laser` chọn kênh đơn sắc tối ưu; `kiem_tra_chat_luong_vung` kiểm tra bão hòa (`BAO_HOA_NGHIEM_TRONG` vs đốm cục bộ `DOM_BAO_HOA_CUC_BO`), độ mờ FWHM và SNR, trả về `ChatLuongAnh`.
- **Đo đơn khung & đa khung:** `do_delta_y_tu_anh` trả về `KetQuaDoDeltaY` (với `delta_y_px` và `sai_so_delta_y_px` = $\sqrt{\sigma_{\text{mẫu}}^2 + \sigma_{\text{tc}}^2}$). `do_delta_y_da_khung_hinh` trả về `KetQuaDoDaKhungHinh` lấy trung vị chống ngoại lai và phát hiện trôi tuyến tính theo thời gian; `phan_tich_can_bang_nhiet` khớp đường cân bằng nhiệt trên chuỗi $\Delta y(t)$ theo `KetQuaCanBangNhiet`.

### 1.4. Đường chuẩn đa biến & Bất định (`core/calibration.py`)
- **Đọc CSV & bảo vệ dữ liệu:** `doc_csv_hieu_chuan` chuẩn hóa cột, gắn nhãn `NHAN_CHUA_XAC_DINH` nếu thiếu cột nguồn; `phat_hien_ban_sao_du_lieu` phát hiện dòng trùng lặp (`DU_LIEU_CO_BAN_SAO`) và khi `loai_ban_sao_khi_khop` bật trong `CauHinhHieuChuan`, giữ bản đầu tiên để tránh thổi phồng bậc tự do và rò rỉ CV.
- **Mô hình hồi quy:** `tao_mo_hinh` và `dung_duong_chuan` khớp mô hình $\Delta y(S, T, D)$ có cả số hạng nhiệt độ $(T - 25)$ và chênh lệch hai ngăn $D = T_{\text{mẫu}} - T_{\text{tc}}$, chọn bậc tối ưu qua CV 5-fold (`chia_train_test`), trả về `MoHinhHieuChuan` và `BaoCaoHieuChuan`.
- **Giải ngược độ mặn & bất định:** `uoc_luong_do_man` giải ngược $S$ (‰) và truyền bất định từ phần dư đường chuẩn, sai số đo $\Delta y$, bất định nhiệt kế ($\sigma_T$ có xét sàn phân giải $\sigma_{\text{pg}}$) và bất định chênh nhiệt hai ngăn $D$, trả về `KetQuaDoMan` với `S_ppt`, `u_S_ppt`, `U_S_ppt`.

### 1.5. Các module hỗ trợ thí nghiệm, hiệu chuẩn phần cứng & ngưỡng loài
- `core/nhiet_ke.py`: `HieuChuanCheoNhietKe` và `offset_va_sigma_tai` hiệu chuẩn chéo hai nhiệt kế để bù sai số lệch hệ thống giữa $T_{\text{mẫu}}$ và $T_{\text{tc}}$; `uoc_luong_do_phan_giai` nâng sàn bất định khi nhiệt kế chia thô.
- `core/thang.py`: `tinh_thang_tu_hai_diem` và `quy_doi_delta_y_sang_mm` quy đổi $\Delta y$ từ pixel sang mm tại màn hứng; `doc_exif_may_anh` và `doc_exif_phoi_sang` kiểm tra EXIF thật của ảnh.
- `core/ong_kinh.py`: `hieu_chuan_tu_anh_ban_co` và `sua_meo_anh` hiệu chỉnh méo xuyên tâm ống kính qua `ThamSoOngKinh`; `kiem_tra_vung_meo_ong_kinh` cảnh báo khi vạch nằm gần rìa ảnh.
- `core/thresholds.py`: `doc_danh_sach_loai` và `danh_gia_do_man_loai` đối chiếu $S \pm U$ với ngưỡng sinh học trong `config.yaml` (trả `KetQuaDanhGiaLoai`, giữ `tao_ket_qua_khong_danh_gia_duoc` khi nguồn ngưỡng chưa xác thực).
- `core/kiem_tra_thiet_ke.py`: `kiem_tra_thiet_ke_thi_nghiem` kiểm tra độ phủ lưới $S \times T$, số lần lặp mỗi ô, bản sao và dải đo trước khi dựng đường chuẩn.
- `core/trang_thai_cau_hinh.py`: `liet_ke_tham_so_chua_xac_nhan` quản lí danh sách `DANH_MUC_GIA_DINH` và trạng thái xác nhận Quan–Fry (`phan_tich_xac_nhan_quan_fry`).

### 1.6. Các module Vòng 6 phục vụ thu & phân tích dữ liệu thật (X1–X5)
- `core/thu_du_lieu.py` (X1): `tao_phien_thu_du_lieu`, `ghi_lan_do_thu_du_lieu`, `danh_dau_loai_bo_lan_do` và `tinh_tien_do_thu_du_lieu` quản lí phiên thu dữ liệu chuẩn, chặn ảnh trùng SHA-256 (`LoiTrungAnhThuDuLieuError`), ép đủ hai nhiệt độ và bảo vệ W0.
- `core/troi_laser.py` (X2): `phan_tich_chuoi_troi_laser` và `phan_tich_troi_laser_tu_thu_muc` đo tốc độ trôi khi hai ngăn cùng chứa nước cất, phát hiện bất thường warm-up, ước lượng $\kappa = 1 - \sigma(\Delta y)/\sigma_{\text{đơn}}$ kèm KTC 95% circular block-bootstrap; `ap_dung_troi_laser_vao_tham_so` ghi bảo thủ $1 - \kappa_{\text{lo}}$ vào `data/tham_so_do_duoc.json`.
- `core/can_bang_nhiet.py` (X3): `khop_lan_do_can_bang_nhiet` và `phan_tich_can_bang_nhiet_tu_df` khớp $D(t) = D_\infty + D_0 e^{-t/\tau}$, tính thời gian chờ $t_{\text{chờ}}$ kèm bất định và đề xuất `sigma_D_khi_chua_do_C`, `sigma_D_khi_da_on_dinh_C` qua `ap_dung_can_bang_nhiet_vao_tham_so`.
- `core/chuyen_duong_chuan.py` (X4): `phan_tich_chuyen_duong_chuan` chạy LOPO theo `id_dien_thoai` và LOBO theo `ma_me_pha` trên cả `px` và `mm`, bật cờ `DUONG_CHUAN_KHONG_CHUYEN_DUOC` khi RMS vượt ngưỡng.
- `core/so_sanh_ngan_sach.py` (X5): `phan_ra_phuong_sai_phan_du` và `so_sanh_ngan_sach_sai_so` phân rã ANOVA phần dư thực nghiệm (lặp lại, mẻ pha, điện thoại, nhiệt độ dư, trôi laser) và đối chiếu với `ngan_sach_sai_so` lí thuyết.

---

## 2. Ví dụ số chạy trực tiếp trên ảnh mô phỏng (`seed=42`)

> [!NOTE]
> Toàn bộ số liệu trong mục này là **MÔ PHỎNG** được tạo bằng `ThamSoMoPhong` và `sinh_du_lieu_hieu_chuan_mo_phong` với `seed=42` để minh họa luồng tính toán từ ảnh đến độ mặn $S \pm U$.

1. **Tạo bộ dữ liệu hiệu chuẩn mô phỏng:** Gọi `sinh_du_lieu_hieu_chuan_mo_phong` với `seed=42` và dựng mô hình qua `dung_duong_chuan` -> chọn đường chuẩn bậc 2 (`bac=2`).
2. **Tạo ảnh 2 vạch mô phỏng:** `ThamSoMoPhong` tại $S = 15.0\,‰$, $T = 25.0\,^\circ\text{C}$, $T_{\text{tc}} = 25.0\,^\circ\text{C}$, `seed=42` qua `sinh_anh_hai_vach_mo_phong` cho giá trị lí thuyết `delta_y_ly_thuyet_px = 75.448039` px.
3. **Đo tâm 2 vạch bằng Gauss cột:** Gọi `do_delta_y_tu_anh` (không vẽ ảnh đánh dấu qua tham số `tao_anh_ve`) tại cột tham chiếu `x_ref = 200.0`:
   - Vạch tham chiếu (`vach_tham_chieu`): `y_tam = 79.999259` px
   - Vạch mẫu (`vach_mau`): `y_tam = 155.443027` px
   - Hiệu vi sai đo được: `delta_y_px = 75.443769` px (sai lệch so với lí thuyết khoảng $-0.0043$ px), bất định đo $\sigma_{\Delta y} =$ `sai_so_delta_y_px = 0.006078` px.
4. **Giải ngược độ mặn và tính bất định:** Gọi `uoc_luong_do_man` trên `MoHinhHieuChuan` bậc `2` với `delta_y_px = 75.443769`, $T = 25.0\,^\circ\text{C}$, $T_{\text{tham\_chieu}} = 25.0\,^\circ\text{C}$:
   - Độ mặn ước lượng: `S_ppt = 15.000275` ‰
   - Bất định chuẩn ($1\sigma$): `u_S_ppt = 0.009355` ‰
   - Bất định mở rộng ($k = 2$): `U_S_ppt = 0.018711` ‰
   - Kết quả minh họa (MÔ PHỎNG): $S = 15.000275 \pm 0.018711\,‰$.

---

## 3. 10 câu hỏi phỏng vấn khó từ Hội đồng KHKT & Cách trả lời

1. **Tại sao phải dùng lăng kính hai ngăn (vi sai) thay vì một ngăn đơn rồi trừ mốc cố định?**
   Khi chiếu qua hai ngăn đặt cạnh nhau trên cùng một đường truyền laser và cùng một khung hình camera, mọi nhiễu cộng tính chung (trôi nhiệt diode laser, rung nhẹ giá đỡ, dịch chuyển màn hứng) tác động gần như đồng thời lên cả $y_{\text{tc}}$ và $y_{\text{mẫu}}$, nên hiệu $\Delta y = y_{\text{mẫu}} - y_{\text{tc}}$ triệt tiêu phần trôi chung đó. Mức triệt thực tế không được giả định bằng 100% mà phải đo bằng thí nghiệm hai ngăn nước cất trong `core/troi_laser.py` qua $\kappa = 1 - \sigma(\Delta y)/\sigma_{\text{đơn}}$.
2. **Tại sao trong mô hình lại phải tách riêng nhiệt độ mẫu $T_{\text{mẫu}}$ và chênh lệch hai ngăn $D = T_{\text{mẫu}} - T_{\text{tc}}$?**
   Vì chiết suất nước phụ thuộc vào cả nhiệt độ lẫn độ mặn ($n(S, T)$). Nếu cả hai ngăn cùng nóng lên như nhau ($D = 0$), ảnh hưởng nhiệt độ lên nước cất và nước muối gần giống nhau nhưng vẫn còn phần chênh chéo $\partial^2 n / (\partial S \partial T)$. Ngược lại, khi mới đổ mẫu nước nóng/lạnh vào ngăn mẫu ($D \ne 0$), chỉ một ngăn đổi nhiệt độ nên gây lệch $\Delta y$ trực tiếp tỉ lệ với $|dn/dT|\cdot D$.
3. **Nếu đổ mẫu vào rồi đo ngay chưa đợi cân bằng nhiệt thì sai số bao nhiêu và xử lí thế nào?**
   Module `core/can_bang_nhiet.py` khớp chuỗi $D(t) = D_\infty + D_0 e^{-t/\tau}$ để tìm hằng số thời gian $\tau$, thời gian chờ $t_{\text{chờ}}$ để $|D - D_\infty| \le 0.3\,^\circ\text{C}$ và tính phân vị 90% của $|D|$ khi chưa ổn định (`sigma_D_khi_chua_do_C`) so với khi đã ổn định (`sigma_D_khi_da_on_dinh_C`). Bất định này được truyền thẳng vào ngân sách sai số và `uoc_luong_do_man`.
4. **Làm sao hội đồng biết nhóm không lấy ảnh mô phỏng gắn nhãn "ảnh thật"?**
   Mọi ảnh mô phỏng sinh từ `sim/synth.py` đều bị nhúng chữ kí metadata và lưu dấu vân tay SHA-256 vào sổ ảnh mô phỏng. Các luồng thu và xử lí dữ liệu (`core/thu_du_lieu.py`, `core/troi_laser.py`, `scripts/xu_ly_thu_muc_anh.py`) tự động chặn và báo lỗi nếu phát hiện ảnh mô phỏng bị gắn nhãn `THUC_TE`, đồng thời yêu cầu EXIF máy ảnh thật cho dữ liệu thực nghiệm.
5. **Nếu đổi điện thoại khác hoặc đổi khoảng cách chụp, đường chuẩn theo pixel có dùng lại được không?**
   Không trực tiếp nếu hệ số phóng đại `px_per_mm` thay đổi! Khi đổi điện thoại, cùng một độ dịch mm trên màn hứng sẽ ứng với số pixel khác nhau. Module `core/chuyen_duong_chuan.py` chạy LOPO (`id_dien_thoai`) và LOBO (`ma_me_pha`) để kiểm chứng: quy đổi sang mm tại màn hứng (`core/thang.py`) giúp loại bỏ sai số tỉ lệ giữa các điện thoại; nếu RMS ngoài nhóm vẫn vượt ngưỡng, hệ thống bật cờ `DUONG_CHUAN_KHONG_CHUYEN_DUOC`.
6. **Tại sao lại lấy $1 - \kappa_{\text{lo}}$ (cận dưới 95%) thay vì $1 - \kappa$ trung bình khi áp dụng vào ngân sách sai số?**
   Để giữ nguyên tắc thận trọng trong đo lường khoa học: $\kappa$ ước lượng từ một chuỗi hữu hạn có sai số lấy mẫu (và tự tương quan theo thời gian), nên dùng circular block-bootstrap lấy cận dưới 95% $\kappa_{\text{lo}}$ sẽ cho hệ số lọt nhiễu chung bảo thủ $1 - \kappa_{\text{lo}}$, tránh đánh giá thấp bất định thiết bị.
7. **Nhiệt kế điện tử chỉ hiển thị bước nhảy $0.1\,^\circ\text{C}$ hoặc $0.5\,^\circ\text{C}$ thì ảnh hưởng gì đến bất định độ mặn?**
   Một nhiệt kế có độ chia $r$ gây ra sai số lượng tử hóa phân bố đều với độ lệch chuẩn $\sigma_{\text{pg}} = r / \sqrt{12}$ (và cho hiệu hai nhiệt kế là $r/\sqrt{6}$). Module `core/nhiet_ke.py` và `core/calibration.py` tự động áp sàn độ phân giải này để không bao giờ báo bất định nhỏ giả tạo khi dùng nhiệt kế chia thô.
8. **Tại sao phần mềm báo thêm cả `DOM_BAO_HOA_CUC_BO` thay vì chặn hết mọi ảnh có điểm ảnh bằng 255?**
   Laser thực tế chiếu qua nhựa/mica thường có hạt đốm speckle gây vài pixel bão hòa cục bộ nhưng phần lớn cột ảnh vẫn giữ dạng Gauss chuẩn. Phân biệt giữa đốm cục bộ (`DOM_BAO_HOA_CUC_BO`, cảnh báo nhẹ) và bẹt đỉnh diện rộng (`BAO_HOA_NGHIEM_TRONG`, chặn kết quả) giúp không loại nhầm ảnh đo tốt mà vẫn bảo vệ được độ chính xác định tâm.
9. **Độ lệch chuẩn $\sigma_{\text{lặp\_lại}}$ trong phòng thí nghiệm giống hay khác với ngân sách sai số lí thuyết `ngan_sach_sai_so`?**
   Khác: `ngan_sach_sai_so` là dự toán lí thuyết từ các thông số giả định (hoặc đo riêng lẻ), còn `core/so_sanh_ngan_sach.py` phân rã phương sai phần dư thực nghiệm $\hat{S} - S$ theo lặp lại, mẻ pha, điện thoại và nhiệt độ dư. Nếu sai số thực nghiệm vượt quá `he_so_canh_bao` lần lí thuyết, hệ thống bật cờ `SAI_SO_THUC_VUOT_LY_THUYET` để nhóm tìm nguyên nhân còn thiếu.
10. **Tại sao đến nay phần mềm vẫn không ghi sẵn "sai số thiết bị là ±0.5 ‰"?**
    Vì hiện tại trong kho mã chỉ có dữ liệu mô phỏng và cấu hình giả định. Mọi khẳng định về độ chính xác của thiết bị thật chỉ được phép phát biểu sau khi nhóm thu đủ ảnh thật, hiệu chuẩn chéo nhiệt kế, đo trôi laser, đo cân bằng nhiệt, dựng đường chuẩn thực nghiệm và đối chiếu khúc xạ kế chuẩn bằng Bland–Altman.

---

## 4. Những điều KHÔNG được phép khẳng định khi chưa có số đo thật

- **KHÔNG** khẳng định thiết bị thật đạt độ chính xác, sai số $\pm x\,‰$ hay giới hạn phát hiện bao nhiêu ‰ từ kết quả chạy dữ liệu mô phỏng.
- **KHÔNG** khẳng định đường chuẩn dùng chung được cho mọi điện thoại khi chưa kiểm LOPO bằng `core/chuyen_duong_chuan.py` trên ít nhất 2 điện thoại thật có đo `px_per_mm`.
- **KHÔNG** khẳng định hệ số triệt nhiễu chung là 0.01 (99%) khi chưa đo chuỗi nước cất hai ngăn $\ge 20$ phút qua `core/troi_laser.py`.
- **KHÔNG** khẳng định mẫu ổn định nhiệt ngay sau khi đổ khi chưa đo đường suy giảm $D(t)$ qua `core/can_bang_nhiet.py`.
- **KHÔNG** dùng ngưỡng sinh học trong `config.yaml` như khuyến cáo nuôi trồng chính thức nếu chưa đối chiếu nguồn TCVN/QCVN gốc.

---

## 5. Bảng tự khai báo của học sinh trước khi phỏng vấn (Để trống tự điền)

| Hạng mục trong dự án | Phần nhóm học sinh tự thực hiện & hiểu rõ | Phần có tham khảo / AI hỗ trợ | Minh chứng tự kiểm chứng được |
| :--- | :--- | :--- | :--- |
| Lắp đặt phần cứng quang học (laser, lăng kính 2 ngăn, màn hứng) | | | |
| Pha mẫu chuẩn NaCl theo khối lượng & ghi chép nhiệt độ | | | |
| Chụp chuỗi trôi laser & chuỗi cân bằng nhiệt thực nghiệm | | | |
| Hiểu công thức vật lí (Snell, Gauss 1D, $D = T_{\text{mẫu}} - T_{\text{tc}}$, truyền bất định) | | | |
| Hiểu luồng code Python / Web & kiểm thử tự động | | | |
