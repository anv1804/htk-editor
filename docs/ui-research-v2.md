# Bộ UI tu tiên v2

## Quy tắc hình ảnh

- Canvas điện thoại ngang 16:9, 640 × 360 pixel logic. Dùng 1280 × 720 ở mức 2× khi cần giữ pixel đều.
- Vòng chiêu: thuật toán midpoint, một nét 1 pixel, một màu, không bóng, không nền, không chữ. Vẽ lại theo đường kính từng instance; xuất PNG đúng kích thước.
- Khung nút, ô item, tab, tooltip và dòng danh sách: viền xanh đơn giản một nét, tâm trong suốt.
- Bảng trúc: một đốt ngang, một đốt dọc và một cụm lá phủ góc. Cạnh lặp, lá được phản chiếu, không kéo giãn.
- Nền giấy, ngọc tối và vải xanh là các tile riêng. Đặt nền phía sau khung; không gộp nền vào ảnh viền.
- Joystick giữ nền để nhìn rõ vùng điều khiển. Mây, đồng xu, lệnh bài và ngọc bội thuộc nhóm trang trí tùy chọn.

## Danh sách thành phần đề xuất

Đây là đề xuất cho game của bạn, dựa trên các màn hình thường cần; tài liệu bên dưới hướng dẫn cơ chế dựng control.

| Nhóm | Có trong thư viện v2 | Khi nối với game |
|---|---|---|
| Chiến đấu | Vòng chiêu, nút, ô vật phẩm nhanh, joystick, khung thanh HUD | Gắn cooldown, HP/MP và sự kiện hành động |
| Túi đồ | Khung trống, bảng có ô ghép, ô item, tab, dòng danh sách | Dữ liệu item, lọc/sắp xếp, kéo thả, chọn ô |
| Trang bị | Khung preview nhân vật, ô trang bị, bảng thuộc tính, tooltip | Render nhân vật đang mặc và so sánh chỉ số |
| Chat | Khung lịch sử, khung nhập, nút gửi | RichTextLabel, LineEdit; nối kênh chat |
| Cuộn | Rãnh và con trượt ngang/dọc độc lập | ScrollContainer cho nội dung, thanh cuộn tương tác |
| Hội thoại | Khung hội thoại, khung xác nhận, nút lựa chọn | Văn bản, lựa chọn, trạng thái mở/đóng |
| Vật liệu nền | Giấy trúc, ngọc tối, vải xanh | Lớp riêng, lặp tile 32 × 32 |

Các phần nên bổ sung sau khi xác định gameplay: khung nhiệm vụ, bản đồ, cửa hàng, menu thiết lập, thông báo nhỏ và khung nhóm/đồng đội. Chưa cần vẽ icon cho các phần này.

## Nghiên cứu áp dụng

- [Godot NinePatchRect](https://docs.godotengine.org/en/stable/classes/class_ninepatchrect.html): giữ nguyên góc, lặp cạnh; dùng chế độ TILE để tránh méo pixel. Có thể tắt `draw_center` để không vẽ nền.
- [Godot StyleBoxTexture](https://docs.godotengine.org/en/stable/classes/class_styleboxtexture.html): chia 9 vùng để skin control theo kích thước. Theme xuất kèm dùng tâm trong suốt.
- [Godot ScrollContainer](https://docs.godotengine.org/en/stable/classes/class_scrollcontainer.html): nội dung cuộn phải nằm trong container; con trượt thay đổi theo kích thước nội dung. Hai PNG rãnh/con trượt riêng là vật liệu tạo control, không tự chứa dữ liệu túi đồ/chat.
- [Godot SubViewportContainer](https://docs.godotengine.org/en/stable/classes/class_subviewportcontainer.html): có thể hiển thị nhân vật trong viewport riêng ở bảng trang bị. Với nhân vật sprite 2D đơn giản, cũng có thể đặt Sprite2D trong SubViewport.
- [Android touch target size](https://support.google.com/accessibility/android/answer/7101858?hl=en-GB): nên dành vùng chạm khoảng 48 dp và khoảng cách giữa các nút; dp không tương đương pixel logic của canvas. Có thể mở rộng vùng bấm quanh hình viền mà không làm ảnh dày hơn.

## Editor

- Tìm kiếm và lọc theo nhóm; nền riêng nằm trong nhóm Nền riêng.
- Ba bố cục mẫu: chiến đấu, túi đồ + trang bị, chat + hội thoại. Áp dụng mẫu có thể hoàn tác.
- Kéo bố trí, nhập vị trí/kích thước, đổi thứ tự lớp, nhân đôi, xóa, ẩn và khóa lớp.
- Hoàn tác/làm lại bố cục: nút ↶/↷ hoặc Ctrl+Z/Ctrl+Shift+Z khi đang ở HUD.
- Khung trúc/khung chữ nhật: tách mảnh, chọn mảnh, vẽ pixel; sửa mảnh áp dụng cho các khung dùng chung.
- Vòng tròn và viền thanh cuộn là hình sinh theo kích thước: không tách thành các góc vuông và không co giãn ảnh vòng.
- Lưu/mở JSON giữ bố cục và pixel đã sửa; xuất PNG thành phần và ZIP Godot. `HUD.tscn` giữ các lớp rãnh/con trượt bạn bố trí; `Scroll_v.tscn` và `Scroll_h.tscn` là VScrollBar/HScrollBar dùng được, có tín hiệu `value_changed` để nối nội dung cuộn.

Khung preview trang bị là vùng để bạn ghép nhân vật. Editor không tự lấy dữ liệu nhân vật/trang bị từ game. Chat chưa nối mạng; tín hiệu nút cần nối gameplay trong Godot.
