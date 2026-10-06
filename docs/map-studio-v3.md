# Map Studio v3 — layer + module

## Ý tưởng và chuẩn hình ảnh

Map tham chiếu 1983 × 793 px quyết định bố cục, chủ đề trúc/đá/cổng miếu và chiều sâu.
`Map_Layers_Dong_Bo/objects/gate_main.png` cùng `06_props.png` quyết định cảm giác đường
viền và chi tiết. Đây là mẫu thẩm mỹ người dùng chọn, không phải bằng chứng ảnh được vẽ
tay hay tuân thủ bảng màu của một máy console cụ thể.

Mục tiêu là silhouette rõ, cụm lá/đá có hình, ánh sáng theo từng mảng, viền tối có màu,
ít nhiễu hạt. Khóa mật độ pixel theo nhân vật 64 × 64 trước khi sản xuất terrain.
Tile lưới 16/32/64 px là thông số ráp, không ép mọi prop vào 64 × 64.

Giữ nguồn nguyên vẹn. Preview 100/200/400% dùng nearest và vị trí nguyên. Không dùng
Lanczos hoặc làm mượt mặc định cho asset đã được duyệt. Nền xa có thể giảm tương phản
và chi tiết để tạo chiều sâu; không cần blur. Alpha cứng phù hợp prop/terrain, còn sương,
nước và hiệu ứng có thể cần alpha mềm có chủ đích. Không ép alpha hoặc palette toàn map.

## Đã quan sát trong bộ nguồn

- 8 layer có chung canvas 1983 × 793; 20 object riêng và `layout.json`.
- Object đã nằm trong layer 05/06/08: importer chỉ đưa bản riêng vào thư viện.
- Cổng chính 175 × 139 px có 11.890 màu RGB nhìn thấy; phần lớn alpha lõi 251–253.
  Không thể suy ra mẫu chỉ có 16/32 màu hoặc alpha nhị phân từ ảnh chụp.
- Alpha terrain phần lớn 252–253, có nhiều pixel viền alpha thấp. Việc ép tất cả về
  255 hoặc xóa mọi mảnh rời có thể thay đổi lá nhỏ và biên vật thể.
- Ghép 8 layer bằng Pillow source-over sai khác 839.305 pixel so với preview, nhưng
  lệch tối đa chỉ 4/255 mỗi kênh và MAE RGB khoảng 0,318/255. Chưa kết luận nguyên nhân;
  tuyên bố “0 pixel khác biệt” trong file hướng dẫn không khớp phép kiểm này.
- Terrain có chuyển sắc mềm hơn props. Giảm palette/làm sắc không tự thiết kế lại các
  mặt đá và cụm lá; cần bản vẽ hoặc lượt tạo lại asset để đạt chất lượng mong muốn.

## Quy trình sản xuất

1. Nhập folder có `layout.json`, ZIP hoặc PNG độc lập. Giữ tọa độ và ảnh gốc.
2. Bật/tắt từng lớp để xem terrain, vật thể, nước. Khóa các layer nguồn lúc mới nhập.
3. Chọn/cắt vùng từ một layer thành module mới; vùng crop giữ pixel và có thể gồm
   nhiều thành phần rời. Không giả định connected component là một vật thể hoàn chỉnh.
4. Đặt module đúng kích thước, sửa pivot, kéo theo pixel/lưới, lật, nhân bản, đổi lớp.
5. Vẽ collision riêng cho nền đặc hoặc mặt sàn một chiều. Preview camera/parallax
   giúp kiểm tra khoảng hở; nội dung sau vật che phải được vẽ bù trước.
6. Xuất PNG toàn cảnh và project portable; metadata lưu lớp, pivot và collision.

## Kiến trúc

- Model v3: kích thước map tính bằng pixel; thư viện ảnh; lớp có vị trí/z/opacity;
  instance có vị trí nguyên và phép lật; collision riêng.
- Editor: cây layer bên trái, canvas giữa, thuộc tính bên phải, module dưới canvas.
- Import folder giữ layout; PNG thêm thư viện; ZIP được đọc trong RAM qua Python.
- Bộ dựng canvas dùng chung cho preview/export để tránh khác bố cục. Parallax là
  preview camera, PNG xuất luôn ở camera gốc.
- IndexedDB lưu project lớn; lịch sử lưu snapshot metadata, chuỗi nguồn ảnh không đổi.
  Không ghi đè khóa localStorage project v2.
- Giữ bàn làm sạch như công cụ riêng, mặc định trung tính; tạo phiên bản mới khi sửa.

## Khả năng và giới hạn của Python/AI

Pillow/NumPy làm tốt cắt, alpha/mask, palette, kiểm tra, đóng gói và ráp bố cục từ module.
Sinh địa hình bằng thuật toán chỉ cho chất lượng tương ứng với bộ module và quy tắc đã
thiết kế. Python không có sẵn khả năng vẽ nghệ thuật; có thể điều phối mô hình sinh ảnh.

Với ảnh phẳng, segmentation hỗ trợ mask theo click/box. Nó không phục hồi pixel bị che,
không tự phân biệt toàn bộ lớp chiều sâu chính xác và không thiết kế các cạnh tile ghép.
Inpainting là vẽ bù, có thể đổi chi tiết; phải duyệt lại.

Nên sản xuất một bộ nhỏ trước: mặt cỏ, góc trái/phải, thân đá, đáy đảo, cụm trúc, cầu,
thác và nước. Duyệt cạnh nối và mật độ pixel cạnh cổng mẫu ở 100%/400%; chỉ sau đó mở
rộng thư viện và autotile. Editor không gọi một bộ lọc là “chuẩn pixel art tự động”.

Nguồn kỹ thuật: [Pillow filters](https://pillow.readthedocs.io/en/stable/handbook/concepts.html#filters),
[SAM 2 masks](https://github.com/facebookresearch/sam2).

## Xử lý nét pixel đã triển khai

Mở **Xử lý nét pixel**. Chọn toàn bộ layer/module hoặc tải một ảnh map gốc. Chọn lưới
1 px để giữ mật độ; 2–4 px là quyết định thay đổi mật độ và sẽ lấy mẫu lại alpha/màu.
Mặc định: 128 màu, mức gom cân bằng, 3 lượt, giữ alpha. Có thể dùng 192/256 màu nếu
chuyển sắc hoặc chi tiết bị mất. Bảng màu là thông số xử lý thử, không phải định nghĩa
hay chứng nhận “16-bit”.

Pipeline: phân tích alpha và tương phản cục bộ → gom màu gần nhau bên trong vùng
đặc → bảo vệ nét tương phản cao → lấy mẫu màu có tăng trọng số các sắc hiếm (sen
hồng/đèn đỏ) → học palette chung bằng Oklab → gom các cụm nhỏ tương đồng màu →
đóng gói đúng kích thước. Mẫu cổng chỉ điều chỉnh ngưỡng bảo vệ chi tiết, không phải
mô hình học phong cách. Thuật toán không vẽ lại hình dáng mặt đá/cụm lá theo ngữ nghĩa.

Server xử lý ở worker riêng, một lượt tại một thời điểm; kiểm tra hủy và deadline ở
các chặng tính toán. Giới hạn 300 giây tính toán, 16 triệu pixel/lượt, 128 ảnh và
32 MB payload. Thời gian tải lên không nằm trong 300 giây; trình duyệt dành tối đa
120 giây cho yêu cầu tải lên. Không trì hoãn giả để đủ 3–5 phút. Nếu mất kết nối,
**Tiếp tục theo dõi** lấy lại cùng job, không tạo job trùng. Tối đa hai kết quả gần
nhất được giữ tạm trong RAM trong 30 phút; restart server làm mất các job này.

Sau khi so sánh, **Áp dụng** cập nhật đồng bộ các ảnh của map hiện tại và lưu
`originalSrc`. Xử lý lại luôn bắt đầu từ nguồn gốc, tránh cộng dồn bộ lọc. Với ảnh
phẳng tải lên, tạo map mới có lớp gốc ẩn, lớp xử lý hiện và lớp module rỗng;
không tự gọi đó là các lớp nền/terrain/props đã tách. Hoàn tác trả lại map trước.

PNG xuất dùng chung compositor với preview ở camera gốc. Project JSON giữ ảnh nguồn,
kết quả, layer và collision; IndexedDB lưu tự động, không ghi đè project v2.
