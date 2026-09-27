# Xưởng item

Mở **Xưởng item** trên thanh đầu editor, hoặc `Alt+J`. Đây là bảng vẽ riêng cho
phụ kiện/vũ khí; ảnh nguồn, thuật toán ghép outfit, mask và lịch sử của editor
không thay đổi khi vẽ trong xưởng.

## Từ ảnh thành item

1. Chọn PNG/JPG/WebP, hoặc kéo ảnh vào cửa sổ. Giới hạn 20 MB và 4 triệu pixel.
2. Kéo trên ảnh tham chiếu để chọn riêng vật phẩm.
3. Chọn kích thước, giới hạn màu và cách thu nhỏ. Pixel art dùng nearest-neighbor;
   ảnh chụp/tranh dùng thu nhỏ mượt trước khi đưa về alpha nhị phân và bảng màu.
4. Tách nền chỉ xóa vùng màu nối với mép vùng chọn. Màu nền và độ lệch có thể chỉnh;
   chi tiết sáng được bao kín không bị xóa. Ảnh phức tạp cần chọn vùng hoặc tô sửa.
5. Bấm **Đưa lên bảng vẽ**. Mỗi lần thay item đều có thể hoàn tác.

Có mẫu kiếm, trượng và khiên để bắt đầu không cần ảnh. Lưới 32/64/128 giữ pixel
khi đổi kích thước, không phóng to artwork. Phần vượt lưới nhỏ hơn sẽ bị cắt và có
thể khôi phục bằng hoàn tác.

## Vẽ và căn tay cầm

- `B`: cọ; `E`: tẩy; `G`: tô vùng; `W`: xóa vùng cùng màu; `I`: hút màu.
- `L`: đường thẳng; `R`: khung chữ nhật; công tắc đối xứng áp dụng cho nét vẽ/tô vùng.
- `A`: chọn điểm neo trên cán; `T`: bấm vị trí tay để chuyển neo tới đó.
- `V`: kéo item; mũi tên dịch 1px; Shift+mũi tên dịch 5px.
- Lật ngang, xoay 90°, viền trong 1px, gom màu không dithering.
- Ctrl+Z / Ctrl+Shift+Z hoặc Ctrl+Y: lịch sử riêng, tối đa 40 thao tác.

Preview ở trên bảng thuộc tính. Nhân vật, lưới và dấu neo chỉ dùng tham chiếu;
không được xuất vào PNG. Chọn **Gắn vào frame** để chép item vào lớp tô tay của
đúng frame đang xem. Canvas clipping chặn ghi sang frame bên cạnh. Thao tác này
có thể hoàn tác trong editor cũ; bấm **Xử lý sprite** để cập nhật PNG kết quả.
Item được gắn phía trước nhân vật, không tự suy luận ngón tay che cán vũ khí.

## Lưu

Bản nháp được lưu cục bộ riêng (`hkt-item-workbench-v1`). **Lưu bản vẽ** tạo
`*.item.json` có PNG, kích thước và neo; **Mở bản vẽ** kiểm tra định dạng trước
khi thay nội dung. **Xuất PNG** xuất toàn bộ lưới trong suốt để giữ tọa độ.
Ảnh tham chiếu và lịch sử hoàn tác không nhúng trong bản vẽ đã lưu.

Xử lý ảnh diễn ra trong trình duyệt. Đây là công cụ dựng/chỉnh item từ ảnh,
không phải mô hình sinh thêm góc nhìn hay tạo toàn bộ animation từ một ảnh.

Kiểm tra: chạy `npm test` và `npm run build` trong `tools/editor`.
