# QUY TRÌNH THU DỮ LIỆU THỰC NGHIỆM & HIỆU CHUẨN HỆ THỐNG

> **Lưu ý chung về mọi con số trong tài liệu này:**  
> Các mốc số lượng mức mặn, số lần lặp, dải nhiệt độ hay số cặp nhiệt kế dưới đây là **gợi ý khởi điểm, nhóm điều chỉnh cùng giáo viên hướng dẫn** cho phù hợp điều kiện phòng thí nghiệm và đối tượng nuôi thực tế, đồng thời đồng bộ trực tiếp với các khóa trong [`config.yaml`](../config.yaml).

---

## 1. Chuẩn bị dụng cụ & an toàn laser

- **Hệ quang học hai ngăn:** Lăng kính rỗng hai ngăn (mặc định góc đỉnh `A = 40°` trong `quang_hoc.goc_dinh_do` của `config.yaml`), một ngăn chứa **nước cất đóng kín** làm ngăn tham chiếu (`0‰`) và một ngăn chứa **nước mẫu**.
- **An toàn nguồn sáng:** Dùng module laser vạch `650 nm`, công suất `≤ 1 mW`. Tuyệt đối không chiếu trực tiếp hoặc phản xạ gương vào mắt; cố định chắc khung lăng kính, tia laser vuông góc mặt vào và màn hứng trắng mờ trước khi bật nguồn.
- **Định cỡ thước ảnh:** Đặt thước chia vạch mm ngay cạnh màn hứng tại mặt phẳng chiếu vạch để đọc được tỉ lệ `px_per_mm` cho từng phiên chụp.
- **Nhiệt kế & dụng cụ pha chuẩn:** Hai nhiệt kế (ngăn mẫu và ngăn tham chiếu), nhiệt kế chuẩn (nếu có) hoặc cùng một cốc nước khuấy đều để hiệu chuẩn chéo, cân điện tử, bình định mức/cốc cân, muối NaCl tinh khiết và nước cất.

---

## 2. Hiệu chuẩn chéo hai nhiệt kế (`V1`) trước khi đo độ mặn

Hai nhiệt kế phổ thông có thể lệch hệ thống với nhau ±0,3 đến ±1,0 °C. Nếu không đo và trừ độ lệch hệ thống này (`offset`), phần mềm sẽ tính nhầm độ chênh nhiệt $D = T_{\text{mẫu}} - T_{\text{tc}}$ và có thể chặn nhầm kết luận đo mặn.

1. Đặt cả hai đầu đo nhiệt kế (nhiệt kế ngăn mẫu và nhiệt kế ngăn tham chiếu; thêm nhiệt kế chuẩn nếu có) **vào cùng một cốc nước khuấy đều liên tục** để nhiệt độ cả hai đầu đo bằng nhau thật sự.
2. Ghi kết quả ở nhiều mức nhiệt khác nhau (ví dụ `15 °C`, `25 °C`, `35 °C`; mốc `hieu_chuan.nhiet_ke_cheo.so_muc_nhiet_toi_thieu = 2` và `hieu_chuan.nhiet_ke_cheo.so_cap_toi_thieu = 6` trong `config.yaml` là *gợi ý khởi điểm, nhóm điều chỉnh cùng giáo viên hướng dẫn*).
3. **Độ phân giải nhiệt kế & ghi đủ chữ số (`W3`):** Khuyến nghị dùng nhiệt kế có độ phân giải hiển thị `≤ 0,1 °C` (`hieu_chuan.nhiet_ke_cheo.do_phan_giai_toi_da_C = 0.1` — *gợi ý khởi điểm, nhóm điều chỉnh cùng giáo viên hướng dẫn*). **Phải ghi đầy đủ tất cả các chữ số sau dấu phẩy trên màn hình** (không tự làm tròn bớt phần thập phân); nếu nhiệt kế chỉ chia `0,5 °C` hoặc `1 °C`, phần mềm tự cộng thêm sàn sai số lượng tử hóa `σ_pg = √(r_mẫu² + r_tc²)/√(12·số_mức)` và bật cảnh báo `DO_PHAN_GIAI_NHIET_KE_THO`. Nếu biết chính xác độ chia nhỏ nhất từ thông số nhà sản xuất, truyền thêm `--do-phan-giai-mau` và `--do-phan-giai-tc`.
4. **Lưu ý khi kiểm điểm 0 °C:** Nếu muốn kiểm điểm `0 °C`, phải dùng **nước đá xay + nước cất (hỗn hợp cân bằng băng–nước khuấy đều)** có nước bọc quanh đầu đo để nhiệt độ ổn định ở `0,0 °C`. **Không** áp đầu đo trực tiếp lên viên đá cục khô trong ngăn đông hay đá khô CO₂ vì nhiệt độ bề mặt đá không phải `0 °C` và tiếp xúc nhiệt không đều.
5. Điền các cặp đọc đồng thời vào file mẫu [`data/mau_cap_nhiet_ke.csv`](../data/mau_cap_nhiet_ke.csv) (`nhiet_do_mau_doc_C`, `nhiet_do_tc_doc_C`, `nhiet_do_chuan_C`, `nguon_du_lieu=THUC_TE`, `ghi_chu`), rồi chạy lệnh:
   ```bash
   python scripts/hieu_chuan_cheo_nhiet_ke.py --csv data/cap_nhiet_ke_cua_nhom.csv --nguoi-thuc-hien "<Ten_HS>" --nguon THUC_TE
   ```
   Lệnh này tạo `data/hieu_chuan_nhiet_ke.json` (hiện chưa có sẵn trong mã nguồn) và tự kiểm xem độ lệch hai nhiệt kế có phụ thuộc tuyến tính theo nhiệt độ hay không.

---

## 3. Pha tối thiểu 2 mẻ dung dịch NaCl độc lập & ghi bất định dụng cụ

1. Pha các mức nồng độ NaCl theo dải mục tiêu `hieu_chuan.dai_man_muc_tieu_ppt` trong `config.yaml` (mặc định `[0.0, 35.0] ‰`, `thiet_ke_thi_nghiem.so_muc_man_toi_thieu = 6`, `thiet_ke_thi_nghiem.phai_co_muc_0 = true`, `thiet_ke_thi_nghiem.ti_le_phu_dai_man_toi_thieu = 0.8` — các ngưỡng này là *gợi ý khởi điểm, nhóm điều chỉnh cùng giáo viên hướng dẫn*).
2. Pha thành **ít nhất 2 mẻ độc lập** (`thiet_ke_thi_nghiem.so_me_pha_toi_thieu = 2`, *gợi ý khởi điểm, nhóm điều chỉnh cùng giáo viên hướng dẫn*), cân muối và nước riêng cho từng mẻ và đặt mã phân biệt ở cột `ma_me_pha` (ví dụ `ME_01`, `ME_02`) để `GroupKFold` tách kiểm định đúng theo mẻ, không bị rò rỉ dữ liệu lặp.
3. Ghi lại đầy đủ khối lượng muối, khối lượng nước, ngày đo và tên người đo vào biểu mẫu [`data/mau_ghi_chep_thi_nghiem.csv`](../data/mau_ghi_chep_thi_nghiem.csv).
4. Từ độ chia nhỏ nhất của cân/bình định mức và sai số cho phép trên nhãn nhiệt kế, điền hai giá trị thực vào `config.yaml`:
   - `hieu_chuan.sai_so_dung_dich_chuan_ppt`
   - `hieu_chuan.sai_so_nhiet_ke_C`
   - `hieu_chuan.nhiet_do_toi_thieu_phu_C`

---

## 4. Quy trình chụp ảnh hiệu chuẩn & đo thực tế

1. **Tráng cuvet & nạp mẫu:** Tráng ngăn mẫu **2 lần** bằng chính dung dịch sắp đo để tránh pha loãng từ giọt nước mẫu cũ còn đọng thành ngăn; giữ nguyên ngăn tham chiếu nước cất `0‰` đóng kín.
2. **Kiểm soát nhiệt độ hai ngăn:**
   - Đo và ghi **cả hai cột** `nhiet_do_C` (ngăn mẫu) và `nhiet_do_tham_chieu_C` (ngăn tham chiếu) nếu có nhiệt kế nhúng hai ngăn.
   - Khi muốn dùng đường chuẩn có học hệ số chênh nhiệt `D = T_mẫu − T_tc`, phải chủ động thu dữ liệu ở nhiều mức `D` khác nhau (`thiet_ke_thi_nghiem.so_muc_D_toi_thieu_neu_hoc_D = 2`, `thiet_ke_thi_nghiem.chenh_D_toi_thieu_C = 1.0` °C — *gợi ý khởi điểm, nhóm điều chỉnh cùng giáo viên hướng dẫn*).
   - Khi thu ở trạng thái cân bằng nhiệt, nên dùng chức năng đo đa khung để theo dõi tốc độ trôi `Δy(t)` và chờ ổn định (các ngưỡng `xu_ly_anh.*` và `hieu_chuan.thoi_gian_on_dinh_toi_thieu_phut` trong `config.yaml` cũng là *gợi ý khởi điểm* cần đối chứng trên bình thật).
   - Khảo sát nhiều mức nhiệt mẫu phủ dải thực tế ao/phòng (`thiet_ke_thi_nghiem.so_muc_nhiet_toi_thieu = 3`, `thiet_ke_thi_nghiem.bien_do_nhiet_toi_thieu_C = 6.0` °C — *gợi ý khởi điểm, nhóm điều chỉnh cùng giáo viên hướng dẫn*).
3. **Thiết lập camera điện thoại:**
   - **Định dạng ảnh (iPhone/Android):** Chụp ở định dạng **JPEG** hoặc **PNG**. Không tải trực tiếp ảnh **HEIC/HEIF** hay **WebP** (phần mềm sẽ nhận diện chữ kí byte và từ chối với mã `ANH_KHONG_HO_TRO_DINH_DANG`). Trên iPhone: vào **Cài đặt > Camera > Định dạng > Tương thích nhất (JPEG)**, hoặc xuất ảnh sang JPEG/PNG trước khi đưa vào xử lí.
   - Gắn điện thoại lên giá đỡ cố định, căn tâm vạch gần vùng giữa khung hình (`xu_ly_anh.nguong_lech_tam_meo_ti_le`).
   - **Bắt buộc khóa phơi sáng (AE) và khóa lấy nét (AF)** ở ứng dụng camera thủ công, ghi nhận `khoa_ae_af = 1` và kiểm không cho vạch bị chói trắng bẹt đỉnh.
   - Chụp lặp tại mỗi ô `(S × mức T)` tối thiểu `thiet_ke_thi_nghiem.so_lan_lap_toi_thieu_moi_o = 3` ảnh và phân bố đều giữa các mức độ mặn (`thiet_ke_thi_nghiem.ti_le_toi_da_moi_muc = 0.4` — *gợi ý khởi điểm, nhóm điều chỉnh cùng giáo viên hướng dẫn*).
4. **Đánh giá kênh màu trên chính điện thoại dự thi:** Trước khi chốt `xu_ly_anh.kenh_laser` trong `config.yaml`, tự chạy công cụ so sánh kênh trên ảnh chụp thật của nhóm:
   ```bash
   python scripts/so_sanh_kenh.py --nguon THUC_TE --thu-muc data/anh_that
   ```

---

## 5. Xử lí thư mục ảnh, kiểm tra thiết kế, dựng đường chuẩn & đối chiếu Quan–Fry

1. **Xử lí hàng loạt thư mục ảnh thật (`--nguon THUC_TE`):**
   ```bash
   python scripts/xu_ly_thu_muc_anh.py --thu-muc data/anh_that --nguon THUC_TE --metadata data/anh_that/metadata.csv
   ```
   Kiểm lại file `*_bao_cao_chat_luong.csv` xem có ảnh nào bị loại do bão hòa, nền chói, SNR thấp (`xu_ly_anh.snr_toi_thieu`) hay thiếu khóa AE/AF không.
2. **Kiểm tra thiết kế thí nghiệm (`V4` & `W1`, không chặn dựng đường chuẩn):**
   ```bash
   python scripts/kiem_tra_thiet_ke_thi_nghiem.py --csv <csv_hieu_chuan.csv>
   ```
   (Hoặc kiểm trực tiếp trên Tab 4 của Web App, tích chọn *"Yêu cầu đủ biến thiên chênh nhiệt D"* nếu định học mô hình có số hạng `D`).  
   - **Giới hạn phát hiện bản sao (`W1`):** Công cụ chỉ bắt các dấu hiệu định danh rõ ràng gồm dòng trùng hệt toàn bộ cột, trùng `sha256_anh`, hoặc trùng `ten_file` nhưng khác `delta_y_px` (*nghi ngờ gán nhãn lại*). Hệ thống chủ động **không** dùng heuristic đánh dấu "độ tản mát quá nhỏ bất thường" để tránh báo nhầm dương tính giả khi phép đo lặp thực sự rất ổn định.
3. **Dựng đường chuẩn & xuất bộ tài liệu báo cáo KHKT:**
   ```bash
   python scripts/dung_duong_chuan.py --csv <csv_hieu_chuan.csv>
   python scripts/xuat_bao_cao.py --csv <csv_hieu_chuan.csv> --so-sanh <csv_khuc_xa_ke.csv>
   ```
4. **Đối chiếu 10 hệ số Quan–Fry (`V2`, 2 người độc lập):**
   Mở [`docs/DOI_CHIEU_QUAN_FRY.md`](DOI_CHIEU_QUAN_FRY.md), đọc trực tiếp bài báo gốc Quan & Fry (*Applied Optics*, 1995), điền đủ số trang/bảng cho từng hệ số `a0..a9` rồi xác nhận bằng 2 người độc lập qua `scripts/kiem_tra_quan_fry.py`.

---

## 6. Những việc TUYỆT ĐỐI KHÔNG LÀM

1. **TUYỆT ĐỐI KHÔNG** gắn nhãn `--nguon THUC_TE` (CLI, CSV hay Nhật kí web) cho ảnh mô phỏng sinh từ `sim/synth.py` hay ảnh còn mang dấu `SIMULATED`/`MO_PHONG`.
2. **TUYỆT ĐỐI KHÔNG** trộn chung dữ liệu `MO_PHONG` và `THUC_TE` trong cùng một tập CSV hiệu chuẩn hoặc so sánh Bland–Altman.
3. **TUYỆT ĐỐI KHÔNG** sao chép lại 10 hệ số `a0..a9` từ mã nguồn để tự ký `xac_nhan_quan_fry.json`; bắt buộc phải đối chiếu trực tiếp từ bài báo gốc Quan & Fry (1995) có đủ tên 2 người xác nhận độc lập khác nhau và số trang/bảng.
4. **TUYỆT ĐỐI KHÔNG** lấy các chỉ số từ bộ ảnh/dữ liệu **MÔ PHỎNG** (ví dụ sai số sub-pixel trên ảnh giả lập hay độ phủ mô phỏng) để ghi trong báo cáo hoặc thuyết trình thành *"độ chính xác đo thực tế của thiết bị"*.
5. **TUYỆT ĐỐI KHÔNG** chọn lọc seed riêng cho ra số đẹp, không xóa bớt điểm ngoại lai thật mà không có bằng chứng chất lượng ảnh, và không nới lỏng các tiêu chí kiểm thử để làm cho bảng nghiệm thu chuyển sang ĐẠT giả tạo.
6. **TUYỆT ĐỐI KHÔNG** dùng tay không hiệu chuẩn chéo hai nhiệt kế rồi giả định `T_mẫu = T_tc`, và **không** đo điểm `0 °C` bằng cách kẹp đầu đo trực tiếp lên đá cục/đá khô.
