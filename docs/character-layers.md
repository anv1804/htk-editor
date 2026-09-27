# Ba lớp nhân vật

Xem thêm [đối chiếu frame, tự chọn màu và ghi nhớ chỉnh sửa](adaptive-sprite-processing.md).

Sau khi **Xử lý sprite**, nhân vật gồm ba PNG cùng kích thước sheet và tọa độ frame:

1. **Base**: nhân vật gốc không mặc đồ, nằm dưới cùng. Da mặt và bàn tay lộ ra lấy pixel từ base.
2. **Outfit**: áo, tay áo, quần, giày và phụ kiện thân. Phần da được tách để lộ base bên dưới.
3. **Tóc / mũ**: tóc, tóc dài phía sau, băng cài và mũ, nằm trên cùng.

Các nút **Base / Outfit / Tóc / mũ** phía trên canvas cho phép xem riêng từng lớp. Trong **Xuất ảnh**, tải riêng Base, Outfit và Tóc/mũ; ghép theo thứ tự trên để dựng lại kết quả. Base trong editor là lớp tham chiếu. Ảnh nguồn gốc được giữ lại.

Tô màu khi đang xem Outfit hoặc Tóc/mũ sẽ thuộc lớp đang chọn, kể cả pixel mới nằm ngoài hình cũ. Công cụ **Giữ Outfit (U)** và **Giữ tóc / phụ kiện đầu (W)** sửa lại phân loại của pixel nguồn. Undo/redo vẫn áp dụng cho cả mask và nét tô. Nét tô được gộp vào lớp tương ứng khi xuất, không cần lớp thứ tư. Tẩy toàn pixel vẫn có hiệu lực trên bản ghép và các lớp xuất.

Tóc nâu được phân loại riêng trước khi đánh giá vải nâu; màu áo không còn bị suy ra từ tóc. Phần dưới của băng cài theo đường mở của trán trong ảnh nguồn. Tóc dài có thể che cánh tay base, nhưng các viền cổ tay không tự nhập vào tóc. Với chế độ phác màu 32/64, tóc và outfit học bảng màu riêng trong cùng tổng giới hạn màu.

Ở chế độ **Phác màu sắc nét**, các sắc nâu trung gian của tóc được làm tối nhẹ 10%, đồng nhất giữa các frame. Băng cài xanh, phụ kiện sáng, viền tối, màu dùng chung với base/outfit và nét tô thủ công giữ nguyên; giới hạn tổng số màu không tăng. Chế độ giữ sắc độ gốc hoặc không giới hạn màu vẫn giữ màu tóc nguồn.

Logo Gemini được xử lý trước các bước tách lớp. Bộ dò hỗ trợ sai lệch vị trí do thu nhỏ sheet; các vùng không đủ bằng chứng vẫn giữ nguyên. Chi tiết ở [gemini-logo-cleanup.md](gemini-logo-cleanup.md).

API `/api/repair` trả về `baseLayer`, `outfitLayer`, `headwearLayer`, `image` và thứ tự trong `report.layers`. Các lớp outfit/headwear không chồng quyền sở hữu pixel. Base xuất giữ cả cơ thể nằm dưới trang phục; nếu dùng tẩy toàn pixel hoặc chế độ cũ dựng da, lớp Base xuất phản ánh thay đổi đó để phép ghép luôn khớp ảnh kết quả.

## Tái sử dụng tóc và trang phục

Bản `source-neckline-25` bổ sung bảo vệ cổ áo theo ảnh nguồn: so màu viền kem/vàng với da má, nhận dải ve áo liên tục xuống thân và giữ đường may chung. Pixel nhiễu màu trên một nét viền được xét theo hai điểm nối lân cận, không mở rộng vùng cắt theo toàn bộ ngực trần của base. Các vùng cổ thực sự hở vẫn lấy pixel từ base. Kiểm thử có cả tư thế nghiêng và giơ tay của bộ áo tím, cùng các bộ áo kem, tóc, găng và giày.

Bản `material-owned-layers-24` phân loại vùng trước khi giảm màu. Dây áo xanh nối với thân áo, kể cả viền tối và viền xám, thuộc Outfit; dây cài đầu rời vẫn có thể thuộc Tóc/mũ. Bảng màu giữ nhóm sắc xanh dương và xanh lá riêng, tránh ép dây áo sang màu băng cài. Kiểm tra mảnh rời được thực hiện lại trên từng lớp cuối cùng; cụm 1–3 pixel không có chỉnh sửa xác nhận được loại bỏ. Vệt thái dương rời dài hơn được kiểm tra thêm theo vị trí vùng mặt và màu viền. Các nét cọ màu thủ công giữ nguyên.

Da mặt sáng bị chia thành nhiều cụm bởi mắt/bóng đổ được xét cùng nhau để tìm đường trán. Không lấp cả mặt chỉ vì đường tóc bao quanh nó. Màu nâu bóng tối của mặt không đủ để kết luận rằng găng da, giày da hoặc giáp là da trần: vùng cơ thể phải có mẫu da sáng tương ứng trong ảnh nguồn trước khi mở rộng sang bóng đổ. Tay áo tím cạnh cổ cũng được giữ theo sắc vải.

Để ghép lại, dùng các PNG giữ nguyên toàn bộ kích thước, số hàng/cột và thứ tự tư thế; không tự cắt gọn riêng từng frame. `report.layerLayout` mô tả bố cục này. Tab **Sprite sheet** hiện đúng lớp Base/Outfit/Tóc-mũ đang chọn, giống chế độ xem một frame.

Các lớp xuất chỉ chứa phần nhìn thấy trong ảnh nguồn. Tóc nằm khuất hoàn toàn sau tay áo không có pixel gốc để khôi phục chính xác; đổi sang áo ngắn hơn có thể lộ phần khuyết đó. Kiểu tóc dài cần thứ tự lớp trước/sau phù hợp nếu dùng với trang phục có dáng khác hẳn. Vì vậy cần kiểm tra các tư thế che khuất khi ghép chéo; việc tách sạch không tự tạo ra phần hình đã bị che.
