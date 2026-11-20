# BÁO CÁO THAY ĐỔI DỰ ÁN KHKT (P0 → P1 → P2)

> **Dự án:** Đo độ mặn nước bằng khúc xạ laser qua lăng kính hai ngăn (vi sai) + camera điện thoại  
> **Nguyên tắc thực hiện:** Trung thực dữ liệu, không bịa số liệu/nguồn/kết quả thực nghiệm, dữ liệu mô phỏng luôn gắn nhãn rõ ràng, làm tuần tự P0 → P1 → P2 và kiểm thử + commit riêng sau từng nhiệm vụ.

---

## 1. Kết quả kiểm thử trước và sau khi sửa

| Thời điểm | Lệnh chạy | Kết quả thực tế | Ghi chú |
| :--- | :--- | :--- | :--- |
| **Cơ sở (trước T1)** | `python -m pytest tests -q` | **`58 passed`**, 0 failed (29.89s) | Lưu tại commit `bf060f6` |
| **Sau hoàn tất T1–T12** | `python -m pytest tests -q` | **`79 passed`**, 0 failed (43.32s trước commit báo cáo) | Mọi test mới cho T1–T11 đều pass không bỏ qua |
| **Kiểm tra cú pháp JS** | `node --check app/static/app.js` | Exit code `0` | Xác nhận sau mỗi lần sửa frontend |

---

## 2. Danh sách thay đổi theo từng nhiệm vụ (T1–T12) kèm commit git

| Mã NV | Ưu tiên | Commit hash | Tóm tắt thay đổi & file ảnh hưởng |
| :--- | :---: | :---: | :--- |
| **Baseline** | — | `bf060f6` | Lưu trạng thái cơ sở (`58 passed`) trước chuỗi nâng cấp P0–P2 (`README.md`, `app/web_app.py`, `app/static/app.js`, `app/static/index.html`, `core/calibration.py`). |
| **T1** | P0 | `5f0b104` | **Làm sạch CSV mẫu & bỏ mặc định `THUC_TE`:** `data/mau_hieu_chuan.csv` chỉ giữ dòng tiêu đề 13 cột; `core/calibration.py` gán `CHUA_XAC_DINH` khi thiếu `nguon_du_lieu` và chỉ gắn nhãn đo thật khi mọi dòng là `THUC_TE`; cập nhật 3 trạng thái nhãn trong `app/web_app.py` và `app/static/app.js`. (`60 passed`) |
| **T2** | P0 | `942e6f4` | **Xóa ngưỡng/nguồn chưa kiểm chứng & bỏ lời khuyên tự ý:** Đưa toàn bộ ngưỡng trong `config.yaml` về `null` và `nguon_tham_khao: ""`; bổ sung `giai_doan` tùy chọn ở `core/thresholds.py` và `app/web_app.py`; xóa mọi lời khuyên hành động không nguồn, chỉ hiển thị trạng thái, khoảng tham chiếu, giá trị đo, nguồn và dòng liên hệ khuyến nông/khuyến ngư. (`60 passed`) |
| **T3** | P0 | `d6f09bf` | **Sửa mô tả nói quá trong `README.md` và `sim/synth.py`:** Sửa khẳng định triệt tiêu hoàn toàn trôi/rung (nêu rõ `he_so_triet_chung` chưa đo), nhấn mạnh độ lặp lại sub-pixel hiện mới đo trên ảnh MÔ PHỎNG, cập nhật khuyến cáo hiệu chuẩn tới `≥ 35 °C`, nêu giới hạn dải hiệu lực Quan–Fry và khác biệt nước ao vs NaCl; sửa docstring `sim/synth.py`. (`60 passed`) |
| **T4** | P1 | `c0695a4` | **Bổ sung chênh nhiệt độ hai ngăn $D = T_{\text{mẫu}} - T_{\text{tc}}$ & bỏ mặc định 25 °C:** Thêm cột `nhiet_do_tham_chieu_C`, cảnh báo giả định cân bằng nhiệt khi thiếu, thêm số hạng `D`/`SD` và bất định nhiệt độ tham chiếu trong `core/calibration.py` (`cau_hinh.nguong_lech_T_hai_ngan_C: 0.5`); cho phép `T_tham_chieu_C` độc lập trong `sim/synth.py`; bỏ mặc định 25 °C và bổ sung tùy chọn "Không đo nhiệt độ" trong `app/web_app.py`, `index.html`, `app.js`. (`62 passed`) |
| **T5** | P1 | `514ffd3` | **Thang `px/mm` theo từng ảnh, chuẩn `mm`, khóa AE/AF & EXIF:** Tạo `core/thang.py` (`tinh_thang_tu_hai_diem`, `quy_doi_delta_y_sang_mm`, `doc_exif_phoi_sang`); hỗ trợ `don_vi_y: "px" \| "mm"` và cảnh báo khi dùng `px` trong `core/calibration.py`; thêm UI chọn 2 điểm trên ảnh, checkbox AE/AF lock và lưu EXIF/thang vào SQLite (`app/web_app.py`, `index.html`, `app.js`); thêm `tests/test_thang.py`. (`66 passed`) |
| **T6** | P1 | `6341acc` | **Cổng chất lượng, bão hòa theo cột, SNR 2 vùng, `[S - U, S + U]` & phân loại lỗi:** Chuyển kiểm tra bão hòa sang tỉ lệ cột có đỉnh ≥ ngưỡng và tính SNR cho CẢ HAI vùng lấy min (`config.yaml` nâng mặc định `snr_toi_thieu: 10.0`) trong `core/measure.py`; thêm phân loại theo khoảng `[S - U, S + U]` với trạng thái `SAT_RANH_GIOI` và `KHONG_DANH_GIA_DUOC` ở `core/thresholds.py`, `styles.css`, `app.js`; phân loại rõ 4 mã lỗi HTTP (`ANH_KHONG_HOP_LE`, `KHONG_TIM_THAY_VACH`, `LOI_MO_HINH_GIAI_NGUOC`, `DAU_VAO_KHONG_HOP_LE`) trong `app/web_app.py`. (`70 passed`) |
| **T7** | P1 | `73f35a3` | **Hiệu chuẩn trung thực hơn:** Thêm `ma_me_pha` và `ngay_do`; chia train/test theo nhóm mẻ pha và GroupKFold thuần NumPy khi đủ `ma_me_pha` (cảnh báo khi thiếu), thêm `sai_so_dung_dich_chuan_ppt: null` vào thành phần bất định/cảnh báo và `nhiet_do_toi_thieu_phu_C: null` cảnh báo dải nhiệt độ hẹp (`config.yaml`, `core/calibration.py`, `app/web_app.py`, `app.js`). (`72 passed`) |
| **T8** | P1 | `3b94ff5` | **Thuật toán tìm tâm & đa khung trung thực:** `core/spot.py` bổ sung cắt ngoại lai 3σ lặp (tối đa 3 lần), chặn tỉ số trọng số, đếm riêng `so_cot_dung_centroid`; `core/measure.py` bỏ `except Exception: continue`, ghi `khung_loi`, lấy chất lượng xấu nhất toàn chuỗi, phát hiện trôi tuyến tính theo chỉ số khung và dao động độ sáng đỉnh > 15%; thêm endpoint `POST /api/measure-multi` và UI chọn nhiều ảnh/video ngắn/chuỗi 5 khung (`app/web_app.py`, `index.html`, `app.js`). (`75 passed`) |
| **T9** | P2 | `8e46df2` | **Mô phỏng thực tế hơn (mặc định TẮT), watermark+JSON & độ bền vững:** `sim/synth.py` bổ sung 7 tham số nhiễu/biến dạng tùy chọn (`speckle_cuong_do`, `meo_ong_kinh_k1`, `gradient_nen_y`, `do_cong_vach`, `chenh_sang_hai_nua`, `gamma_cam_bien`, `chat_luong_jpeg`), bật `gan_watermark=True` mặc định khi lưu PNG kèm file `.json` `{"simulated": true}`; tạo & chạy `scripts/danh_gia_do_ben_vung.py`. (`77 passed`) |
| **T10** | P2 | `d7c2077` | **Công thức chiết suất Quan–Fry (tùy chọn):** Thêm `chiet_suat_quan_fry(S, T, λ)` và cảnh báo ngoài dải `0–30 °C, 0–35 ‰, 400–700 nm` trong `core/optics.py` (`config.yaml` giữ mặc định `"tuyen_tinh"`); tạo & chạy `scripts/so_sanh_quan_fry.py`. (`78 passed`) |
| **T11** | P2 | `7ec3bd9` | **Nhật kí & tốc độ biến đổi độ mặn:** `app/web_app.py` tính `toc_do_ppt_gio ± u_toc_do_ppt_gio` giữa hai lần đo liên tiếp cùng `(vi_tri, nguon_du_lieu)` trong cùng hồ sơ; Tab 3 thêm cột tốc độ và ô ngưỡng cảnh báo tự đặt lưu `localStorage` (không đặt ngưỡng mặc định). (`79 passed`) |
| **T12** | P2 | `d0169f2` | **Vệ sinh dự án & đóng gói:** Cập nhật `.gitignore` (thêm `*.db-wal`, `*.db-shm`, `outputs/*_MO_PHONG*`, `*.zip`), tạo `scripts/dong_goi.py` (đã test đóng gói 45 file, 0 file cấm), tăng `CACHE_STATIC` lên `salinity-static-v4` trong `app/static/sw.js`, đồng bộ `README.md`. (`79 passed`) |

---

## 3. Kết quả chạy thực tế các script bổ sung

### 3.1. Độ bền vững thuật toán trên ảnh MÔ PHỎNG (`T9`)
- **Lệnh tái lập:** `python scripts/danh_gia_do_ben_vung.py` (xuất `outputs/danh_gia_do_ben_vung_MO_PHONG.csv`)
- **Cảnh báo:** Đây là độ bền vững của thuật toán trên ảnh MÔ PHỎNG ($S = 20{,}0\,‰$, $T = 25{,}0\,^\circ\text{C}$, $N = 10$ ảnh/mức), **không phải** sai số thiết bị thật.
- Tóm tắt điểm nổi bật quan sát được:
  - Cơ sở (`0.0`): 10/10 đạt chất lượng, sai lệch TB `+0.0027 px` (`+0.0005 ‰`), ĐLC `0.0070 px` (`0.0014 ‰`).
  - `meo_ong_kinh_k1` (`-0.1`, `-0.05`, `+0.05`, `+0.1`): gây sai lệch hệ thống `+0.5950`, `+0.3415`, `-0.3885`, `-0.8230 px` (`+0.1175` đến `-0.1625 ‰`) do 2 vạch lệch tâm trục quang khác nhau.
  - `gradient_nen_y = 90.0`: 0/10 đạt chất lượng, lệch TB `-185.9863 px` (ĐLC `65.0207 px`) do nền sáng làm sai ngưỡng tách ROI tự động — chứng minh sự cần thiết của việc che sáng môi trường.
  - `speckle_cuong_do = 0.1 / 0.2`: độ phân tán tăng (`0.0391 / 0.0837 px`) và `0/10` đạt ngưỡng chất lượng (vượt ngưỡng bão hòa cục bộ / giảm SNR) dù trung bình sai lệch vẫn nhỏ (`+0.0019 / +0.0058 px`).
  - `do_cong_vach <= 3.0 px`, `chenh_sang_hai_nua <= 0.6`, `gamma_cam_bien ∈ [0.7, 2.0]`, `chat_luong_jpeg ∈ [50, 90]`: 10/10 đạt chất lượng, sai lệch TB `< 0.022 px` (`< 0.005 ‰`).

### 3.2. So sánh độ nhạy nhiệt: Tuyến tính vs Quan–Fry (`T10`)
- **Lệnh tái lập:** `python scripts/so_sanh_quan_fry.py` (xuất `outputs/so_sanh_quan_fry.csv`)
- Với cấu hình mặc định ($A = 40^\circ$, $D = 1{,}0\text{ m}$, $\lambda = 650\text{ nm}$):
  - Độ nhạy theo độ mặn $\partial\Delta y/\partial S$ hai mô hình gần nhau (~`4.93–5.18 px/‰`).
  - Khi hai ngăn **cùng nhiệt độ**, đạo hàm $\partial\Delta y/\partial T$ ở $S = 15\,‰$ rất nhỏ (`-0.022 px/°C` tuyến tính vs `-0.255` đến `-0.003 px/°C` theo Quan–Fry) nhờ triệt vi sai.
  - Khi **chênh nhiệt hai ngăn** ($T_{\text{tc}} = 25\,^\circ\text{C}$), độ nhạy theo chênh nhiệt $\partial\Delta y/\partial D$ lớn hơn hàng chục lần (`~ -2.8 px/°C` tuyến tính; `-1.86` đến `-4.09 px/°C` theo Quan–Fry), khẳng định $D = T_{\text{mẫu}} - T_{\text{tc}}$ là nguồn sai số nhiệt chủ đạo.

---

## 4. Các giả định thận trọng đã chọn (khi gặp điểm mở)

1. **Nguồn dữ liệu hỗn hợp / thiếu cột (`T1`):** Nếu trong cùng file CSV chỉ có **1 dòng** ghi `MO_PHONG`/`SIMULATED` thì cả đường chuẩn gắn nhãn `MÔ PHỎNG`; nếu có dòng trống hoặc thiếu `nguon_du_lieu` thì gán `CHUA_XAC_DINH` (`CHƯA XÁC NHẬN NGUỒN DỮ LIỆU`), tuyệt đối không gắn `"đo thật"`.
2. **Khi chọn "Không đo nhiệt độ" (`T4` + `T6`):** Backend vẫn giải ngược giá trị $\Delta y$ tại $T_{\text{ref}}$ danh định để hiển thị số ước lượng tham khảo, nhưng bật cờ `khong_danh_gia_duoc = True`, giữ `danh_gia_loai = None` và cảnh báo đỏ cấm dùng cho phân loại an toàn loài.
3. **Bất định khi chọn 2 điểm thang ảnh (`T5`):** Khi người dùng không truyền sai số chọn điểm riêng, `core/thang.py` dùng giả định thận trọng `sigma_diem_px = 0.5 px` và `sigma_mm = 0.1 mm` truyền sai số vào `u_px_per_mm`.
4. **Ngưỡng `snr_toi_thieu = 10.0` và quy tắc bão hòa (`T6`):** Đặt `snr_toi_thieu = 10.0` trong `config.yaml` (ghi chú rõ chưa hiệu chuẩn trên ảnh thiết bị thật). Tính tỉ lệ cột bão hòa trên các cột có tín hiệu rõ (`col_max >= nen + 15`, dự phòng toàn vùng khi nền cháy trắng) và dùng trung vị đỉnh cột `col_max` để chỉ số không đổi khi chiều cao ROI thay đổi (`±15, ±40, ±120 px`).
5. **Cổng chất lượng & `SAT_RANH_GIOI` (`T6`):** Ngoài ảnh không hợp lệ, S/T ngoại suy và mô hình mô phỏng/chưa xác nhận nguồn, ảnh mô phỏng trong `api_measure` / `api_measure-multi` cũng bị đánh dấu `KHONG_DANH_GIA_DUOC` (màu xám trung tính `#64748b`). Một khoảng `[max(0, S - U), S + U]` chỉ được xếp `AN_TOAN` (hoặc `CANH_BAO` / `NGUY_HIEM`) khi toàn bộ khoảng nằm gọn trong một vùng duy nhất và không cắt ngang bất kì ranh giới nào.
6. **Chia nhóm `ma_me_pha` (`T7`):** Chỉ kích hoạt Group split & GroupKFold khi cột `ma_me_pha` đầy đủ không ô trống và có ít nhất 2 mẻ khác nhau; khi chia nhóm ưu tiên giữ ở tập train ít nhất 1 mẻ ở `S_min` và `S_max` (nếu có nhiều mẻ) để tránh tập train bị thiếu đầu mút dải đo.
7. **Lọc ngoại lai 3σ trên ảnh sạch (`T8`):** Trong `core/spot.py`, sàn độ lệch chuẩn bền vững tại `max(1.4826 * MAD, 0.05) px` để các ảnh mô phỏng ít nhiễu (`MAD ≈ 0`) không bị loại nhầm cột hợp lệ. Giới hạn tỉ số trọng số mặc định `ty_le_trong_so_toi_da = 100.0` quanh trung vị.
8. **Chênh sáng đa khung & trôi thời gian (`T8`):** Cờ dao động phơi sáng bật khi biên độ đỉnh giữa các khung hợp lệ chênh `> 15%` so với trung vị; cờ trôi theo thời gian bật khi `so_khung_hop_le >= 4`, `|slope| > 2.5 * SE_slope` và tổng dịch toàn chuỗi `> max(0.15 px, 2 * 1.4826 * MAD)`.
9. **Chênh sáng hai nửa (`T9`):** Áp dụng giảm sáng nửa tối theo hệ số `max(0.05, 1 - chenh_sang_hai_nua)` thay vì tăng nửa sáng vượt 255 để không vô tình gây bão hòa cháy sáng ngoài ý muốn.
10. **Ngưỡng tốc độ biến đổi `‰/giờ` (`T11`):** Không đặt sẵn bất kì ngưỡng "an toàn" mặc định nào; ô `#t3-rate-threshold` để trống cho người dùng tự nhập (lưu `localStorage`).

---

## 5. Các bài test đã sửa và lí do

1. `tests/test_calibration.py::test_doc_csv_hop_le_loai_dong_thieu_va_mac_dinh_thuc_te` → đổi thành `test_doc_csv_hop_le_loai_dong_thieu_va_mac_dinh_chua_xac_dinh` (**T1**): Test cũ kỳ vọng hành vi sai (thiếu cột `nguon_du_lieu` lại gán `"THUC_TE"`). Đã sửa để kiểm tra đúng hành vi mới là mặc định `"CHUA_XAC_DINH"` và `la_du_lieu_thuc_te(df) == False`.
2. `tests/test_calibration.py::test_file_mau_csv_doc_duoc_va_khong_co_so_lieu` & `tests/test_web_app.py::test_mau_hieu_chuan_csv_valid` (**T1**): Hai test cũ đọc `data/mau_hieu_chuan.csv` cũ có 16 dòng số liệu hỏng và khẳng định `len(df) > 0`. Sau khi làm sạch CSV mẫu chỉ giữ dòng tiêu đề 13 cột, hai test được cập nhật để kiểm tra đủ cột bắt buộc/tùy chọn và `len(df) == 0`.
3. `tests/test_thresholds.py` (**T2**): Trước đây `test_loai_chua_co_nguon_phai_canh_bao` chỉ kiểm một vài loài, còn `test_danh_gia_muc_an_toan` / `test_danh_gia_cay_nhay_cam` đọc ngưỡng tôm/sầu riêng có sẵn trong `config.yaml` thật. Vì `config.yaml` thật đã được xóa sạch ngưỡng chưa kiểm chứng về `null` theo T2, các test kiểm tra logic phân vùng/lời khuyên phải chuyển sang tạo file YAML tạm trong `tmp_path` mang nhãn rõ `"GIÁ TRỊ THỬ NGHIỆM, KHÔNG PHẢI NGƯỠNG THẬT"`, đồng thời bổ sung `test_config_that_khong_co_nguong_thieu_nguon` kiểm trực tiếp `config.yaml` thật.
4. `tests/test_spot_measure.py::test_loai_ngoai_lai_3_sigma_chan_trong_so_va_dem_centroid` (**T8 — test mới tự viết**): Lần chạy đầu dùng khối hộp chữ nhật rộng 9 px khiến khớp Gauss đơn vẫn đạt `R² ≥ 0.80` (nên không fallback sang centroid) và bị làm tròn `int()` lệch tâm biến thành outlier; đã chỉnh dữ liệu cột test đó thành biên dạng 2 đỉnh đối xứng quanh đúng tâm `mu_x` (có `R² < 0.80`) để thực sự kích hoạt và kiểm chứng cơ chế dự phòng centroid.

---

## 6. Những việc CHỈ người dùng (nhóm thực hiện) mới làm được

Các công việc sau liên quan trực tiếp đến **tài liệu gốc, thiết bị vật lí và đo đạc thực nghiệm thật**, phần mềm không thể tự sinh hay xác minh thay:

1. **Tra cứu tài liệu gốc và điền ngưỡng sinh học có trích dẫn (`T2`):** Đọc tài liệu khuyến nông/khuyến ngư, TCVN/QCVN hoặc bài báo khoa học tin cậy rồi mới điền giá trị vào `nguong_loai` (và `giai_doan` nếu cần) trong `config.yaml`, kèm đủ `nguon_tham_khao` (tác giả, năm, số trang/DOI hoặc số hiệu văn bản).
2. **Thu thập bộ dữ liệu hiệu chuẩn thực nghiệm thật (`T1`, `T4`, `T5`, `T7`):** Pha dải dung dịch chuẩn NaCl từ ≥ 2 mẻ pha riêng (`ma_me_pha`), đo lặp lại qua nhiều ngày (`ngay_do`) và phủ đủ dải nhiệt độ ao nuôi thật (≥ 35 °C nếu có thể), đo đủ `nhiet_do_C` + `nhiet_do_tham_chieu_C`, bật khóa AE/AF, chụp kèm thước để có `px_per_mm`, và chỉ khi đo thật mới ghi `nguon_du_lieu = THUC_TE` vào CSV.
3. **Đo thực nghiệm `he_so_triet_chung` (`T3`):** Cố ý tạo trôi laser/rung động chung đã biết để đo tỉ phần còn sót lại trong `Δy`, thay cho giá trị giả định `0.01` trong `config.yaml`.
4. **Khai báo bất định dụng cụ & dung dịch chuẩn (`T4`, `T7`, `config.yaml`):** Điền sai số nhiệt kế thật vào `hieu_chuan.sai_so_nhiet_ke_C`, độ không đảm bảo của cân/bình định mức vào `hieu_chuan.sai_so_dung_dich_chuan_ppt`, khoảng nhiệt độ tối thiểu cần phủ vào `hieu_chuan.nhiet_do_toi_thieu_phu_C`, khoảng cách màn thật `D_m`, góc đỉnh `A` thật, kích thước pixel chuẩn và kiểm chứng lại ngưỡng `xu_ly_anh.snr_toi_thieu` (`10.0`) trên ảnh thật từ điện thoại của nhóm.
5. **Đối chiếu công thức Quan–Fry với bài báo gốc (`T10`):** Kiểm tra lại 10 hệ số `a0..a9` của `chiet_suat_quan_fry` trong `core/optics.py` đối chiếu trực tiếp với bài báo gốc **Quan & Fry, *Applied Optics* (1995)** trước khi đưa vào báo cáo thi chính thức.
6. **Chuẩn hóa độ đục Formazin (nếu muốn báo NTU):** Hiện tại chỉ số độ đục là thang tương đối `[0–1]`; nếu muốn quy đổi sang đơn vị `NTU`, nhóm phải đo đường chuẩn thực nghiệm riêng bằng dải dung dịch chuẩn Formazin.
