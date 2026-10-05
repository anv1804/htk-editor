"""
Map Asset Extractor Tool
Trích xuất tự động toàn bộ Asset Sheet (Tileset, Platforms, Props, Parallax) từ ảnh AI:
- Chuẩn hóa tileset về 64x64 px sạch viền
- Tách nền trong suốt (transparent RGBA) cho Props và Platforms
- Cắt các lớp nền Parallax
- Xuất manifest.json để game/editor nạp trực tiếp
"""

import os
import sys
import json
from pathlib import Path
from PIL import Image, ImageFilter
import numpy as np

# Ensure UTF-8 output on Windows console
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass


def extract_tileset(img, output_dir, target_size=(64, 64)):
    """
    Trích xuất lưới tileset ở góc trên bên trái, chuẩn hóa về đúng 64x64 px
    """
    tiles_dir = output_dir / "tiles"
    tiles_dir.mkdir(parents=True, exist_ok=True)
    
    # Tọa độ khung lưới tileset (8 cột x 7 hàng) trong ảnh
    cols = 8
    rows = 7
    # Tọa độ vùng lưới trong ảnh gốc 1024x682
    grid_x0, grid_y0 = 4, 4
    grid_w, grid_h = 305, 265
    
    cw = grid_w / cols
    ch = grid_h / rows
    
    tile_paths = []
    atlas_img = Image.new("RGBA", (cols * target_size[0], rows * target_size[1]))
    
    for r in range(rows):
        for c in range(cols):
            x1 = int(grid_x0 + c * cw)
            y1 = int(grid_y0 + r * ch)
            x2 = int(grid_x0 + (c + 1) * cw)
            y2 = int(grid_y0 + (r + 1) * ch)
            
            # Shave 1-2px border để loại bỏ đường viền đen của lưới
            inset_x = max(1, int(cw * 0.05))
            inset_y = max(1, int(ch * 0.05))
            cell = img.crop((x1 + inset_x, y1 + inset_y, x2 - inset_x, y2 - inset_y))
            
            # Upscale chính xác về 64x64 px bằng bộ lọc Lanczos chất lượng cao
            tile = cell.resize(target_size, Image.Resampling.LANCZOS)
            
            name = f"tile_r{r:02d}_c{c:02d}.png"
            path = tiles_dir / name
            tile.save(path)
            tile_paths.append(str(path.relative_to(output_dir)))
            
            atlas_img.paste(tile, (c * target_size[0], r * target_size[1]))
            
    atlas_path = output_dir / "tileset_atlas_64x64.png"
    atlas_img.save(atlas_path)
    return {
        "count": len(tile_paths),
        "atlas": str(atlas_path.relative_to(output_dir)),
        "tiles": tile_paths
    }


def remove_dark_background(rgba_img, threshold=24):
    """
    Khử màu nền đen/navy đậm thành nền trong suốt (Alpha = 0)
    """
    arr = np.array(rgba_img).copy()
    r = arr[:, :, 0].astype(int)
    g = arr[:, :, 1].astype(int)
    b = arr[:, :, 2].astype(int)
    
    # Tính độ sáng và khoảng cách tới màu nền đen/teal đậm ([2, 13, 17])
    bg_dist = np.sqrt((r - 2)**2 + (g - 13)**2 + (b - 17)**2)
    max_c = np.maximum(np.maximum(r, g), b)
    
    is_bg = (bg_dist < threshold) | (max_c < 18)
    arr[is_bg, 3] = 0
    return Image.fromarray(arr)


def find_components_boxes(mask, min_w=12, min_h=12, pad=2):
    """
    Tìm bounding box của các vật thể rời rạc từ mask nhị phân
    """
    h, w = mask.shape
    visited = np.zeros((h, w), dtype=bool)
    boxes = []
    
    # Downsample nhẹ để tìm bounding box nhanh
    for y in range(0, h, 2):
        for x in range(0, w, 2):
            if mask[y, x] and not visited[y, x]:
                # BFS tìm cụm
                min_x, max_x = x, x
                min_y, max_y = y, y
                queue = [(y, x)]
                visited[y, x] = True
                pixel_count = 0
                
                while queue:
                    cy, cx = queue.pop()
                    pixel_count += 1
                    min_x = min(min_x, cx)
                    max_x = max(max_x, cx)
                    min_y = min(min_y, cy)
                    max_y = max(max_y, cy)
                    
                    # 4 láng giềng bước 2
                    for dy, dx in ((-2, 0), (2, 0), (0, -2), (0, 2), (-2, -2), (2, 2)):
                        ny, nx = cy + dy, cx + dx
                        if 0 <= ny < h and 0 <= nx < w and mask[ny, nx] and not visited[ny, nx]:
                            visited[ny, nx] = True
                            queue.append((ny, nx))
                            
                bw = max_x - min_x + 1
                bh = max_y - min_y + 1
                if bw >= min_w and bh >= min_h and pixel_count >= 15:
                    boxes.append((
                        max(0, min_x - pad),
                        max(0, min_y - pad),
                        min(w, max_x + 1 + pad),
                        min(h, max_y + 1 + pad)
                    ))
                    
    # Hợp nhất các box chồng chéo
    merged = []
    for b in boxes:
        bx1, by1, bx2, by2 = b
        absorbed = False
        for i, m in enumerate(merged):
            mx1, my1, mx2, my2 = m
            # Kiểm tra va chạm hoặc rất gần nhau
            if not (bx2 < mx1 - 4 or bx1 > mx2 + 4 or by2 < my1 - 4 or by1 > my2 + 4):
                merged[i] = (min(bx1, mx1), min(by1, my1), max(bx2, mx2), max(by2, my2))
                absorbed = True
                break
        if not absorbed:
            merged.append(b)
            
    # Lọc lại kích thước tối thiểu
    return [b for b in merged if (b[2] - b[0]) >= min_w and (b[3] - b[1]) >= min_h]


def extract_props(img, output_dir):
    """
    Trích xuất toàn bộ vật thể trang trí (Props) ở dải giữa:
    cổng miếu, cây hoa anh đào, bụi trúc, đèn lồng, cầu treo, bánh xe nước...
    """
    props_dir = output_dir / "props"
    props_dir.mkdir(parents=True, exist_ok=True)
    
    # Dải vật thể: y từ ~275 đến ~475
    crop_region = img.crop((0, 275, 1024, 475)).convert("RGBA")
    clean_region = remove_dark_background(crop_region, threshold=25)
    
    arr = np.array(clean_region)
    mask = arr[:, :, 3] > 0
    
    boxes = find_components_boxes(mask, min_w=12, min_h=14)
    # Sắp xếp từ trái sang phải, trên xuống dưới
    boxes.sort(key=lambda b: (b[1] // 30, b[0]))
    
    prop_paths = []
    for idx, (x1, y1, x2, y2) in enumerate(boxes):
        item = clean_region.crop((x1, y1, x2, y2))
        name = f"prop_{idx+1:02d}_{item.width}x{item.height}.png"
        path = props_dir / name
        item.save(path)
        prop_paths.append({
            "id": idx + 1,
            "file": str(path.relative_to(output_dir)),
            "width": item.width,
            "height": item.height
        })
        
    return {
        "count": len(prop_paths),
        "props": prop_paths
    }


def extract_platforms(img, output_dir):
    """
    Trích xuất các khối bục bay / platform modules ở góc trên bên phải
    """
    plat_dir = output_dir / "platforms"
    plat_dir.mkdir(parents=True, exist_ok=True)
    
    # Khu vực bục đá bay: x từ 315 đến 1024, y từ 0 đến 275
    crop_region = img.crop((315, 0, 1024, 275)).convert("RGBA")
    clean_region = remove_dark_background(crop_region, threshold=24)
    
    arr = np.array(clean_region)
    mask = arr[:, :, 3] > 0
    
    boxes = find_components_boxes(mask, min_w=18, min_h=16, pad=3)
    boxes.sort(key=lambda b: (b[1] // 40, b[0]))
    
    plat_paths = []
    for idx, (x1, y1, x2, y2) in enumerate(boxes):
        item = clean_region.crop((x1, y1, x2, y2))
        name = f"platform_{idx+1:02d}_{item.width}x{item.height}.png"
        path = plat_dir / name
        item.save(path)
        plat_paths.append({
            "id": idx + 1,
            "file": str(path.relative_to(output_dir)),
            "width": item.width,
            "height": item.height
        })
        
    return {
        "count": len(plat_paths),
        "platforms": plat_paths
    }


def extract_parallax(img, output_dir):
    """
    Trích xuất các dải nền Parallax (bầu trời, núi xa, rừng trúc sương mù, thác nước)
    """
    para_dir = output_dir / "parallax"
    para_dir.mkdir(parents=True, exist_ok=True)
    
    layers = []
    # Khu vực đáy: y từ 475 đến 682
    # Lớp 1: Bầu trời & mây cuộn (trái)
    sky = img.crop((0, 475, 570, 640))
    sky_path = para_dir / "layer_01_sky_clouds.png"
    sky.save(sky_path)
    layers.append({"name": "Sky & Clouds", "file": str(sky_path.relative_to(output_dir)), "size": sky.size})
    
    # Lớp 2: Rừng trúc & Sương mù / Thác nước (phải)
    forest = img.crop((570, 475, 1024, 640))
    forest_path = para_dir / "layer_02_forest_waterfall.png"
    forest.save(forest_path)
    layers.append({"name": "Forest & Waterfall", "file": str(forest_path.relative_to(output_dir)), "size": forest.size})
    
    # Lớp 3: Dải nước & hoa sen
    water = img.crop((570, 640, 1024, 682))
    water_path = para_dir / "layer_03_water_lotus.png"
    water.save(water_path)
    layers.append({"name": "Water & Lotus", "file": str(water_path.relative_to(output_dir)), "size": water.size})
    
    return {
        "count": len(layers),
        "layers": layers
    }


def process_asset_sheet(input_image_path, output_dir=None):
    """
    Xử lý toàn bộ asset sheet và xuất ra đầy đủ các thành phần
    """
    input_path = Path(input_image_path)
    if not input_path.exists():
        raise FileNotFoundError(f"Không tìm thấy file ảnh: {input_image_path}")
        
    if output_dir is None:
        output_dir = input_path.parent / (input_path.stem + "_extracted")
    else:
        output_dir = Path(output_dir)
        
    output_dir.mkdir(parents=True, exist_ok=True)
    
    img = Image.open(input_path)
    print(f"Đang xử lý ảnh: {input_path.name} ({img.size[0]}x{img.size[1]} px)...")
    
    # 1. Trích xuất Tileset 64x64
    print("- Trích xuất lưới tileset 64x64...")
    tileset_data = extract_tileset(img, output_dir)
    
    # 2. Trích xuất Platforms
    print("- Trích xuất khối platform module...")
    plat_data = extract_platforms(img, output_dir)
    
    # 3. Trích xuất Props
    print("- Trích xuất vật thể trang trí (Props) và khử phông trong suốt...")
    props_data = extract_props(img, output_dir)
    
    # 4. Trích xuất Parallax
    print("- Trích xuất dải nền Parallax...")
    para_data = extract_parallax(img, output_dir)
    
    manifest = {
        "source": input_path.name,
        "tileSize": [64, 64],
        "tileset": tileset_data,
        "platforms": plat_data,
        "props": props_data,
        "parallax": para_data
    }
    
    manifest_path = output_dir / "manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
        
    print(f"\n HOÀN TẤT!")
    print(f"Tổng cộng:")
    print(f"  • {tileset_data['count']} ô Tileset chuẩn 64x64 + 1 Atlas hoàn chỉnh")
    print(f"  • {plat_data['count']} khối Platform module bục đá trong suốt")
    print(f"  • {props_data['count']} vật thể Props (cổng miếu, cây đào, trúc, cầu...) trong suốt")
    print(f"  • {para_data['count']} dải nền Parallax")
    print(f"  • File thông tin: {manifest_path}")
    return manifest


if __name__ == "__main__":
    if len(sys.argv) > 1:
        img_path = sys.argv[1]
        out = sys.argv[2] if len(sys.argv) > 2 else None
        process_asset_sheet(img_path, out)
    else:
        print("Sử dụng: python tools/map_asset_extractor.py <đường_dẫn_ảnh_sheet>")
