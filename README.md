# HKT Pixel Forge

HKT Pixel Forge is a native-pixel character and animation asset compiler for a 64x64 side-scrolling xianxia MMORPG.

The current project standard is four 64x64 frames per action. New characters have no automatic color cap; use `--colors N` only when the game's actual renderer requires one. Existing character contracts keep their saved settings.

It deliberately separates generation from production validation. A model or artist creates one native-size master sprite and action poses. Pixel Forge preserves those pixels, prepares motion canvases, validates animation frames, and emits engine-ready sheets and previews.

## Why this exists

General image models often simulate pixel art at a large resolution. Downscaling those images produces blended colors, unstable outlines, and fake pixel clusters. Pixel Forge therefore rejects the large-image-to-small-sprite workflow:

```text
native 64x64 master
  -> approved identity and palette
  -> action-ready first pose
  -> transparent padding without resampling
  -> animation backend or authored keyframes
  -> technical QC + nearest-neighbor visual review
  -> lossless spritesheet + GIF preview + final_outputs.json
  -> human approval tied to exact frame hashes for release
```

The generation backend is intentionally replaceable. Meowa's hosted models are proprietary and are not copied here.

`tools/grid_aware_pixel_reduce.py` is retained for experiments and comparison. Its output is not an approved native pixel master merely because it has 64x64 dimensions. The previous `ivory-jade-novice` asset remains a visual-review candidate. A production character must be drawn or corrected at native pixel scale and pass the visual checks in [the style reference](docs/character-pixel-style-reference.md).

## Codex CLI backend

Codex CLI can run as a bounded agent backend. It receives the approved master image and immutable contracts, may use the image/sprite skills available in that Codex environment, writes only the requested frame directory, and must run Pixel Forge QC before returning.

Inspect a job without spending model usage:

```bash
PYTHONPATH=src python3 -m hkt_pixel_forge codex-run \
  --character work/jade-novice/character.json \
  --action-contract work/jade-novice/actions/idle/action.json \
  --output work/jade-novice/actions/idle/codex-output \
  --dry-run
```

Run it:

```bash
PYTHONPATH=src python3 -m hkt_pixel_forge codex-run \
  --character work/jade-novice/character.json \
  --action-contract work/jade-novice/actions/idle/action.json \
  --output work/jade-novice/actions/idle/codex-output
```

This uses `codex exec --ephemeral` with `workspace-write`, approval policy `never`, an attached master image, and a strict JSON output schema. It never enables the dangerous sandbox bypass. Codex returns a **candidate** with a review board, not an approved game asset. Visual quality still depends on the image or animation capability available to that CLI session.

## Commands

Run from the repository without installation:

```bash
PYTHONPATH=src python3 -m hkt_pixel_forge --help
```

Repair an outfit sheet against a clean base sheet when generated clothes smear
skin, hands, or eyes. The output keeps the outfit, restores anatomy pixels from
the base, removes soft alpha/background, and optionally snaps the sheet to a
small palette:

```bash
python3 tools/repair_outfit_sprite.py \
  --base base.png \
  --outfit outfit.png \
  --output repaired-outfit.png \
  --rows 7 \
  --cols 4 \
  --colors 32 \
  --paint 1 \
  --report repair-report.json
```

### Local UI

Run the browser interface with:

```bash
python3 tools/repair_outfit_ui.py
```

The tool opens `http://127.0.0.1:8765`. Drop the clean base sheet and outfit
sheet into the two input areas, adjust the grid if needed, then process and
download the repaired transparent PNG.

Install the standalone repair dependencies with `python -m pip install Pillow numpy`.
Open the HTTP address above, not the HTML file directly: image processing runs
in the local Python server.

The repair pipeline removes the background and small detached debris, replaces
the generated head and detected hands with exact base pixels, then repaints
the clothing using a shared sheet palette. A one-pixel inward outline uses
the base's dark outline color. Clothing stays above the body; restoring a
hand does not copy the whole bare arm over a sleeve. Base anatomy colors are
locked even when reducing the palette. `--colors 0` disables recoloring;
`--paint 0/1/2` selects palette-only, up to 12 cloth colors, or up to 6 cloth
colors (subject to the total color limit). `--no-outline` preserves the source
contour; `--cleanup 0` keeps small detached details.

Use the frame comparison at 4×/6×/8× to inspect the result. The input sheets
must have matching dimensions and aligned poses. Skin-colored fabric and
overlapping hands can be ambiguous, so the UI includes correction brushes:
red takes the base, blue keeps the outfit, green erases, and transparent
returns to automatic processing. Paint on the result frame and process again.
Undo, save/load correction masks, and a per-frame JSON report are available.
Saved masks can also be used with `--overrides outfit-corrections.png`.
Sources and corrections survive reloads within the browser session when
session storage has enough space.

Sleeves and collars now occlude base anatomy, including sleeves raised in
front of the face. Hand replacement is clipped to the outfit's exposed-skin
opening, without dilation into the sleeve. Small missing wrist/neck areas
are completed from nearby base skin pixels; this is local pixel reconstruction,
not generation of a new garment or a new pose. Existing colored thin tips
and ribbons are retained during matte cleanup and outline normalization.
The mask view distinguishes exact base pixels (red), clothing (blue), and
reconstructed skin (yellow). Reports include those reconstruction counts.

The UI and CLI now default to a reusable base anatomy profile. The initial
head/palm regions are estimated from the base alone, rather than following
skin shapes in each generated outfit. Edit head (red) and palms (orange) on
the base canvas, including erasing false selections. A selected palm keeps
the base's original coordinates and pixels; only that small palm region can
open a cuff, while the rest of the arm stays behind clothing. Obsolete outfit
hand openings are filled from nearby sleeve material. Check and correct the
automatic proposal once, especially for crossed arms or hands behind the head.

Profiles are saved in browser local storage under the base pixel/grid identity,
and can be exported/imported as `base-anatomy.json`. Loading one for a different
base or grid is rejected. CLI: `--base-profile base-anatomy.json` (RGBA mask PNG
is also supported); `--free-skin` selects the older outfit-guided behavior.
The Python `repair_sheet` API retains its old default for compatibility; pass
`lock_base=True` or `base_profile=...` to use fixed anatomy.

`--paint 3` (the new UI/CLI default) separates two fabric color families and
repaints shadow, midtone and highlight regions with shared ramps. It preserves
the silhouette and uses source lighting rather than inventing new folds.
Connected dark belt, cuff and fold lines are preserved before recoloring.
Tone levels follow the source light distribution, so nearly flat fabric does
not gain exaggerated shadow patches and cream/blue shades retain their hue.
Other paint modes remain available. The UI also has direct color painting,
an eyedropper that ignores mask overlays, and a separate PNG retouch layer
(`--retouch outfit-retouch.png`). Hand-painted colors are locked during
repainting and count toward the selected total palette budget. Undo works
for region, profile and color edits. Mask opacity affects the inspection
overlay only and never the exported sprite.

Register an approved native sprite:

```bash
PYTHONPATH=src python3 -m hkt_pixel_forge character-init \
  --character-id jade-novice \
  --master assets/characters/jade-novice/idle-final/idle-1.png \
  --colors 0 \
  --anchor-y 59 \
  --output work/jade-novice
```

Inspect the recommended animation contract:

```bash
PYTHONPATH=src python3 -m hkt_pixel_forge plan \
  --character work/jade-novice/character.json \
  --action idle
```

Prepare an action source. This changes only canvas dimensions; source pixels are copied exactly:

```bash
PYTHONPATH=src python3 -m hkt_pixel_forge prepare \
  --character work/jade-novice/character.json \
  --action idle \
  --source work/jade-novice/master.png \
  --output work/jade-novice/actions/idle
```

Validate generated or authored frames:

First ingest an animation backend's exact output. The command refuses the wrong frame count or canvas size and records a SHA-256 hash for every unchanged frame:

```bash
PYTHONPATH=src python3 -m hkt_pixel_forge ingest \
  --action-contract work/jade-novice/actions/idle/action.json \
  --frames 'provider-output/*.png' \
  --provider my-animation-backend \
  --output work/jade-novice/actions/idle/frames
```

Then validate generated or authored frames:

```bash
PYTHONPATH=src python3 -m hkt_pixel_forge validate \
  --character work/jade-novice/character.json \
  --action-contract work/jade-novice/actions/idle/action.json \
  --frames 'work/jade-novice/actions/idle/frames/*.png' \
  --output work/jade-novice/actions/idle/qc.json
```

Build only after QC passes:

```bash
PYTHONPATH=src python3 -m hkt_pixel_forge build \
  --character work/jade-novice/character.json \
  --action-contract work/jade-novice/actions/idle/action.json \
  --frames 'work/jade-novice/actions/idle/frames/*.png' \
  --columns 4 \
  --output builds/jade-novice/idle
```

The build is a candidate. The PNG sheet is lossless: it uses indexed mode only if all opaque colors fit exactly; otherwise it stays RGBA. `preview.gif` may be limited by GIF color rules and is for inspection only. The build also writes `review-board.png` at 4x nearest-neighbor scale.

For a releasable sheet, inspect the board and animation, then record explicit visual checks:

```bash
PYTHONPATH=src python3 -m hkt_pixel_forge review \
  --frames 'work/jade-novice/actions/idle/frames/*.png' \
  --output builds/jade-novice/idle/review-board.png

PYTHONPATH=src python3 -m hkt_pixel_forge approve \
  --frames 'work/jade-novice/actions/idle/frames/*.png' \
  --output builds/jade-novice/idle/visual-review.json \
  --reviewer 'artist-name' \
  --check face --check hands --check feet --check outline --check identity --check motion

PYTHONPATH=src python3 -m hkt_pixel_forge build \
  --character work/jade-novice/character.json \
  --action-contract work/jade-novice/actions/idle/action.json \
  --frames 'work/jade-novice/actions/idle/frames/*.png' \
  --output builds/jade-novice/idle \
  --release --review-record builds/jade-novice/idle/visual-review.json
```

The approval is invalidated if any source frame changes. See [pixel style reference](docs/character-pixel-style-reference.md) for what to inspect. Technical QC alone does not assess drawing quality.

## Backend boundary

Pixel Forge currently accepts native PNG frames from an artist, an image model, or an animation service. A backend must obey these contracts:

- preserve canvas dimensions;
- preserve native hard pixel edges;
- preserve the master identity and palette;
- return PNG frames with sharp alpha;
- keep declared anchors and padding;
- never silently resize the source.

See [Meowa research](docs/meowa-research.md) for the public workflow analysis behind these rules.
