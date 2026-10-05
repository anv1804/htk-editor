# Nghiên cứu asset map từ bộ ảnh đã gửi

Ngày 06/10/2026. Mục tiêu: từng item rõ chi tiết trong Aseprite, màu sạch, giữ hình dáng và có quy cách để ghép vào game.

**Kết luận:** Python có thể làm tốt phần tách có kiểm soát, chuẩn hóa alpha, làm sạch màu, xuất asset và kiểm tra mối nối. Python cũng có thể tô lại trong một khuôn đã duyệt. Tuy nhiên, một bộ lọc tự động không thể bảo đảm khôi phục đúng chi tiết đã mất, hiểu chính xác mọi vật thể, hoặc biến sheet minh họa thành tileset khớp cạnh chỉ bằng cắt và giảm màu. Muốn đạt chất lượng ổn định cần khuôn từng item, đường cấu trúc quan trọng, quy tắc màu/vật liệu và quy tắc ghép tile.

## Đã kiểm tra trực tiếp

- Sheet gửi kèm: **1536 × 1024**, RGBA. Alpha có các mức 0–254; không có pixel alpha 255. Vì vậy sheet này đã chứa thông tin trong suốt mềm. Không nên bỏ alpha rồi xóa nền theo một màu suy đoán.
- ZIP chứa **307 PNG item**. Tất cả đều chỉ có alpha 0/255. Số màu RGB hiện được đo tối đa là **65**, trong đó 5 file có 65 màu; không phải hàng nghìn màu mỗi item. Manifest ghi dùng MAXCOVERAGE, tối đa 64 màu, không dithering và có thêm viền tối 1 px. Mức 65 màu có thể liên quan màu viền thêm sau bước giảm màu, nhưng không có mã tạo ZIP để xác nhận.
- Số thứ tự trong ảnh chụp Aseprite không trùng ZIP: cổng trong ZIP là `asset_167.png`, cụm tre là `asset_158.png`. Bục đá rộng 112 × 61 là `asset_019.png`.
- Có 47 file có ít nhất một chiều dưới 16 px. Đây là dấu hiệu cần duyệt việc gom item; không thể từ con số đó kết luận tất cả đều là lỗi, vì các chi tiết nhỏ có thể là asset hợp lệ.
- Ảnh map và sheet là hai ảnh riêng, khác kích thước và bố cục. Không có dữ liệu layer/mesh để chứng minh mọi asset trong sheet là bản cắt nguyên vẹn từ ảnh map.

**Điểm quan trọng:** nhiều màu không tự gây mờ. Mờ có thể đã nằm trong RGB nguồn, do cách resize/lọc hoặc do alpha pha với nền. Giảm màu quá mạnh lại gây loang thành mảng, mất bậc sáng tối và tạo đốm màu. Alpha nhị phân cũng không sửa được RGB đã dính màu nền hoặc bị lượng tử hóa sai.

## Thử nghiệm đã làm

Mã `study.py` dùng Pillow và NumPy; không dùng ImageGen, không phóng lớn asset xuất và không vẽ thêm chi tiết tưởng tượng.

| Mẫu | Kích thước xuất | ZIP | Bản dùng palette 128 màu chung |
|---|---:|---:|---:|
| Bục đá/cỏ | 112 × 61 | 64 màu | 108 màu được dùng |
| Cổng | 163 × 154 | 64 màu | 126 màu được dùng |
| Cụm tre | 83 × 132 | 64 màu | 78 màu được dùng |

Quy trình:

1. Lấy lại RGB và alpha từ sheet, dùng tọa độ trong manifest. Với ba mẫu, kích thước PNG bằng khung manifest bỏ 1 px mỗi cạnh; thử nghiệm dùng cách căn này để so sánh cùng kích thước.
2. Tạo mặt nạ bằng alpha hai ngưỡng: pixel alpha ≥200 làm hạt giống, giữ phần alpha ≥110 nối với hạt giống. Không co viền toàn bộ, không chỉ giữ thành phần lớn nhất nên các lá rời có hạt giống vẫn có thể được giữ.
3. Duyệt trực quan khung cổng và loại **5 vùng nhỏ** chứa mảnh lân cận/cành thừa. Các hình chữ nhật loại bỏ được ghi rõ trong mã và `audit.json`. Đây là hiệu chỉnh mặt nạ có hướng dẫn, **không phải tách hoàn toàn tự động**.
4. Lọc bilateral nhẹ 3 × 3, chỉ dùng pixel thuộc mặt nạ. Pixel nền ẩn không được trộn vào màu vật thể. Cách này làm dịu biến thiên nhỏ nhưng giữ tương đối các cạnh có tương phản mạnh; nó không khôi phục chi tiết.
5. Chỉnh nhẹ độ sáng/tương phản và độ đậm màu trong Oklab. Không thay góc nhìn, không thay vị trí vùng bóng, không suy luận hay dựng lại nguồn sáng 3D.
6. Xuất `detail.png`: giữ nhiều màu để ưu tiên chuyển sắc và chi tiết. Xuất `palette128.png`: cùng bảng màu học từ cả ba mẫu, ánh xạ theo khoảng cách màu cảm nhận, không dithering. Có thêm bản `palette48.png` để xem tác động của việc ép ít màu hơn.
7. Từ mặt nạ đã duyệt, cả ba bản xử lý giữ nguyên mặt nạ, kích thước và vị trí pixel. Không thêm viền ngoài làm dày hình. Ảnh so sánh chỉ phóng nguyên lần bằng Nearest.

**Kết quả quan sát:** bản lấy lại nguồn giữ mặt cột và mặt đá liên tục hơn; bản ZIP có nhiều đốm màu tương phản và viền ngoài dày hơn. Bản 128 màu giảm số màu rõ rệt nhưng vẫn có thể làm mất chuyển sắc nhỏ. Bản nhiều màu phù hợp hơn nếu ưu tiên giống tranh map và giữ chi tiết. Cả hai vẫn còn giới hạn độ nét của ảnh nguồn; đây chưa phải bộ asset được họa sĩ dựng lại từng nét.

Đã kiểm tra kích thước, alpha nhị phân, giới hạn palette và mặt nạ không đổi giữa các bản tô màu. Đã xem trên nền caro, trắng và xanh đen. Đây là kiểm tra kỹ thuật và duyệt trực quan, không phải phép đo độ chính xác so với một bộ asset chuẩn do họa sĩ cung cấp. Mặt nạ alpha tự suy ra có thể vẫn sai ở vùng mờ hoặc chi tiết mảnh.

## Muốn Python “vẽ đè đúng khuôn + góc + bóng”

Nên lưu mỗi item thành một bộ hướng dẫn thay vì chỉ một PNG:

- **Khuôn/alpha đã duyệt:** hình dạng ngoài, các lỗ trống, các bộ phận rời được phép. Đây là phần khóa để tô không lẹm.
- **Vùng vật liệu:** cỏ, đá, gỗ, ngói, kim loại, hoa, nước. Không nên phân loại chỉ theo hue: bóng của lá có thể gần màu ngói, rêu gần màu đá.
- **Đường cấu trúc:** mép mái, khe đá, cột, nan cầu, thân tre. Giữ các đường này khi gom những đốm màu nhỏ thành mảng sạch. Lọc ảnh chung không biết đường nào là quan trọng.
- **Bản đồ sáng tối:** có thể giữ ánh sáng sẵn trong nguồn, hoặc vẽ lại các vùng sáng/trung gian/bóng theo một hướng sáng chung. Nếu muốn chiếu sáng mới theo hình học, cần normal/depth hoặc hướng dẫn tương đương; một ảnh RGB không cung cấp đầy đủ thông tin đó.
- **Bảng màu theo vật liệu:** các dải màu từ tối tới sáng, dùng chung giữa những item liên quan. Tránh vừa chỉnh bão hòa tùy tiện vừa ép mọi item về một số màu quá thấp.

Với những dữ liệu này, Python có thể rasterize đường nét, tô vùng, áp palette và xuất hàng loạt một cách lặp lại được. Phần khó nằm ở tạo/duyệt khuôn và cấu trúc ban đầu. Có thể dùng phân đoạn hỗ trợ rồi chỉnh một lần. Những nét nhỏ đã biến mất trong ảnh cần dựng lại có chủ đích; không thể gọi phần suy đoán đó là khôi phục chính xác.

Nếu asset cần hiển thị lớn hơn nhiều, nên dựng/tạo lại từng item ở độ phân giải đích, cùng góc nhìn và hướng sáng. Bục đá 112 × 61 chỉ có 6.832 vị trí pixel: phóng 400% trong Aseprite không làm nó có thêm chi tiết hình học.

## Điều kiện để lắp vào game khớp

**Prop và tile địa hình cần quy cách khác nhau.** Cổng/cây có thể là sprite kích thước tự do với điểm chân/pivot. Nền cỏ, tường đá và góc địa hình phải có cạnh nối theo cùng một quy tắc. Không ép cổng hoặc bục đá thành hình vuông 64 × 64 vì sẽ biến dạng hoặc giảm chi tiết.

Quy trình tileset nên gồm:

1. Chốt kích thước ô logic, tỷ lệ nhân vật, cao độ mặt đứng và góc nhìn. Chưa có đủ thông tin để chọn thay người dùng một grid 32/48/64 px.
2. Tạo các mảnh giữa, mép trái/phải, mặt trên/dưới, góc lồi/lõm và chuyển tiếp cần dùng. Các mảnh liên quan tái sử dụng cùng dải biên, độ dày lớp cỏ và quy tắc sáng tối.
3. Gán nhãn cạnh/góc để engine hoặc công cụ terrain biết mảnh nào được nối. Nhãn không tự sửa một hình vẽ đang lệch: vẫn phải dựng dải nối tương thích.
4. Ghép thử nhiều tổ hợp trong patch 3 × 3 hoặc lớn hơn. Kiểm tra đường đi, silhouette, khe alpha và thay đổi màu ở mối nối; với các cặp được thiết kế chia sẻ đúng dải biên, có thể so sánh pixel tự động.
5. Xuất origin/pivot, điểm gắn cầu/thang, collision riêng và atlas có khoảng đệm phù hợp cách lấy mẫu của engine. Cạnh hình nhìn được và cạnh va chạm không nhất thiết trùng hoàn toàn.

Tiled hỗ trợ Terrain Sets theo cạnh, góc hoặc cả hai; Godot cũng có thiết lập terrain và các lớp dữ liệu TileSet. Các công cụ này cần bộ tile được chuẩn bị đúng trước. Thử nghiệm hiện tại **chưa tạo tileset nối cạnh, chưa thiết lập collision và chưa xác nhận chạy trong game**.

Trong workspace còn có `tools/map_asset_extractor.py`: mã đang dùng nhiều tọa độ giả định sheet 1024 × 682, trong khi sheet gửi lần này là 1536 × 1024, có resize Lanczos lên 64 × 64 và xóa nền dựa vào màu tối. Đây là các điểm cần sửa trước khi dùng script đó cho bộ ảnh này. Không có bằng chứng script đó đã tạo ZIP đang kiểm tra, nên không quy các lỗi ZIP cho script. Chưa sửa script hay tích hợp vào editor trong nghiên cứu này.

## Cách xem kết quả

- Mở `output/comparison.png`: nguồn / ZIP / bản nhiều màu / bản 128 màu.
- Mở `output/background-check.png`: nhìn viền trên nền trắng và tối.
- Mở trực tiếp `output/platform/detail.png`, `output/gate/detail.png`, `output/bamboo/detail.png` trong Aseprite để đánh giá giữ chi tiết.
- So sánh với `palette128.png` cùng thư mục nếu muốn palette gọn hơn. Các PNG là RGBA; tên palette mô tả giới hạn màu RGB, không có nghĩa file đã chuyển sang indexed mode.
- Xem ở 100%, 200% hoặc 400%; đánh giá cả ở kích thước game thật. Độ nét của bản phóng Nearest không phải bằng chứng đã có thêm chi tiết.

Chạy lại từ thư mục nghiên cứu, chỉ cần Pillow và NumPy:

```powershell
python study.py --sheet 'C:\Users\Admin\Downloads\5718c50d-12f1-4233-987c-24bf158bce79.png' --zip 'C:\Users\Admin\Downloads\assets_optimized_outline_v3 (1).zip' --out output
```

## Tài liệu đối chiếu

- [Pillow: quantize, palette, dithering và resize](https://pillow.readthedocs.io/en/stable/reference/Image.html): các công cụ giảm màu, chọn bộ lọc và xuất ảnh. Thử nghiệm dùng MEDIANCUT để học palette; tự ánh xạ màu trong Oklab.
- [OpenCV: bilateral filtering](https://docs.opencv.org/4.x/d4/d13/tutorial_py_filtering.html): làm mượt dựa trên cả khoảng cách không gian lẫn khác biệt màu để giảm ảnh hưởng qua cạnh. Bản thử cài đặt một phiên bản nhỏ bằng NumPy, không cần cài OpenCV.
- [OpenCV: morphology](https://docs.opencv.org/4.x/d9/d61/tutorial_py_morphological_ops.html): erosion làm co biên, dilation làm nở biên. Vì vậy không dùng chúng mặc định trên toàn bộ lá, dây và hoa văn mảnh.
- [Oklab, tác giả Björn Ottosson](https://bottosson.github.io/posts/oklab/): mô hình và công thức chuyển đổi để xử lý độ sáng và màu.
- [Tiled: Using Terrains](https://docs.mapeditor.org/en/stable/manual/terrain/): quy tắc terrain theo góc/cạnh.
- [Godot: Using TileSets](https://docs.godotengine.org/en/stable/tutorials/2d/using_tilesets.html): tổ chức TileSet, terrain và các lớp dữ liệu liên quan.

Ba mẫu này là bằng chứng khả thi cho một bước làm sạch có kiểm soát. Để sản xuất toàn bộ bộ asset cần duyệt danh sách item/khuôn, chọn quy cách hiển thị rồi dựng hệ tile nối cạnh; không nên xử lý mù toàn bộ 307 file rồi coi đó là một tileset hoàn chỉnh.
