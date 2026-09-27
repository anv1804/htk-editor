# Outfit over base

The default browser/CLI workflow now stacks the cleaned outfit over the base.
Skin-colored openings on the outfit are cut out using color and proximity to
base flesh, including bare feet. Garment pixels retain priority over the base.
The base palette and native pixel positions remain unchanged where revealed.

Skin removal also samples the outfit's face palette before compositing. This
cuts differently shaded source hands without moving the base palms. Free dark
skin rims are removed while rims shared with fabric stay as cuff seams. Blue
sleeves with cream trim do not trigger whole-body tan-fabric protection. The
outline pass normalizes dark fabric-side cuff/collar joins without drawing over
base anatomy. Warm clothing protection begins below the chin.

Before recoloring, the outline pass repairs redundant inner dark strokes one
or two pixels from a continuous parallel outer contour. It requires a run of
at least three pixels and brighter inward fabric to sample. It never changes
alpha or base pixels, crosses transparent gaps, or samples another frame.
Broad dark panels and perpendicular fold lines remain intact. Ambiguous
decorative parallel seams may still need a manual color correction.

Cuffs and collars share the base's existing dark boundary rather than gaining
a second cloth-side stroke. Missing boundaries are drawn on the cloth side.
Internal shading is kept at source tones, rather than automatically promoted
to ink or skeletonized. Removed duplicate ink is repainted from nearby fabric,
never from skin. The original base and
manual colors remain locked; this cannot thin a thick stroke already in base.
Use outline enabled, paint 3 and 32 colors for the default repair workflow.

Use **Xoa outfit de lo base** on the result canvas to cut more of the top layer.
It previews the original base at the same coordinates while brushing. An empty
base pixel is transparent; the tool does not invent a hand there. **Giu outfit**
restores an outfit pixel, while **Xoa** erases both layers. Apply with **Xu ly
sprite**, then export the composite or the separate transparent outfit layer.
The separate outfit export excludes base anatomy and headwear; manual outfit
retouches are included. Color fitting and layer extraction use the same result.

The default repaint uses the full remaining palette budget and supports more
than two materials. It adds neither dithering nor forced contrast. Skin cuts
do not fill across enclosed colored fabric details, including dark green/blue
pixels that would otherwise be mistaken for a hand's dark rim.

Toe/heel cleanup uses competing distances to exposed skin and material anchors
within the source foreground. It only removes neutral fringe within two pixels
outside the base foot and near confirmed bare skin. Covered boots are excluded.
Between-leg cleanup requires exposed skin on both sides; a material strip that
continues to the foot line is retained as a long hem/ribbon. Short crotch bridges
are removed. This is a geometric estimate, not semantic recognition of every
garment: short hanging panels or skin-colored cloth may need keep-outfit marks.

Automatic color classification cannot reliably distinguish skin from flesh-tone
cloth in every asset. Keep-outfit corrections are authoritative. Misaligned poses
may still require trimming the top layer or erasing unwanted base protrusions.

The previous pinned-profile compositor remains available through the composition
menu or `--composition pinned`. It is not used to force hands through sleeves in
the new `--composition layers` workflow.
# Workflow preserving the source garment

The studio defaults to `composition=cutout`: the outfit stays above the base;
detected source skin is removed to reveal exact base pixels. Unlike `layers`,
this mode does not infer an empty crotch from the base silhouette, remove colored
spurs, or repaint every skin/fabric junction black. Short hanging panels are
preserved too. Headwear protection and explicit manual masks remain authoritative.

Body skin cuts must now have evidence from the source face palette. Similarity
to the base skin palette alone cannot start a body aperture. A competing source
cloth palette protects connected warm shadows when they fit fabric better than
flesh; ambiguous warm fabric is retained. This veto only applies in cutout mode,
and does not change the legacy layers or pinned workflows. Exact skin-colored
cloth is still ambiguous and must be resolved with manual keep/reveal masks.
The nude base is a pose reference, not proof of source skin exposure. Source
fabric evidence takes priority even directly over base skin. Apertures are
recomputed after this veto, preventing false seeds inside cream folds from
expanding into nearby cloth and exposing the base's dark outlines. Actual palms
still use their separate source-face-color and palm-geometry recovery pass.
The cream robe regression covers these pixels in the full sheet and verifies
both composite colors and standalone outfit ownership.

The crisp repaint mode limits tonal adjustment to eight luminance levels before
fitting to the source palette. It cannot aggressively darken midtones simply
because most of the frame is bright cloth. Session restoration preserves the
chosen repaint mode and outline toggle without silently upgrading either.

The face reference includes source jaw shadows as well as bright skin. Below
the chin, neutral fringe cleanup and the legacy expanded face cut cannot erase
collar highlights without source skin evidence. After palette fitting, isolated
near-color dots can join a supported neighboring color; connected dark seams,
locked anatomy and frame boundaries are protected. The cream/green robe is now
a checked-in regression input covering neck, collar and palm ownership.

Outline repair is optional. In cutout mode it traces the supported outer mask
boundary, including bright hems and soles, and continuous existing dark seam valleys, leaving bright collar joins
and thin colored ribbons intact. It never grows the silhouette or edits base
pixels. Supported redundant dark strokes immediately inside the border are
recolored from neighboring fabric; more distant folds remain intact.
Detached one/two-pixel fragments touching a skin cut are removed unless
explicitly protected. Color reduction is a separate operation. This is
not semantic reconstruction: skin-colored fabric, uncertain openings and source
misalignment still require review with Reveal base / Keep fabric / Paint tools.

The editor groups source inputs, processing settings, mask review and exports;
side panels become drawers below 850px. Existing masks and paint layers remain
editable and reusable. Preview updates even while playback is paused.

Palm recovery is bounded to the actual base palm, never its expanded cuff
neighborhood. New skin seeds must also match the source face palette; a warm
hue alone cannot override a fabric label. The frame-2 cream robe cuffs have
explicit regression checks on both their pale cloth and dark green rims.

Studio tools now include frame-bounded connected fill (G): restore source
fabric, reveal base, paint a color or erase transparency. The operation is
undoable and compares pixels with the original seed rather than progressively
following a gradient. Result-only and outfit-layer views make the cutout
inspectable. Project JSON embeds both source images, masks, retouch layer,
optional base profile, settings and selected frame. Loading validates all
images and settings before replacing the current inputs. Projects regenerate
the result using the current processor instead of embedding a stale export.
Color presets explicitly distinguish preserving source colors from reducing
them to 32/64 colors; repainting controls are disabled in preserve-color mode.

Paint mode 4, **Sharp color redraw**, is the default palette-limited finish.
Within each frame it modestly separates existing light and shadow values and
adds a small chroma lift, then maps pixels to the outfit palette under the
selected color budget. Flat cloth is skipped. It does not resample, blur, dither,
or change the alpha silhouette; base pixels, outer ink and hand-painted pixels
stay locked. Paint mode 3 remains available to preserve the original shading.
