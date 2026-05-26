#!/usr/bin/env python3
"""Run the fuse-beads pipeline on a specific image."""

from beads import load_image, resize_to_beads, match_bead_colors, build_beads_image

# config
INPUT = "Hornet.png"
OUTPUT = "Hornet_beads.png"
N_COLORS = 8
WIDTH = 100
BEAD_SIZE = 5
GRID = 1

img = load_image(INPUT)
print(f"Loaded: {INPUT} ({img.width}x{img.height})")

small = resize_to_beads(img, WIDTH, None)
print(f"Bead grid: {small.width}x{small.height}")

quantized, palette_hex = match_bead_colors(small, N_COLORS)
print(f"Matched to {len(palette_hex)} real bead colors:")
for i, h in enumerate(palette_hex):
    rgb = tuple(int(h[j:j+2], 16) for j in (1, 3, 5))
    print(f"  #{i+1}: {h}  rgb({rgb[0]}, {rgb[1]}, {rgb[2]})")

result = build_beads_image(quantized, palette_hex, BEAD_SIZE, GRID)
result.save(OUTPUT)
print(f"Saved: {OUTPUT}  ({result.width}x{result.height})")
