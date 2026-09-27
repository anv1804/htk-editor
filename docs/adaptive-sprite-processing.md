# Đối chiếu frame và ghi nhớ chỉnh sửa

Chọn **Tự chọn màu**, **Phác màu sắc nét**, bật **Rõ viền & đường may**, rồi bấm **Xử lý sprite**. Base và outfit cần cùng kích thước và bố cục frame.

- Tool lấy mẫu chất liệu tóc từ các vùng đã nhận diện trên toàn sheet, học vị trí tương đối theo đầu, rồi đối chiếu lại tóc mái và tóc sau lưng. Một mảng tóc bị khăn hoặc tay áo che ngang vẫn có thể thuộc lớp Tóc/mũ dù không nối liền với búi tóc.
- Mỗi vòng chỉ bổ sung pixel có trong ảnh nguồn, đúng màu và vùng hình học cho phép. Bảng mẫu cố định trong lần chạy; pixel tự đoán không trở thành dữ liệu huấn luyện mới. Dừng khi hội tụ hoặc đạt 16 vòng. Chạy lại cùng đầu vào không tự tích lũy thay đổi.
- Viền dưới băng cài được kiểm tra ở ranh giới tóc–da; viền ngoài dùng màu tối xuất hiện ổn định trong chất liệu. Viền đi vào trong hình, không nở ra nền. Mảnh viền tóc sót ở Outfit được trả về đúng lớp; mảnh mặt rời không có nét sửa thủ công được dọn riêng.
- **Tự chọn màu** chọn ngân sách từ độ phức tạp của chất liệu và số màu phải giữ của base/nét tô. Tóc và outfit dùng bảng màu riêng trong cùng giới hạn. Không dithering hoặc làm nhòe bằng nội suy. **Giữ gốc** tiếp tục giữ các màu nguồn.

## Ghi nhớ từ lần sửa trước

1. Dùng **Giữ tóc (W)**, **Giữ Outfit (U)**, **Lộ base (R)** hoặc cọ màu để sửa vùng sai.
2. Mở **Điều chỉnh → Đối chiếu & ghi nhớ → Nhớ nét sửa**.
3. Bấm **Xử lý sprite**. Nhãn bạn đã xác nhận được giữ ở đúng pixel; các mẫu màu tóc và nhãn loại trừ giúp đối chiếu các vùng tương tự trong sheet.

Ghi nhớ lưu trong trình duyệt, gắn với nội dung Base, Outfit và grid. Thay bộ ảnh không áp nhầm ghi nhớ cũ. Nét sửa hiện tại ưu tiên hơn ghi nhớ. Có thể bỏ chọn **Dùng chỉnh sửa đã ghi nhớ**, hoặc **Quên bộ này**; thao tác quên không xóa nét đang vẽ. Dữ liệu tự xử lý không tự được ghi nhận là đúng.

Nếu còn ứng viên chưa đủ chắc, báo cáo liệt kê frame cần kiểm tra và có nút chuyển đến frame đó. Đây là đối chiếu bằng mẫu và phản hồi cục bộ, không phải huấn luyện một mô hình AI tổng quát. Những chi tiết không tồn tại trong ảnh nguồn hoặc tóc/vải có cùng màu, hình dạng và vị trí vẫn có thể cần nhãn người dùng.

API trả `report.learning` với số vòng, số pixel tóc phục hồi, mảng tóc bị che, ngân sách màu tự chọn, frame cần kiểm tra và số pixel ghi nhớ. Ba lớp xuất vẫn ghép lại đúng ảnh kết quả theo thứ tự Base → Outfit → Tóc/mũ.
