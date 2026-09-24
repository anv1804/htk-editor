# Character pixel style reference

Reference: `assets/references/meowa-character-2x2.png` (four distinct characters, each in a 64x64 cell). This is a visual benchmark, not a sheet of animation frames or a template to copy literally.

## Measured properties

- Canvas: 64x64 per character; transparent background with binary alpha.
- Visible bounding boxes inside the four cells, left-to-right then top-to-bottom: (23,2)-(40,61), (19,2)-(44,60), (13,3)-(44,61), (20,3)-(44,61). The third includes a held prop; body width is narrower.
- Feet are near y=59-60. Tall silhouettes occupy nearly all available height while keeping 2-3 pixels of top and bottom air.
- The file contains many RGB shades (1808 nontransparent RGBA values across the sheet). Do not assert that this reference uses a 24- or 32-color palette. Its visible pixel edges and silhouette are more important than a strict color count.

## Drawing rules observed at native scale

1. **Silhouette and proportions.** Upright cartoon bodies with a slightly enlarged head, but not a huge chibi head. Hair/head is approximately a quarter to a third of the visible height. Shoulders and torso are narrow; long, separate legs and small feet keep the pose readable.
2. **Outline.** A mostly one-pixel dark contour, with hue-shifted dark brown, blue, or green depending on the material. It is interrupted where a light edge or an overlapping limb reads better. Corners and hair curves step gradually across pixels; avoid thick square stair blocks and a uniform black border.
3. **Face.** Broad uninterrupted skin area. Eyes are tiny dark vertical marks (roughly 1x2 pixels at native size), separated by several skin pixels. Brows/upper lids and hairline carry expression. Nose and mouth are absent or a single very quiet pixel; do not add detailed lips or large anime eyes.
4. **Hands and arms.** Hands are tiny warm skin clusters at the ends of sleeves, clearly separated from torso color. Arms have recognizable elbows/sleeve overlap, but no individually drawn fingers at this resolution.
5. **Legs and feet.** Two distinct leg columns or a clear dark gap between them. Shoes are low, horizontal clusters; ground contact shares one baseline. Avoid merging the robe/trousers/boots into a single dark column.
6. **Color.** Each garment reads first as a solid midtone region, then receives compact shadow and highlight clusters. Local material colors remain separate: skin versus hair versus inner cloth versus outer cloth versus footwear. Shade transitions may use several nearby colors, but edges stay pixel sharp and alpha stays binary.
7. **Detail budget.** Distinctive accessories use a few pixels in the hair, collar, belt, or hems. Large pattern/noise fields are not what makes these sprites readable. The face, hand and foot clusters deserve priority over decoration.

## Standard for this project's xianxia characters

- Draw a native 64x64 master first. Use a side-scroller 3/4 standing pose facing right; horizontal flip supplies left. This reference mostly shows front or 3/4 poses, so it does not by itself prove how a strict side-running pose should look.
- Keep feet near y=59-60, head/hair below the top edge, and the body centered. A robe may widen the lower silhouette, but the legs or footwear must remain distinguishable.
- At 100% and 400% nearest-neighbor preview, the two eyes, each hand, robe layers, and both feet must be recognizable without relying on blur or antialiasing.
- Preserve facial pixel placements and identity markers across animation frames. Animate sleeves, hair tips, torso compression and pose; do not redraw the face differently per frame.
- Review visual quality before accepting a sprite. Dimensions, alpha, palette count and anchor checks are necessary file checks, not evidence of good drawing.
