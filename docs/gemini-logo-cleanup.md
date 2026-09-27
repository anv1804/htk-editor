# Xử lý logo Gemini trên outfit

Trong **Kích thước & bảng màu → Logo Gemini ở góc ảnh**, mặc định là **Tự nhận diện & khôi phục màu**. Bấm **Xử lý sprite** như bình thường. Chọn **Giữ nguyên** để tắt bước này; tùy chọn được lưu cùng dự án. Dự án cũ vẫn mở được.

Hệ thống kiểm tra dấu logo ở góc dưới bên phải của toàn ảnh, trước khi học màu, tách da, tóc và trang phục. Khi mẫu logo khớp đủ rõ, hệ thống đảo phép trộn màu trắng của logo để khôi phục màu bên dưới. Không xóa ô vuông ở góc, không làm mờ hay vẽ lại trang phục. Kích thước và alpha của ảnh không đổi. Nét mask và lớp tô thủ công vẫn được ưu tiên.

Ảnh nguồn và file gốc không bị ghi đè. Kết quả, lớp outfit và lớp tóc/phụ kiện đều dùng nguồn đã xử lý; chạy lại luôn bắt đầu từ ảnh gốc nên không sửa chồng nhiều lần. Thanh trạng thái báo số pixel đã khôi phục. JSON báo cáo có `logoCleanup` với trạng thái, vùng, mẫu và điểm khớp.

Các mẫu 36/48/96 px và một số tỉ lệ thu nhỏ được hỗ trợ. Ảnh bị cắt góc, biến dạng, nén mạnh hoặc logo quá nhỏ có thể không đủ bằng chứng: hệ thống giữ nguyên thay vì đoán và làm hỏng đồ. Nên dùng PNG nguồn rõ nhất có cùng bố cục/kích thước base. Không cam kết phục hồi chính xác những chi tiết đã mất do thu nhỏ hoặc nén.

Thuật toán chỉ xử lý dấu logo nhìn thấy. Không yêu cầu API, tải mô hình hay gửi ảnh ra ngoài. Các mặt nạ tham khảo từ [GeminiWatermarkRemover](https://github.com/PlayerYK/GeminiWatermarkRemover) và công trình [GeminiWatermarkTool của Allen Kuo](https://github.com/allenk/GeminiWatermarkTool); giấy phép MIT và nguồn phiên bản được giữ trong `tools/assets/gemini`.

CLI: `--logo-cleanup auto` (mặc định) hoặc `--logo-cleanup off`. API `/api/repair`: `logoCleanup: "auto" | "off"`.
