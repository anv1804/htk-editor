# Xưởng UI / HUD — khung ghép cho điện thoại

Bản v2: xem [danh mục, nghiên cứu và cách ghép nền riêng](ui-research-v2.md).

Mở **Xưởng UI / HUD** trên HKT Editor hoặc nhấn `Alt+U`.
Mặc định là điện thoại **ngang 16:9**, canvas pixel 640 × 360: phóng 2× thành
1280 × 720 hoặc 3× thành 1920 × 1080. Có thêm preset 19.5:9 và 20:9.
Đường vùng an toàn 16 px chỉ là hướng dẫn bố trí trong editor.

## Bộ khung sử dụng được

- Bảng trúc ghép, khung nút, khung chiêu, khung item và bảng túi đồ.
- Khung trúc dùng **3 mảnh**: một đốt ngang, một đốt dọc, một cụm lá phủ góc. Khung nút và item dùng cạnh/góc xanh 16 px; khung chiêu được vẽ lại theo kích thước bằng thuật toán midpoint, outline một nét 1 px, không có nhãn/nền/bóng.
- Khi thay đổi rộng/cao, nền và cạnh được lặp; đoạn cuối được cắt vừa chiều dài.
  Góc luôn giữ nguyên 16 × 16, không phóng méo.
- Bảng túi đồ ghép khung trúc với lưới ô item 40 px, khoảng cách 4 px.
  Số hàng/cột tự tính theo kích thước bảng.
- Joystick mặc định hiển thị 88 × 88, ở góc trái dưới; cụm chiêu ở góc phải dưới.
- Mây, lệnh bài, tiền đồng, ngọc bội, liên hoa và cuộn giấy là **đồ trang trí**.
  Chọn bộ lọc **Hoa văn** để thêm chúng. Chúng không nhận click trong scene xuất.

## Ghép và sửa trong editor

1. **Bộ thành phần** → chọn khung → **Ghép khung** để xem ảnh lắp hoàn chỉnh.
2. Bấm **Tách khung thành mảnh** để mở tab ghép và thấy từng mảnh riêng. Bảng trúc có ba mảnh; chúng cũng nằm ngay trong thư viện chính.
3. Chọn một góc, đốt cạnh hoặc nền ở bảng bên phải để vào **Vẽ pixel**.
   Có bút B, tẩy E, hút màu I, đổ màu G, lưới, Ctrl+Z và Ctrl+Shift+Z.
4. Nét sửa được dùng cho mọi khung dùng chung mảnh đó; ảnh tổng được dựng lại.
   **Về mẫu sinh** chỉ bỏ bản sửa của mảnh đang chọn.
5. Bấm `＋` trong thư viện để thêm khung vào HUD. Chọn khung trên HUD để sửa
   **Rộng khung / Cao khung**, tọa độ, nhãn, thứ tự lớp. Nhấp đúp để xem cấu tạo.
   Khung thường tối thiểu 32 px; túi đồ tối thiểu 184 × 156; joystick 64–116 px.
6. Bộ lọc **Đốt & góc rời** cho phép thêm từng mảnh độc lập vào HUD.
7. **Thử joystick** cho kéo núm và xem vector hướng. Tắt để tiếp tục bố trí HUD.
8. **Lưu thiết kế** giữ canvas, kích thước từng khung, layout và các bản sửa PNG.
   **PNG thành phần** xuất mảnh đang chọn hoặc khung ghép theo kích thước đang xem.

Bản nháp v3 riêng với bản nháp v1/v2. Có thể mở JSON phiên bản cũ; hình trang trí
cũ được giữ lại. Ảnh đã sửa tay giữ palette riêng khi đổi phong cách. Lịch sử
undo giữ 40 nét mỗi mảnh trong phiên; JSON lưu kết quả, không lưu lịch sử undo.
Các thông số rộng/cao bảng cũ, góc, độ dày và phù điêu dành cho các mẫu cũ.

## Xuất Godot

**Xuất bộ Godot** tạo ZIP chứa thư mục `ui_forge/`:

- PNG từng đốt/góc/nền và ảnh ghép xem trước.
- `HUD.tscn`: khung ghép bằng các TextureRect riêng; nút, chiêu, ô item và từng
  ô túi đồ là Button thật. Kích thước và bố cục theo thiết kế đang mở.
- `frame_button.gd`: phản hồi sáng/tối khi hover và nhấn.
- `joystick.gd`: chuột/cảm ứng; phát `direction_changed(Vector2)`, về tâm khi nhả.
- `preset.json`: schema v3 với canvas, layout, kích thước, recipe và bản sửa pixel.
- `theme.tres`: theme xanh trong suốt; `Scroll_v.tscn` và `Scroll_h.tscn`: thanh cuộn tương tác độc lập. `ASSEMBLY.txt`: hướng dẫn lắp ghép.

Chép thư mục vào project Godot 4. Đặt viewport 640 × 360 cho mẫu 16:9, stretch
canvas_items, aspect keep, texture filter Nearest. Các mảnh trong scene giữ
bố cục đã xuất; thay đổi kích thước trong xưởng rồi xuất lại để tính lại số đốt.
Nối Button.pressed, signal joystick và dữ liệu HP/MP/inventory với game.
Khung túi đồ hiện là các ô trống để gắn icon vật phẩm và logic của bạn.

## Source

- `tools/ui_segments.py`: vẽ và ghép các mảnh.
- `tools/ui_forge.py`: API, validation, layout và xuất Godot.
- `tools/ui_motifs.py`: đồ trang trí và joystick.
- `tools/editor/src/ui-assembly.ts`: lặp mảnh trong preview.
- `tools/editor/src/ui-studio.ts`: editor và bố cục.
- `tools/editor/src/ui-paint.ts`: vẽ pixel và undo.

Chạy `python tools/repair_outfit_ui.py --no-browser --port 8765`.
Sau khi sửa frontend chạy `npm run build` trong `tools/editor` rồi tải lại trang.
Sau khi sửa backend, khởi động lại server.


Cập nhật khung trúc: chỉ dùng **3 mảnh** — tre ngang 32 × 16, tre dọc
16 × 32 và cụm lá 32 × 32. Lá không chứa đốt tre; editor phản chiếu lá
để phủ bốn góc. Cạnh được nối từ một loại đốt cho mỗi hướng. Lòng tất cả
khung và bảng túi đồ trong suốt. Các mảnh trúc 9 phần cũ chỉ giữ để đọc
bản sửa cũ, không xuất hiện trong bộ lọc mảnh đang dùng.


Khung chiêu luôn giữ kích thước vuông để vòng tròn không thành ellipse; nhãn
chiêu trong thiết kế cũ được bỏ khi mở. Nút, item, vòng chiêu và joystick dùng
chung sắc xanh; chỉ joystick có mặt nền. Khung nút/item và track HP/MP có lòng
trong suốt. Các PNG mảnh riêng được xuất trong thư mục ui_forge.
