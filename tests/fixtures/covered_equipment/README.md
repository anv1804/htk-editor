# Covered equipment regressions

Four 256×448 source sheets supplied locally by the user for the September 27
glove/boot regression. Layout: 4 columns × 7 rows, aligned with
`../hair_outfit/base.png`.

- `leather-gloves-boots.png`: cream/green tunic, brown gloves and boots.
- `dark-armor.png`: brown/dark armor, gloves and boots.
- `embroidered-robe.png`: purple robe with warm embroidery and covered legs.
- `gold-robe.png`: gold robe, used as a warm-material negative control.

The first frame's glove/boot interiors and torso are intentionally annotated
in `test_covered_equipment.py`. They must remain outfit regardless of bare
skin at the same positions in the base. Existing cream/green/hair fixtures
provide the complementary exposed-hand tests.
