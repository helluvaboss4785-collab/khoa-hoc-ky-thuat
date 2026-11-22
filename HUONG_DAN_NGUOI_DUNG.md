# HƯỚNG DẪN SỬ DỤNG MÁY ĐO ĐỘ MẶN BẰNG KHÚC XẠ LASER (DÀNH CHO NGƯỜI NUÔI)

> Tài liệu này hướng dẫn thao tác đo đúng cách và đọc hiểu kết quả an toàn. Thiết bị đo ở đây hỗ trợ theo dõi nhanh tại ao nuôi; **kết quả chỉ là độ mặn tương đương NaCl** và **không thay thế xét nghiệm phòng thí nghiệm chính thức**.

---

## 1. Chuẩn bị trước khi đo

1. **Kiểm tra ngăn tham chiếu (nước cất 0 ‰):** Đảm bảo ngăn nước cất đóng kín, trong suốt, không có bọt khí bám vào mặt kính.
2. **Tráng và rót nước mẫu:**
   - Tráng ngăn mẫu 2 lần bằng chính nước ao cần đo để tránh lẫn nước cũ.
   - Đổ đầy ngăn mẫu, lau khô mặt kính bên ngoài bằng khăn giấy mềm sạch.
3. **Chờ cân bằng nhiệt độ hai ngăn:**
   - Nếu nước mẫu lấy từ ao nắng nóng hoặc mát hơn nước cất trong ngăn chuẩn, chênh lệch nhiệt độ $D = T_{\text{mẫu}} - T_{\text{tham chiếu}}$ sẽ làm tia laser bị lệch giả tạo (khúc xạ thay đổi theo nhiệt độ).
   - Đặt máy yên ở nơi râm mát trong thời gian chờ cân bằng nhiệt là **`[điền sau khi nhóm đo]`**, hoặc dùng nút **⏱️ Chờ cân bằng nhiệt** trên ứng dụng cho tới khi phần mềm báo **"Đã ổn định nhiệt"**.
   - Nếu có nhiệt kế, đo cả **nhiệt độ mẫu** lẫn **nhiệt độ ngăn tham chiếu** rồi nhập đầy đủ vào ứng dụng.

---

## 2. Cách đặt điện thoại và chụp ảnh

1. Bật tia laser vạch đỏ (650 nm, $\le 1\text{ mW}$) chiếu vuông góc qua lăng kính hai ngăn tới màn hứng mờ.
2. Che bớt ánh nắng hoặc đèn chói trực tiếp vào màn hứng để hai vạch sáng nổi rõ trên nền tối.
2. **Định dạng ảnh trên điện thoại (tránh lỗi HEIC / HEIF / WebP):**
   - Phần mềm hỗ trợ tốt ảnh **JPEG / PNG** (và BMP/TIFF). Điện thoại iPhone mặc định thường lưu định dạng **HEIC** hoặc một số ứng dụng xuất **WebP** không được OpenCV hỗ trợ trực tiếp (hệ thống sẽ báo lỗi `ANH_KHONG_HO_TRO_DINH_DANG`).
   - **Trên iPhone:** vào **Cài đặt > Camera > Định dạng > Tương thích nhất (JPEG)** trước khi chụp.
   - Hoặc chuyển/xuất ảnh sang **JPEG/PNG** rồi tải lên ứng dụng.
3. **Đặt điện thoại lên giá đỡ cố định**, giữ camera song song và thẳng góc với màn hứng:
   - Nếu muốn quy đổi theo đơn vị mm, đặt một **thước chuẩn** trên màn hứng cùng mặt phẳng hai vạch và dùng mục **Thang chuẩn (px/mm)** trên ứng dụng.
   - **Bật khóa phơi sáng và lấy nét (AE/AF lock)** trên camera trước khi chụp, rồi tích ô **"Đã khóa AE/AF"** trên giao diện.
   - Chỉnh vị trí sao cho hai vạch rõ nét nhưng **không bị lóa trắng bệt (bão hòa)** và nằm gần vùng trung tâm khung ảnh.
4. Nhấn **💧 KIỂM TRA NƯỚC NGAY** (hoặc **🎞️ Chuỗi 5 khung** nếu muốn lấy trung vị nhiều ảnh để giảm rung).

---

## 3. Cách đọc kết quả `"x ± U ‰"`

Ứng dụng không chỉ hiện một con số mà luôn hiển thị dạng **`x ± U ‰`** (ví dụ: `16.4 ± 0.3 ‰`):
- **`x`**: Độ mặn tương đương NaCl ước lượng tại thời điểm đo.
- **`± U`**: Khoảng bất định mở rộng (~95%). Ý nghĩa: giá trị thực quy chiếu nằm trong khoảng từ **`x - U`** đến **`x + U`** nếu phép đo hợp lệ và hệ thống đã được hiệu chuẩn bằng dữ liệu thật.
- **Chỉ số độ đục tương đối (0,00 – 1,00):** Phản ánh mức vạch laser bị tán xạ mở rộng và mờ đi do phù sa/tảo. Đây là thước đo tương đối để theo dõi xu hướng, **không phải** đơn vị NTU chuẩn.

---

## 4. Ý nghĩa các nhãn trạng thái & cờ cảnh báo

| Biểu tượng / Nhãn | Ý nghĩa | Bạn nên làm gì? |
| :--- | :--- | :--- |
| **✅ ĐẠT CHUẨN** | Ảnh đạt SNR tốt, không bị bẹt đỉnh rộng | Có thể lưu kết quả vào Nhật kí (nếu đã dùng đường chuẩn đo thật). |
| **⚠️ Đốm bão hòa cục bộ** | Có vài đốm sáng nhỏ (hạt speckle laser) chạm mức 250 nhưng chưa bẹt đỉnh dải rộng | Kết quả vẫn tính được; có thể giảm nhẹ phơi sáng cho lần chụp sau. |
| **🚨 Bão hòa rộng (cháy sáng)** | Vạch laser quá chói, đỉnh bị bẹt phẳng ở mức 255 | Giảm phơi sáng (EV) trên điện thoại hoặc giảm độ sáng tia laser rồi chụp lại. **Không lấy số đo này.** |
| **🚨 Vạch quá mờ / Nhòe** | SNR thấp hoặc FWHM quá lớn (hết nét hoặc nước quá đục) | Tắt bớt đèn nền, che sáng môi trường, lấy nét lại hoặc để lắng cặn thô trước khi đo. |
| **⚠️ Nền sáng không đều** | Ánh sáng nền chênh lệch lớn trên màn hứng | Che ánh sáng xiên; hoặc dùng nút **✏️ Kéo ROI** trên giao diện để khoanh tay 2 vùng chứa vạch. |
| **⚠️ / 🚨 Chênh nhiệt hai ngăn** | Chưa đo nhiệt độ ngăn tham chiếu, hoặc $T_{\text{mẫu}}$ chênh $T_{\text{tham chiếu}}$ vượt phạm vi hiệu chuẩn | Đo lại cả hai nhiệt độ hoặc chờ cân bằng nhiệt hai ngăn rồi đo lại. |
| **⚖️ SÁT RANH GIỚI** | Khoảng bất định `[x - U, x + U]` cắt ngang ranh giới ngưỡng tham chiếu | Chưa đủ cơ sở kết luận gọn về một phía; nên đo lặp lại nhiều khung hoặc kiểm tra bằng phương pháp đối chứng. |
| **⛔ KHÔNG ĐÁNH GIÁ ĐƯỢC** | Đường chuẩn là mô phỏng / chưa xác nhận nguồn, ảnh lỗi, chưa đo nhiệt độ, hoặc chênh nhiệt ngoài mô hình | Không dùng màu cảnh báo cho quyết định thực tế cho tới khi khắc phục nguyên nhân nêu trên màn hình. |
| **📋 CHƯA CÓ NGUỒN** | Loài này trong `config.yaml` chưa được nhóm điền ngưỡng có trích dẫn tài liệu | Liên hệ cán bộ khuyến nông/khuyến ngư địa phương để được tư vấn cụ thể cho giống và giai đoạn nuôi. |

---

## 5. Giới hạn quan trọng của phương pháp

1. **Độ mặn tương đương NaCl:** Đường chuẩn được pha từ muối tinh khiết NaCl. Nước ao thực tế có thêm các ion tự nhiên khác ($\text{Mg}^{2+}, \text{Ca}^{2+}, \text{SO}_4^{2-}\dots$) và chất hữu cơ hòa tan, nên có thể sai khác nhất định so với tổng muối hòa tan hoặc độ mặn chuẩn PSU đo bằng máy chuẩn phòng thí nghiệm.
2. **Phạm vi đường chuẩn:** Chỉ đọc số đo nằm **trong dải độ mặn và dải nhiệt độ** mà máy đã được hiệu chuẩn bằng dung dịch chuẩn. Khi thấy cảnh báo **NGOÀI DẢI**, kết quả là ngoại suy và không còn độ tin cậy định lượng.
3. **Không tự động khuyến cáo xử lí ao:** Phần mềm không đưa ra chỉ dẫn kỹ thuật nuôi trồng thủy sản hay nông nghiệp. Khi có dấu hiệu bất thường về chất lượng nước, hãy liên hệ **cán bộ khuyến nông / khuyến ngư** để được tư vấn chuyên môn.
