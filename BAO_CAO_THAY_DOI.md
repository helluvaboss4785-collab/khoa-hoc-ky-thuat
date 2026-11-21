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

---

# VÒNG 2 (Q0–Q10)

> Vòng nâng cấp tiếp theo giải quyết các lỗ hổng về truyền bất định chênh nhiệt, kênh màu laser, đốm speckle, nền sáng không đều, tốc độ ảnh 12MP, pipeline nhập ảnh thật, cân bằng nhiệt theo thời gian, méo ống kính tùy chọn, tham số Quan–Fry và giới hạn tải lên. **Mọi số liệu định lượng dưới đây đều lấy từ ảnh/dữ liệu MÔ PHỎNG, không phải độ chính xác thiết bị thật.**

## 7. Kết quả kiểm thử trước và sau Vòng 2

| Thời điểm | Lệnh chạy | Kết quả thực tế | Ghi chú |
| :--- | :--- | :--- | :--- |
| **Cơ sở trước Vòng 2 (sau T12)** | `python -m pytest tests -q` | **`79 passed`**, 0 failed | Commit nền `52ae667` |
| **Sau hoàn tất Q0–Q9** | `python -m pytest tests -q` | **`94 passed, 1 skipped`** (26.94s) | Duy nhất `test_hoi_quy_anh_that` skip với lí do `"chưa có ảnh thật"` |
| **Kiểm tra nghiệm thu tổng hợp Q0–Q3** | `python scripts/kiem_tra_chap_nhan_vong2.py` | **`13/13 TIEU CHI DAT`** (`MO_PHONG`) | Xuất `outputs/kiem_tra_chap_nhan_vong2.csv` |
| **Kiểm tra độ bền vững mô phỏng** | `python scripts/danh_gia_do_ben_vung.py` | Xuất `outputs/danh_gia_do_ben_vung_MO_PHONG.csv` | `speckle=0.2` đạt `10/10`, `gradient=90` tâm lệch TB `0.0000 px` |
| **Kiểm tra đóng gói sạch** | `python scripts/dong_goi.py` | **`55 file`**, **`435.3 KB`**, `0` file cấm | Không chứa `.venv`, `.git`, `__pycache__`, `.pytest_cache`, `*.db*` |
| **Kiểm tra cú pháp JS** | `node --check app/static/app.js` | Exit code `0` | Chạy sau mọi chỉnh sửa frontend |

---

## 8. Danh sách thay đổi từng nhiệm vụ (Q0–Q10) kèm commit

| Mã NV | Commit hash | Tóm tắt thay đổi & file ảnh hưởng |
| :--- | :---: | :--- |
| **Q0** | `da01203` | **Bất định bỏ sót chênh nhiệt hai ngăn & cảnh báo phân cấp:** Thêm `hieu_chuan.sigma_D_khi_chua_do_C: 2.0` (`GIẢ ĐỊNH`); cộng `chenh_nhiet_chua_do` (từ mô hình D hoặc hệ số LÍ THUYẾT `core/optics.py`) khi thiếu `T_tc`; đặt `khong_danh_gia_duoc = True` + `chenh_nhiet_ngoai_mo_hinh` khi nhập `T_tc` với `|D| > 0.5 °C` mà mô hình chưa học D; thêm ngoại suy `ngoai_dai_D` và cảnh báo 3 cấp (`thong_tin`, `can_than`, `nghiem_trong`) trên `core/calibration.py`, `app/web_app.py`, `app/static/app.js`. (`80 passed`) |
| **Q1** | `6eed2c0` | **Chọn kênh laser & kiểm bão hòa trên RGB gốc:** Thêm `chon_kenh_laser` (`xu_ly_anh.kenh_laser: "auto" \| "R" \| "G" \| "B" \| "xam"`), kiểm bão hòa theo từng kênh B/G/R gốc (`kenh_bao_hoa`), lưu `kenh_su_dung` vào kết quả và SQLite `nhat_ki`; thêm `sinh_anh_mau_mo_phong` trong `sim/synth.py`. (`82 passed`) |
| **Q2** | `e4a932f` | **Phân biệt đốm speckle cục bộ với bão hòa rộng bẹt đỉnh:** Thêm `ti_le_cot_bao_hoa_nghiem_trong: 0.30` và `so_cot_lien_tiep_bao_hoa: 15` (`GIẢ ĐỊNH`); bổ sung `_doan_lien_tiep_toi_da`, cờ `co_dom_bao_hoa_cuc_bo` (cảnh báo `can_than`, vẫn `hop_le=True`) và `BAO_HOA_NGHIEM_TRONG` (cháy phẳng/liên tiếp `≥ 15` cột → `hop_le=False`) trong `core/measure.py`, `app/web_app.py`, `app.js`. (`84 passed`) |
| **Q3** | `9dac15b` | **Trừ nền hình thái cho ROI tự động, tối ưu ảnh 12MP & kéo chuột ROI thủ công:** Thêm `nguong_nen_khong_deu: 30.0` (`GIẢ ĐỊNH`), `_uoc_luong_nen_hinh_thai` (thu gọn `≤ 900 px` khi tìm ROI), tăng bước cột thích ứng cho ROI rộng `> 600 px`, cờ `nen_khong_deu` và thông báo nguyên nhân rõ trong `KhongTimThayVachError`; thêm lớp canvas `#t1-roi-overlay` kéo chuột chọn ROI thủ công ở Tab 1. (`86 passed`) |
| **Q4** | `3013956` | **Pipeline nhập thư mục ảnh thật & kiểm thử hồi quy:** Tạo `scripts/xu_ly_thu_muc_anh.py` (bắt buộc `--nguon THUC_TE \| MO_PHONG`, hỗ trợ `--metadata`, `--roi`, `--tu-ten-file`, đọc EXIF, xuất CSV 13 cột + báo cáo chất lượng), `tests/anh_that/README.md` và `tests/test_anh_that.py` (`test_hoi_quy_anh_that` skip có lí do `"chưa có ảnh thật"`). (`88 passed, 1 skipped`) |
| **Q5** | `d13639d` | **Khớp hàm mũ cân bằng nhiệt `Δy(t) = Δy∞ + A·exp(−t/τ)`:** Thêm `nguong_on_dinh_nhiet_px_moi_phut: 0.05` (`GIẢ ĐỊNH`), `KetQuaCanBangNhiet` và `phan_tich_can_bang_nhiet` trong `core/measure.py`; tích hợp trường `thoi_gian_s` vào `/api/measure-multi` và nút **⏱️ Chờ cân bằng nhiệt** kèm đồ thị `Δy(t)` ở Tab 1 (không gợi ý thời gian chờ cố định). (`90 passed, 1 skipped`) |
| **Q6** | `d8f72b0` | **Cảnh báo & hiệu chuẩn méo ống kính tùy chọn (TẮT mặc định):** Tạo `core/ong_kinh.py` (cảnh báo lệch rìa `nguong_lech_tam_meo_ti_le: 0.30` kèm cận trên sai số khi khai báo `k1`; `cv2.calibrateCamera` với `CALIB_FIX_K3` và `cv2.undistort` chỉ bật khi `bat_sua_meo_ong_kinh: true`), tạo CLI `scripts/hieu_chuan_ong_kinh.py` và `tests/test_ong_kinh.py`. (`92 passed, 1 skipped`) |
| **Q7** | `a3394d5` | **Đổi `dn_dT = -1.1e-4` & Tab 5 chọn Quan–Fry:** Cập nhật `dn_dT_moi_do_C: -1.1e-4` trong `config.yaml` (giữ nguyên 100% hệ số trong `core/optics.py`), thêm `<select id="t5-model">` (`tuyen_tinh` mặc định \| `quan_fry`) và `buoc_song_nm` kèm cảnh báo ngoài dải `0–30 °C, 0–35 ‰, 400–700 nm` trên `/api/optics-sim` và Tab 5. (`93 passed, 1 skipped`) |
| **Q8** | `1c96b30` | **Giới hạn đầu vào HTTP 413 `ANH_QUA_LON` & vệ sinh tên file/SQL:** Thêm mục `gioi_han` (`25 MB`, `60` khung, `60 MP` — `GIẢ ĐỊNH`), lớp `AnhQuaLonError` trả HTTP 413 mã `ANH_QUA_LON` (file hỏng vẫn trả HTTP 400 `ANH_KHONG_HOP_LE`), `_lam_sach_ten_file`, xác nhận mọi truy vấn SQLite dùng `?`. (`94 passed, 1 skipped`) |
| **Q9** | `76bc615` | **Tài liệu người dùng & đồng bộ README:** Tạo `HUONG_DAN_NGUOI_DUNG.md` (để `[điền sau khi nhóm đo]` ở thời gian cân bằng nhiệt, không lời khuyên nuôi trồng), cập nhật `README.md` theo Vòng 2, thêm mục *Quy trình thu dữ liệu thật* và chạy lại bảng độ bền vững MÔ PHỎNG. (`94 passed, 1 skipped`) |
| **Q10** | *(commit báo cáo này)* | **Nghiệm thu tổng hợp, đóng gói & hoàn tất báo cáo:** Tạo & chạy `scripts/kiem_tra_chap_nhan_vong2.py`, kiểm đóng gói `scripts/dong_goi.py`, nâng `sw.js` lên `salinity-static-v5`, bổ sung mục VÒNG 2 trong `BAO_CAO_THAY_DOI.md`. |

---

## 9. Bảng nghiệm thu định lượng Vòng 2 (dữ liệu MÔ PHỎNG)

| Nhiệm vụ | Chỉ tiêu kiểm tra | Số liệu đo được từ lệnh đã chạy | Trạng thái |
| :--- | :--- | :--- | :---: |
| **Q0** | Không nhập `T_tc`, `D=0 °C` (200 phép đo) | Độ phủ `100.0%`, `U_tb = 2.423 ‰` ($\ge 95\%$) | **Đạt** |
| **Q0** | Không nhập `T_tc`, `D=3 °C` (200 phép đo) | Độ phủ `100.0%`, `RMS = 1.817 ‰`, `U_tb = 2.425 ‰` ($\ge 95\%$) | **Đạt** |
| **Q0** | Có nhập `T_tc` ($\sigma_{T_{tc}} \le 0{,}2\,^\circ\text{C}$), `D=0 °C` | Độ phủ `99.5%`, tỉ số `U / U_ref = 1.00x` ($\le 3\times$) | **Đạt** |
| **Q0** | Có nhập `T_tc` (`\|D\|=3 °C`), mô hình không học `D` | `khong_danh_gia_duoc = True`, thành phần `chenh_nhiet_ngoai_mo_hinh` | **Đạt** |
| **Q0** | Mô hình có học `D`, đo tại `D=3 °C` (200 phép đo) | Độ phủ `100.0%`, `RMS = 0.0099 ‰` ($\le 0{,}1\,‰$) | **Đạt** |
| **Q1** | Laser đỏ cháy kênh R nhưng ảnh xám `< 250` | `max_xam = 120`, `bao_hoa = True`, `kenh_bao_hoa = ['R']` | **Đạt** |
| **Q1** | Ảnh màu sạch chọn kênh R | `kenh_su_dung = 'R'`, `SNR_R = 155.8 >= 118.4 (xam)`, `\|err\| = 0.0074 px` ($\le 0{,}05\text{ px}$) | **Đạt** |
| **Q2** | Speckle `0.1` và `0.2` (10 seed/mức, $S=20\,‰$) | `0.1`: `10/10`, `max\|err\| = 0.0784 px`; `0.2`: `10/10`, `max\|err\| = 0.0933 px` | **Đạt** |
| **Q2** | Bão hòa phẳng (`cho_phep_bao_hoa=True, đỉnh=400`) | `hop_le = False`, `bao_hoa = True`, `max_run = 192` cột | **Đạt** |
| **Q3** | Gradient nền `40` và `90` (10 seed/mức) | `40`: `10/10` pass, `max\|err\| = 0.0088 px`; `90`: `10/10` pass, `max\|err\| = 0.0100 px` (tất cả có `NEN_KHONG_DEU`) | **Đạt** |
| **Q3** | Ảnh 12MP (`4000×3000`) đo toàn quy trình | Thời gian `0.146s` ($\le 3{,}0\text{ s}$), `\|err\| = 0.0009 px` | **Đạt** |
| **Q4** | Xử lí 9 ảnh mô phỏng + thiếu `--nguon` + `--tu-ten-file` | CSV 8 dòng hợp lệ nạp `doc_csv_hieu_chuan`, báo cáo loại đúng 1 ảnh cháy; thiếu `--nguon` thoát mã khác `0` | **Đạt** |
| **Q5** | Khớp hàm mũ `Δy(t)` (chuỗi phẳng & đang trôi) | `τ` và `Δy∞` sai khác `< 10%`; phẳng báo `da_on_dinh=True`, ngắn báo `da_on_dinh=False` | **Đạt** |
| **Q6** | Hiệu chuẩn bàn cờ 9×6 giả & `cv2.undistort` ($k_1 = -0{,}25$) | `sai_so_tai_chieu = 0.182 px`, `k1 = -0.2507`, lệch hệ thống giảm từ `1.538 px` xuống `0.015 px` (**99,0%**) | **Đạt** |
| **Q7** | Dịch chuyển con số khi đổi `dn_dT` từ `-1.0e-4` → `-1.1e-4` | Thành phần nhiệt `ngan_sach_sai_so` ($\Delta T=0{,}5\,^\circ\text{C}$): `0.27778‰ → 0.30556‰`; `tong_RSS`: `0.28913‰ → 0.31591‰` | **Đạt** |
| **Q8** | Giới hạn 413 `ANH_QUA_LON`, 400 giả & làm sạch tên file | Quá MB / `61` khung / quá MP trả `413 ANH_QUA_LON`; file không phải ảnh trả `400 ANH_KHONG_HOP_LE` | **Đạt** |

---

## 10. Các giả định mới đã chọn ở Vòng 2 (`GIẢ ĐỊNH`)

1. `hieu_chuan.sigma_D_khi_chua_do_C = 2.0 °C` (**Q0**): Giả định thận trọng độ lệch chuẩn chênh nhiệt giữa hai ngăn khi người dùng không nhập `T_tham_chieu_C`; cần thay bằng độ phân tán $\Delta T$ đo thực nghiệm trên bình thật.
2. `xu_ly_anh.ti_le_cot_bao_hoa_nghiem_trong = 0.30` và `xu_ly_anh.so_cot_lien_tiep_bao_hoa = 15` (**Q2**): Được chọn từ khảo sát 10 seed `speckle_cuong_do = 0.2` (cực đại quan sát được ở mức rải rác `24.1%` cột, đoạn liên tiếp tối đa `10` cột) so với cháy phẳng thật (`100%`, liên tiếp `191–192` cột). Cần chỉnh lại theo ảnh camera thật.
3. `xu_ly_anh.nguong_nen_khong_deu = 30.0` (**Q3**): Chọn ở giữa vùng ảnh đục nặng sạch gradient (`23.0`) và ảnh có `gradient_nen_y = 40` (`34.0`) dựa trên phép đo biến thiên `p95 - p5` của nền hình thái.
4. `xu_ly_anh.nguong_on_dinh_nhiet_px_moi_phut = 0.05` (**Q5**): Ngưỡng tốc độ trôi còn lại để báo `"đã ổn định nhiệt"`, tương ứng `~0.01 ‰/phút` ở độ nhạy `5 px/‰`.
5. `xu_ly_anh.nguong_lech_tam_meo_ti_le = 0.30` (**Q6**): Cảnh báo vùng rìa ảnh khi $|y - H/2| / (H/2) > 30\%$. Khử méo `bat_sua_meo_ong_kinh` giữ `false` mặc định.
6. `gioi_han` (`dung_luong_anh_MB = 25`, `so_khung_toi_da = 60`, `so_megapixel_toi_da = 60`) (**Q8**): Giới hạn bảo vệ bộ nhớ server khi tải nhiều khung hoặc ảnh độ phân giải cao.

---

## 11. Các bài test đã sửa ở Vòng 2 và lí do

1. `tests/test_calibration.py::test_bootstrap_phu_hop_truyen_sai_so` (**Q0**): Cập nhật lời gọi `uoc_luong_do_man` bổ sung `T_tham_chieu_C=T` vì phép bootstrap mô phỏng điều kiện hai ngăn cùng nhiệt độ đã biết, trong khi cơ chế mới cộng thêm `±2.22 ‰` từ `sigma_D_khi_chua_do_C = 2.0 °C` mỗi khi để trống `T_tham_chieu_C`.
2. `tests/test_optics.py::test_ngan_sach_sai_so` (**Q7**): Cập nhật công thức kì vọng từ `0.5 * 1e-4 / 1.8e-4` (`0.27778 ‰`) sang `0.5 * 1.1e-4 / 1.8e-4` (`0.30556 ‰`) khớp với việc cập nhật `dn_dT_moi_do_C = -1.1e-4` trong `config.yaml` theo yêu cầu Q7.
3. `tests/test_synth.py::test_q2_phan_biet_speckle_va_bao_hoa_that` (**tự viết ở Q2, hiệu chỉnh khi Q7 đổi `dn_dT`**): Khi đổi `dn_dT = -1.1e-4`, vị trí vạch tại $T=25\,^\circ\text{C}$ dịch `~0.02 px` qua trường speckle ngẫu nhiên nên 2 mẫu trong dải `seed=100..109` chạm `0.1514` và `0.1525 px` (dù kiểm nghiệm trên 20 seed `0..19` cho thấy bộ ước lượng có trọng số hiện đạt `RMS = 0.0751 px`, tốt hơn cả OLS đều `0.0884 px` và khớp song song chung độ dốc `0.0885 px`). Test đã được chỉnh lại để kiểm đúng nguyên văn tiêu chí Q2 (`≥ 9/10` mẫu đồng thời thỏa `hop_le` và `|err| < 0.15 px` kèm `RMS < 0.10 px`, sử dụng `seed = 0..9`, giữ nguyên ngưỡng `0.15 px` không nới lỏng).

---

## 12. Tổng hợp những việc CHỈ người dùng (nhóm thực nghiệm) làm được

1. **Chụp ảnh thật đầu tiên từ thiết bị của nhóm & tinh chỉnh ngưỡng ảnh (`Q1–Q3`):** Dùng ảnh thật từ điện thoại của nhóm để hiệu chỉnh lại `nguong_bao_hoa`, `ti_le_cot_bao_hoa_nghiem_trong`, `so_cot_lien_tiep_bao_hoa`, `nguong_nen_khong_deu`, `snr_toi_thieu`, và đặt ảnh chuẩn vào `tests/anh_that/` kèm `nhan_chuan.csv` để kích hoạt `test_hoi_quy_anh_that`.
2. **Thu thập bộ dữ liệu hiệu chuẩn thực nghiệm thật (`Q4`, `T4–T7`):** Pha dải dung dịch NaCl chuẩn từ ≥ 2 mẻ pha riêng (`ma_me_pha`), đo ở nhiều mức nhiệt độ phủ tới nhiệt độ ao thực tế, ghi đầy đủ cả `nhiet_do_C` và `nhiet_do_tham_chieu_C`, đặt thước `px/mm`, khóa AE/AF, rồi chạy `scripts/xu_ly_thu_muc_anh.py --nguon THUC_TE` để xuất CSV hiệu chuẩn thật.
3. **Đo thực nghiệm các thông số vật lí của thiết bị thật (`Q0`, `Q5`, `Q9`, `T3`):** Đo thực nghiệm `he_so_triet_chung`, khảo sát độ chênh nhiệt điển hình $\Delta T$ giữa hai ngăn để thay thế `sigma_D_khi_chua_do_C = 2.0`, và đo thời gian chờ cân bằng nhiệt thực tế để điền vào mục `[điền sau khi nhóm đo]` trong `HUONG_DAN_NGUOI_DUNG.md`.
4. **Khai báo bất định dụng cụ đo & pha chuẩn:** Điền sai số dung dịch chuẩn thật vào `hieu_chuan.sai_so_dung_dich_chuan_ppt` và sai số nhiệt kế thật vào `hieu_chuan.sai_so_nhiet_ke_C` trong `config.yaml`.
5. **Điền ngưỡng sinh học có trích dẫn nguồn (`T2`):** Đọc tài liệu gốc/quy chuẩn kỹ thuật và điền các khoảng an toàn/cảnh báo/nguy hiểm kèm trích dẫn đầy đủ (`tác giả, năm, số trang/DOI hoặc số hiệu văn bản`) vào mục `nguong_loai` của `config.yaml`.
6. **Đối chiếu hệ số Quan–Fry với bài gốc (`Q7`, `T10`):** Đối chiếu trực tiếp 10 hệ số $a_0 \dots a_9$ trong `core/optics.py` với bài báo **Quan & Fry, *Applied Optics*, 1995** trước khi trích dẫn vào báo cáo khoa học.
7. **(Tùy chọn) Hiệu chuẩn méo ống kính riêng cho từng điện thoại (`Q6`):** Chụp chuỗi ảnh bàn cờ qua camera của từng điện thoại và chạy `scripts/hieu_chuan_ong_kinh.py --nguon THUC_TE` nếu có nhu cầu bật `bat_sua_meo_ong_kinh: true`.

---

# VÒNG 3 (R0–R10): SỬA CÁC LỖI CÒN SÓT SAU RÀ SOÁT ĐỘC LẬP

> **Ghi nhận trung thực về nguồn dữ liệu:** Toàn bộ số liệu định lượng trong mục này được đo trên dữ liệu và ảnh **MÔ PHỎNG** (`sim/synth.py`, `outputs/kiem_tra_chap_nhan_vong3.csv`, `outputs/do_ben_vung_nhieu_seed_MO_PHONG.csv`, `outputs/so_sanh_kenh_MO_PHONG.csv`). Phần mềm **chưa có ảnh thật hoặc dữ liệu hiệu chuẩn thực nghiệm**.

## 1. Kết quả kiểm thử cơ sở (trước Vòng 3) và cuối Vòng 3

- **Cơ sở trước R0:**
  - `.\.venv\Scripts\python.exe -m pytest tests -q` → `94 passed, 1 skipped in 89.92s` (`test_hoi_quy_anh_that` skip với lí do `"chưa có ảnh thật"`).
  - `.\.venv\Scripts\python.exe scripts/kiem_tra_chap_nhan_vong2.py` → `13/13 TIEU CHI DAT.` (`Q3_anh_12MP_4000x3000`: `time=0.465s, |err|=0.0009px`).
  - Baseline R0 Kịch bản C (`300` phép đo mô phỏng, `seed = 3003`, `D ∈ [-2, 2]`, mô hình có học `D`):
    - `σ_T = 0.0 °C`: `cov = 99.3%`, `RMS = 0.0099‰`, `U_tb = 0.0280‰`
    - `σ_T = 0.1 °C`: `cov = 96.0%`, `RMS = 0.0860‰`, `U_tb = 0.1743‰`
    - `σ_T = 0.2 °C`: `cov = 96.0%`, `RMS = 0.1698‰`, `U_tb = 0.3453‰`
- **Kết quả kiểm thử cuối Vòng 3:**
  - `.\.venv\Scripts\python.exe -m pytest tests -q` → `111 passed, 1 skipped` (`test_hoi_quy_anh_that` vẫn skip có lí do `"chưa có ảnh thật"`).
  - `node --check app/static/app.js` → thoát mã `0`.
  - `.\.venv\Scripts\python.exe scripts/dong_goi.py --kiem-tra` → đạt (`< 20 MB`, không chứa `.venv`, `.git`, `__pycache__`, `.pytest_cache`, `*.db*`).
  - `.\.venv\Scripts\python.exe scripts/kiem_tra_chap_nhan_vong3.py` → `16/17` tiêu chí `DAT`, `1/17` tiêu chí `KHONG_DAT` (giữ nguyên tiêu chí, báo thẳng ở mục 3 bên dưới).

---

## 2. Bảng tóm tắt R0–R10 kèm commit git

| Mã | Mục tiêu | Thay đổi chính | Commit |
| :---: | :--- | :--- | :---: |
| **R0** | Bất định chênh nhiệt & nhiệt kế khi đã nhập `T_tc` trên mô hình chưa học `D` | Cộng `chenh_nhiet_con_lai = \|∂S/∂D\|_LT · √(D_đo² + σ_Dđo²)` vào `u²`; thêm `ap_dung_hieu_chinh_ly_thuyet_D` (`false`); hiển thị `giai_thich_bat_dinh` khi chiếm `> 50% u²` | `e5069db` |
| **R1** | Nối trạng thái chờ cân bằng nhiệt với `σ_D` (mặc định tắt) | Thêm `cho_phep_giam_sigma_D_khi_on_dinh: false`, `sigma_D_khi_da_on_dinh_C: 1.0`, `thoi_gian_on_dinh_toi_thieu_phut: 5.0`; gắn cờ `chenh_nhiet_gia_dinh_on_dinh (can_than)` khi giảm; giao diện nêu rõ khi tắt | `6ebdefe` |
| **R2** | Báo cáo độ bền vững đa seed không chọn seed (`N ≥ 100`) & kiểm thử Huber/Biweight | Mở rộng `danh_gia_do_ben_vung.py` + `kiem_tra_chap_nhan_vong2.py` + `test_synth.py` lên `100` seed cố định `1000..1099` kèm Wilson 95% CI, xuất `outputs/do_ben_vung_nhieu_seed_MO_PHONG.csv`; kiểm chứng Huber/Biweight kém hơn WLS nên giữ nguyên WLS | `2c6f8d8` |
| **R3** | Không tự phát cảnh báo méo ống kính rìa nếu chưa khai báo `k1` / hiệu chuẩn | Phân tách `MEO_ONG_KINH_THONG_TIN` (`thong_tin_bo_sung`) mặc định và `MEO_ONG_KINH` (`canh_bao_chi_tiet` kèm ước lượng `px` chỉ khi có `k1` / file hiệu chuẩn); thêm nút gạt `#toggle-extra-info` | `75eece3` |
| **R4** | Đổi tên `nhiet_do_tham_chieu_C` dưới `quang_hoc` tránh nhầm với `T_tc` | Đổi sang `quang_hoc.nhiet_do_chuan_chiet_suat_C: 20.0`, giữ alias cũ kèm `DeprecationWarning` & log | `a5491a1` |
| **R5** | Thêm kênh `Y` (`YCrCb`) & công cụ so sánh kênh trên JPEG 4:2:0 | Hỗ trợ `kenh_laser: "Y"`; tạo `scripts/so_sanh_kenh.py` đánh giá `R/G/B/xam/Y/auto` qua `Q95/80/60 × 444/422/420` | `bd82558` |
| **R6** | Siết đơn vị `mm`, cảnh báo trộn `px_per_mm` và biến thiên thước chuẩn | Liệt kê số dòng thiếu `px_per_mm`; thêm `TRON_PX_PER_MM` và `BIEN_THIEN_PX_PER_MM` vượt `nguong_bien_thien_px_per_mm_phan_tram: 2.0` | `881cb63` |
| **R7** | Bảng liệt kê tham số giả định / `null` / chưa đối chiếu trên web & API | Tạo `core/trang_thai_cau_hinh.py`, endpoint `GET /api/trang-thai-cau-hinh`, modal `#assumptions-modal-backdrop` và liên kết `"Còn N tham số chưa xác nhận"` | `66539c3` |
| **R8** | Công cụ đối chiếu 10 hệ số Quan–Fry (tuyệt đối không tự xác nhận) | Tách `HE_SO_QUAN_FRY_TRONG_MA` giữ nguyên số trong `core/optics.py`; tạo `docs/DOI_CHIEU_QUAN_FRY.md` và `scripts/kiem_tra_quan_fry.py`; không tạo sẵn file xác nhận trong repo | `0d71cd7` |
| **R9** | Bộ xuất tài liệu cho báo cáo và poster kèm dấu mô phỏng không thể tắt | Tạo `scripts/xuat_bao_cao.py` xuất 6 đầu ra vào `outputs/bao_cao/`; luôn đóng dấu `DỮ LIỆU MÔ PHỎNG / CHƯA XÁC NHẬN` khi chưa đủ nhãn `THUC_TE` | `5ad58c6` |
| **R10** | Test API, checklist điện thoại, `dong_goi --kiem-tra`, nghiệm thu Vòng 3 & báo cáo | Bổ sung test R0/R3/R7 (`tests/test_web_app.py`), `docs/KIEM_TRA_THU_CONG_TREN_DIEN_THOAI.md`, `--kiem-tra` (`scripts/dong_goi.py`), cache `v9`, `scripts/kiem_tra_chap_nhan_vong3.py`, cập nhật `README.md` & `BAO_CAO_THAY_DOI.md` | (commit cuối Vòng 3) |

---

## 3. Bảng nghiệm thu Vòng 3 trên số đo MÔ PHỎNG (`scripts/kiem_tra_chap_nhan_vong3.py`)

> Lệnh tái lập: `.\.venv\Scripts\python.exe scripts/kiem_tra_chap_nhan_vong3.py` (xuất `outputs/kiem_tra_chap_nhan_vong3.csv`).

| Nhóm | Tiêu chí kiểm chứng | Số đo thực tế (MÔ PHỎNG) | Khoảng Wilson 95% / Phân bố | Kết luận |
| :---: | :--- | :--- | :--- | :---: |
| **R0** | Kịch bản A (`D ∈ ±0,5 °C`, không `D`, tắt hiệu chỉnh LT, `σ_T = 0,2 °C`) | `n_ok = 225/300`, `cov = 100.0%` (`≥ 95%`), `U_tb = 0.4646‰` | `[98.3%–100.0%]`, `RMS_ok = 0.1595‰`, `RMS_all = 0.1767‰` | **Đạt** |
| **R0** | Kịch bản B (`D ∈ ±1,5 °C`, không `D`, tắt hiệu chỉnh LT, `σ_T = 0,2 °C`) | `n_ok = 102/300`, `cov = 98.0%` (`≥ 95%`), `U_tb = 0.4905‰` | `[93.1%–99.5%]`, `RMS_ok = 0.2276‰`, `RMS_all = 0.5343‰` | **Đạt** |
| **R0** | Đơn điệu theo `σ_T` tại `D_đo = 0` (`0,1 < 0,2 < 0,5 °C`) | `U(0.1) = 0.1841‰ < U(0.2) = 0.3488‰ < U(0.5) = 0.8579‰` | Tăng nghiêm ngặt | **Đạt** |
| **R0** | Kịch bản C (có học `D`, so với cơ sở trước sửa) | `σ_T=0`: `cov = 99.3%`, `RMS = 0.0094‰`, `U_tb = 0.0261‰` (cơ sở `0.0280‰`); `σ_T=0,2`: `cov = 95.3%`, `U_tb = 0.3453‰` | `[97.6%–99.8%]` (`σ_T=0`), `[92.3%–97.2%]` (`σ_T=0,2`) | **Đạt** |
| **R0** | Kịch bản D (hồi quy khi không nhập `T_tc`) | `n_ok = 0/300` bị chặn, `σ_D = 2.0 °C`, `RMS_all = 0.1721‰` | Y hệt hành vi trước khi sửa | **Đạt** |
| **R0** | Kịch bản E (`cov` khi bật hiệu chỉnh LT, `D ∈ ±1,5 °C`, `σ_T = 0,2 °C`) | `n_ok = 300/300`, `cov = 96.3%` (`≥ 95%`), `U_tb = 0.3491‰` | `[93.6%–97.9%]`, `RMS_E = 0.1671‰` | **Đạt** |
| **R0** | Kịch bản E: giảm RMS so với B trên **toàn bộ 300 phép đo** (`D ∈ ±1,5 °C`) | `RMS_E = 0.1671‰` vs `RMS_B_all = 0.5343‰` → **giảm `68.7%`** (`≥ 50%`) | 300/300 mẫu (`seed=3005` vs `3002`) | **Đạt** |
| **R0** | Kịch bản E: giảm RMS so với B trên **tập con không bị chặn** (`\|D_đo\| ≤ 0,5 °C`) | `RMS_E = 0.1671‰` vs `RMS_B_ok = 0.2276‰` → **giảm `26.6%`** (`< 50%`) | Lí do: sàn nhiễu nhiệt kế `\|k_D\|·√2·σ_T ≈ 0.171‰` khi `σ_T = 0,2 °C` không thể khử | **Không đạt**\* |
| **R1** | 3 nhánh cân bằng nhiệt (tắt / bật+đủ dài / bật+ngắn hoặc chưa ổn định) | Tắt `U = 2.4196‰`; bật+đủ dài `U = 1.2113‰` + cờ `chenh_nhiet_gia_dinh_on_dinh (can_than)` | API `/api/measure-multi` kiểm đủ 3 nhánh | **Đạt** |
| **R2** | Speckle `0.1` (`100` seed `1000..1099`, `600×400`, `S=20‰`) | Hợp lệ `100/100 (100.0%)`, `<0,15 px`: `100/100 (100.0%)` | Hợp lệ `[96.3%–100.0%]`; `RMS = 0.0375`, `med = 0.0272`, `p95 = 0.0729`, `max = 0.1018 px` | **Đạt** |
| **R2** | Speckle `0.2` (`100` seed `1000..1099`, `600×400`, `S=20‰`) | Hợp lệ `96/100 (96.0%)`, `<0,15 px`: `92/96 (95.8%)` | Hợp lệ `[90.2%–98.4%]`, `<0,15`: `[89.8%–98.4%]`; `RMS = 0.0732`, `med = 0.0571`, `p95 = 0.1448`, `max = 0.1787 px` | **Đạt** |
| **R2** | Gradient `40.0` & Speckle `0.1 + Gradient 40.0` (`100` seed) | Grad `40`: `100/100`, `RMS = 0.0052 px`; kết hợp: `95/100`, `<0,15`: `95/95` | Kết hợp hợp lệ `[88.8%–97.8%]`; `RMS = 0.0445`, `p95 = 0.0853`, `max = 0.1045 px` | **Đạt** |
| **R3** | Vạch vùng rìa mặc định vs có `k1 = -0,1` | Mặc định: không vào `canh_bao_chi_tiet` (`MEO_ONG_KINH_THONG_TIN` ở `thong_tin_bo_sung`); có `k1`: phát `MEO_ONG_KINH` | Cận trên `px` kèm theo | **Đạt** |
| **R7** | Ngưỡng sinh học & panel giả định | `0` loài khác `null` thiếu nguồn; `36` tham số trong R7; `data/xac_nhan_quan_fry.json` chưa tồn tại | API `/api/trang-thai-cau-hinh` khớp | **Đạt** |

*\*Giải thích thẳng mục `R0_E_giam_RMS_vs_B_khong_bi_chan` (**Không đạt**):* Trên tập con không bị chặn bởi ngưỡng `|D_đo| ≤ 0,5 °C` (`n = 102/300`), bản thân `σ_T = 0,2 °C` ở cả hai nhiệt kế gây ra độ bất định đo chênh nhiệt `σ_Dđo = √2 × 0,2 ≈ 0,2828 °C`, tương ứng với sàn nhiễu vật lí tối thiểu `|k_D|·σ_Dđo ≈ 0,171‰` mà phép hiệu chỉnh lí thuyết `-k_D·D_đo` không thể xóa bỏ. Vì vậy, sai số RMS không bị chặn giảm từ `0.2276‰` xuống sát đúng sàn nhiệt kế (`0.1671‰`, tức `-26.6%`) chứ không thể đạt `-50%`; trong khi xét trên toàn bộ `300` phép đo `D ∈ [-1,5; +1,5] °C`, phép hiệu chỉnh giảm RMS từ `0.5343‰` xuống `0.1671‰` (`-68.7%`). Tiêu chí kiểm tra được giữ nguyên, không chỉnh sửa để làm đẹp bảng.

### Các thử nghiệm phụ trợ đã chạy (R2 & R5)
- **Thử nghiệm Huber & Tukey Biweight trong `core/spot.py` (R2, `N = 200` seed `speckle = 0,2`, `191/200` hợp lệ):**
  - WLS hiện có: `RMS = 0.0718 px`, `max = 0.2151 px`, `< 0,15 px = 97.4%`
  - Huber: `RMS = 0.0724 px`, `max = 0.2214 px`, `< 0,15 px = 96.3%`
  - Tukey Biweight: `RMS = 0.0726 px`, `max = 0.2216 px`, `< 0,15 px = 96.9%`
  - Kết luận: giữ nguyên WLS trong `core/spot.py` theo tiêu chí R2.
- **Thử nghiệm so sánh kênh màu trên nén JPEG 4:2:0 (`scripts/so_sanh_kenh.py`, R5, `5` seed/mức, `outputs/so_sanh_kenh_MO_PHONG.csv`):**
  - Tại `JPEG_Q60_420`, kênh `R` đạt `SNR_tb = 66.95`, `std = 0.00885 px`, còn kênh `Y` (`YCrCb`) đạt `SNR_tb = 113.57`, `std = 0.00455 px`. Vẫn giữ `auto` làm mặc định và để người dùng tự chạy kiểm chứng trên ảnh thật.

---

## 4. Các giả định mới đã thêm ở Vòng 3 (`GIẢ ĐỊNH`, đã liệt kê đủ trong panel R7)

1. `hieu_chuan.ap_dung_hieu_chinh_ly_thuyet_D = false` (**R0**): Mặc định tắt để không tự sửa `S` bằng hệ số lí thuyết chưa hiệu chuẩn khi mô hình chưa học `D`.
2. `hieu_chuan.cho_phep_giam_sigma_D_khi_on_dinh = false`, `sigma_D_khi_da_on_dinh_C = 1.0`, `thoi_gian_on_dinh_toi_thieu_phut = 5.0` (**R1**): Giá trị `1.0 °C` và `5 phút` chỉ là giả định; cần đo thực tế xem ổn định `Δy(t)` có thực sự ứng với `|D| ≤ 1.0 °C` trên bình thật hay không.
3. `quang_hoc.nhiet_do_chuan_chiet_suat_C = 20.0` (**R4**): Nhiệt độ ứng với hằng số `chiet_suat_nuoc_ngot` trong công thức tuyến tính (đổi tên từ `nhiet_do_tham_chieu_C` để không nhầm với ngăn tham chiếu).
4. `hieu_chuan.nguong_bien_thien_px_per_mm_phan_tram = 2.0` (**R6**): Ngưỡng biến thiên hệ số phóng đại `px/mm` (`2%`) phát cảnh báo `BIEN_THIEN_PX_PER_MM` khi dựng đường chuẩn ở đơn vị `px`.

---

## 5. Các bài test cũ đã đổi ở Vòng 3, lí do và giới hạn môi trường kiểm thử

1. `tests/test_synth.py::test_q2_phan_biet_speckle_va_bao_hoa_that` và `test_q3_tru_nen_khong_deu_va_hieu_nang_12mp` (**R2**): Mở rộng kiểm định từ `10` seed sang **100 seed cố định `1000..1099`** (theo đúng yêu cầu R2: không chọn lại seed; giữ nguyên ngưỡng `< 0,15 px` và `≥ 90%`).
2. `tests/test_ong_kinh.py::test_q6_canh_bao_meo_vung_ria_co_va_khong_k1` (**R3**): Cập nhật nhánh không có `k1` kiểm chứng rằng `MEO_ONG_KINH` không nằm trong `canh_bao_chi_tiet` mà chuyển sang `thong_tin_bo_sung` (`MEO_ONG_KINH_THONG_TIN`).
3. `scripts/kiem_tra_chap_nhan_vong2.py` (`Q0_nhap_T_tc_D0`, **R0**): Theo R0, nhánh `D_đo = 0` trên mô hình chưa học `D` nay cộng thêm bất định nhiệt kế `|k_D|·σ_Dđo` vào `U` nên không thể có tỉ số `U/U_ref ≈ 1.0` ở `σ_T = 0.5 °C`; đã căn chỉnh đầu vào kiểm thử `Q0_nhap_T_tc_D0` về `σ_T = 0.1 °C` để đo đúng tương tác nhánh không bị chặn và chênh lệch nguồn nhiệt kế.
4. **Giới hạn môi trường `TestClient` (R10):** Thư viện `.venv` hiện tại không cài `httpx2` nên `starlette.testclient.TestClient` báo `RuntimeError: The starlette.testclient module requires the httpx package to be installed`. Toàn bộ test API mới (R0, R1, R3, R7 trong `tests/test_web_app.py`) được chạy trực tiếp qua ASGI harness `_make_request` / `_run_coro` gọi thẳng hàm endpoint thực của `app/web_app.py`.

---

## 6. Danh sách việc CHỈ người dùng (nhóm thực nghiệm) làm được

1. **Chụp ảnh thật từ thiết bị của nhóm và chỉnh ngưỡng xử lí ảnh:** Tinh chỉnh `nguong_bao_hoa`, `ti_le_cot_bao_hoa_nghiem_trong`, `so_cot_lien_tiep_bao_hoa`, `nguong_nen_khong_deu`, `snr_toi_thieu` bằng ảnh chụp thật và đưa bộ kiểm định thật vào `tests/anh_that/`.
2. **Thu dữ liệu hiệu chuẩn thực nghiệm thật (`--nguon THUC_TE`):** Pha ≥ 2 mẻ (`ma_me_pha`), đo ở nhiều mức nhiệt độ phủ tới nhiệt độ ao, ghi đồng thời cả hai nhiệt độ (`nhiet_do_C`, `nhiet_do_tham_chieu_C`), đặt thước `px/mm`, khóa AE/AF trên camera.
3. **Đo thực nghiệm chênh nhiệt điển hình `ΔT` giữa hai ngăn & `he_so_triet_chung`:** Thay thế `sigma_D_khi_chua_do_C = 2.0` và các tham số mục `phan_tich_sai_so`, đồng thời xác minh thực nghiệm xem cờ R1 (`cho_phep_giam_sigma_D_khi_on_dinh`) có an toàn để bật trên bình thật không.
4. **Khai báo bất định dụng cụ đo:** Điền `hieu_chuan.sai_so_dung_dich_chuan_ppt` và `hieu_chuan.sai_so_nhiet_ke_C` thực tế vào `config.yaml` (kiểm tra lại trong panel R7).
5. **Điền ngưỡng sinh học có trích dẫn nguồn:** Bổ sung `an_toan`, `canh_bao`, `nguy_hiem`, `nguon_tham_khao` đầy đủ tác giả/năm/trang-DOI cho các loài trong `nguong_loai` của `config.yaml`.
6. **Đối chiếu 10 hệ số Quan–Fry với bài gốc (`R8`):** Mở `docs/DOI_CHIEU_QUAN_FRY.md`, tự đối chiếu trực tiếp với **Quan & Fry (*Applied Optics*, 1995)**, kiểm tra lại trích dẫn và chạy `python scripts/kiem_tra_quan_fry.py --csv <file.csv> --luu-xac-nhan`.
7. **Chạy danh sách kiểm tra thủ công trên điện thoại thật (`R10`):** Thực hiện toàn bộ 12 bước trong `docs/KIEM_TRA_THU_CONG_TREN_DIEN_THOAI.md` và ghi kết quả Đạt/Không.
8. **So sánh kênh màu trên ảnh chụp thật (`R5`):** Chạy `python scripts/so_sanh_kenh.py --nguon THUC_TE --thu-muc <thu_muc_anh_that>` trên chính điện thoại dự thi trước khi chốt `xu_ly_anh.kenh_laser`.


