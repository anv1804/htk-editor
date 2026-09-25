# Reviewed Base Regions

`chibi-4x7.json` records frame-local rectangular selections made from the supplied
256 x 448 base. It is used only when the RGBA pixel hash, image dimensions and
grid match its `baseId`. Another base uses the automatic profile until edited.

Each rectangle is `[left, top, right, bottom]`, with right/bottom exclusive.
All foreground pixels inside it are selected, including dark square outlines
and highlights. Multiple rectangles can describe a head/chin or two palms.
Only visible hands are annotated; bent legs and feet are excluded.

The browser's **Khoanh khung đầu** replaces the current frame's head selection;
**Khoanh khung bàn tay** adds a palm. **Xóa vùng base trong khung** and
**Xóa đầu/tay frame** remove mistaken selections. Undo and exported base profile
JSON preserve the selected pixels. Selection never rescales the base.

Profiles stored by older automatic detectors remain in browser storage. The
reviewed-region workflow uses a new cache namespace so those masks do not
silently replace the new defaults. Explicitly loading an older exported mask
still applies that mask as an artist override.

The same pixel color can belong to a hand or a leg. These reviewed selections
are specific to this base and are editable, not a general pose detector.
