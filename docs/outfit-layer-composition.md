# Outfit over base

The default browser/CLI workflow now stacks the cleaned outfit over the base.
Skin-colored openings on the outfit are cut out using color and proximity to
base flesh, including bare feet. Garment pixels retain priority over the base.
The base palette and native pixel positions remain unchanged where revealed.

Use **Xoa outfit de lo base** on the result canvas to cut more of the top layer.
It previews the original base at the same coordinates while brushing. An empty
base pixel is transparent; the tool does not invent a hand there. **Giu outfit**
restores an outfit pixel, while **Xoa** erases both layers. Apply with **Xu ly
sprite**, then export the composite or the separate transparent outfit layer.
The separate outfit export excludes base anatomy and the manual retouch layer.

Automatic color classification cannot reliably distinguish skin from flesh-tone
cloth in every asset. Keep-outfit corrections are authoritative. Misaligned poses
may still require trimming the top layer or erasing unwanted base protrusions.

The previous pinned-profile compositor remains available through the composition
menu or `--composition pinned`. It is not used to force hands through sleeves in
the new `--composition layers` workflow.
