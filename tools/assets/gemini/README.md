# Gemini visible logo calibration masks

Vendored from [PlayerYK/GeminiWatermarkRemover](https://github.com/PlayerYK/GeminiWatermarkRemover/tree/584efb45a16b9774237a0d3ebfd6222b1b8c1888), revision `584efb45a16b9774237a0d3ebfd6222b1b8c1888`.

The original reverse-alpha mask work is credited to [Allen Kuo / allenk, GeminiWatermarkTool](https://github.com/allenk/GeminiWatermarkTool). Full MIT notices are included in `LICENSE` and `LICENSE.allenk`. Only calibration data is vendored; no external application is executed or contacted at runtime.

- `bg_48.png`, `bg_96.png`: legacy alpha captures (maximum RGB / 255).
- `bg_96_20260520.png`: newer large-margin capture.
- `bg_36_v2.bin`: 36 × 36 little-endian float32 alpha capture.

Detection and guarded restoration are implemented locally in `tools/gemini_logo.py`. The visible logo is restored before sprite segmentation; image alpha and dimensions stay unchanged.
