"""Fuse beads image converter.

Converts an image into a fuse-beads (拼豆) style output:
- Maps pixels to the nearest real fuse-bead color from a fixed palette
- Draws bead grid with divider lines and numbered cells
- Appends a color legend with #RRGGBB swatch codes
"""

import numpy as np
from PIL import Image, ImageDraw, ImageFont

# ── Real fuse-bead color palette ────────────────────────────────────────────
# Hex values based on Perler / Hama / Artkal common bead colors.

FUSE_BEAD_PALETTE = [
    # Whites / Creams / Neutrals
    "#FEFEFE",  # White
    "#FFFDD0",  # Cream
    "#F5E6D3",  # Sand
    "#F5DEB3",  # Wheat
    # Browns / Tans
    "#D2B48C",  # Tan
    "#CDAA7D",  # Light Brown
    "#A67C52",  # Gingerbread
    "#8B5E3C",  # Brown
    "#5C3A21",  # Dark Brown
    "#3E2723",  # Chocolate
    # Greys / Silvers
    "#D3D3D3",  # Light Grey
    "#C0C0C0",  # Silver
    "#A9A9A9",  # Grey
    "#808080",  # Dark Grey
    "#58595B",  # Charcoal
    "#404040",  # Pewter
    # Reds / Pinks
    "#FFB6C1",  # Light Pink
    "#FF9AAE",  # Pink
    "#FF69B4",  # Hot Pink
    "#E75480",  # Dark Pink
    "#FF1493",  # Magenta
    "#C71585",  # Raspberry
    "#E23D28",  # Red
    "#DC143C",  # Crimson
    "#BE0032",  # Cherry
    "#A9203E",  # Cranberry
    "#800020",  # Burgundy
    "#CC3333",  # Rust
    # Oranges / Peaches
    "#FFDAB9",  # Peach
    "#FFCBA4",  # Light Peach
    "#FFB347",  # Butterscotch
    "#FF8C00",  # Orange
    "#FF5E00",  # Neon Orange
    "#FF6719",  # Tangerine
    # Yellows
    "#FFFACD",  # Pastel Yellow
    "#FFF44F",  # Lemon
    "#FFD700",  # Yellow
    "#FDDC01",  # Cheddar
    "#E8A600",  # Honey
    # Greens
    "#B5EAD7",  # Mint
    "#90EE90",  # Light Green
    "#A9D155",  # Prickly Pear
    "#C1D82F",  # Lime
    "#8BC34A",  # Kiwi
    "#32CD32",  # Bright Green
    "#228B22",  # Green
    "#009E60",  # Shamrock
    "#006400",  # Dark Green
    "#1B4D3E",  # Evergreen
    # Teals / Turquoises
    "#7ED0C4",  # Toothpaste
    "#48D1CC",  # Turquoise
    "#20B2AA",  # Light Teal
    "#008080",  # Teal
    "#006D6F",  # Dark Teal
    # Blues
    "#B3D9FF",  # Pastel Blue
    "#ADD8E6",  # Light Blue
    "#87CEEB",  # Sky Blue
    "#5DADE2",  # Robin's Egg
    "#1E90FF",  # Blue
    "#4169E1",  # Royal Blue
    "#0059B3",  # Cobalt
    "#000080",  # Dark Blue
    "#002A6E",  # Midnight
    # Purples / Lavenders
    "#E6E6FA",  # Lavender
    "#D8BFD8",  # Thistle
    "#C792C1",  # Pastel Lavender
    "#9B7FBD",  # Light Purple
    "#800080",  # Purple
    "#6C3A8B",  # Dark Purple
    "#4A2060",  # Plum
    # Blacks
    "#1A1A1A",  # Black
]


def hex_to_rgb(hex_color):
    """Convert '#RRGGBB' to (R, G, B)."""
    h = hex_color.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


# ── Pipeline functions ──────────────────────────────────────────────────────


def load_image(path):
    img = Image.open(path).convert("RGB")
    return img


def resize_to_beads(img, width, height):
    """Resize image to target bead dimensions, keeping aspect ratio."""
    if width and height:
        return img.resize((width, height), Image.LANCZOS)
    if width:
        ratio = width / img.width
        height = max(1, round(img.height * ratio))
        return img.resize((width, height), Image.LANCZOS)
    if height:
        ratio = height / img.height
        width = max(1, round(img.width * ratio))
        return img.resize((width, height), Image.LANCZOS)
    raise ValueError("Must specify at least --width or --height")


def _kmeans_pixels(pixels, k, max_iter=30):
    """Lloyd's k-means on (N, 3) pixel data — pure numpy, zero extra deps."""
    n = pixels.shape[0]
    # pick k initial centroids evenly spaced across the data
    step = max(1, n // k)
    centroids = pixels[::step][:k].astype(np.float64).copy()
    labels = np.zeros(n, dtype=np.int32)

    for _ in range(max_iter):
        diff = pixels[:, np.newaxis, :] - centroids[np.newaxis, :, :]
        new_labels = np.argmin(np.sum(diff ** 2, axis=2), axis=1)
        if np.array_equal(labels, new_labels):
            break
        labels = new_labels
        for j in range(k):
            mask = labels == j
            if mask.any():
                centroids[j] = pixels[mask].mean(axis=0)

    return centroids


def match_bead_colors(img, n_colors=None):
    """Map every pixel to the nearest real fuse-bead color.

    Uses a fixed palette of 70+ authentic bead colors.  When *n_colors* is
    set, k-means first finds the best *n_colors* cluster-centres for the
    image, then each centre is snapped to the closest real bead colour so
    every colour in the output corresponds to a bead you can actually buy.

    Returns ``(quantized_pil_image, hex_palette)`` where *hex_palette* is a
    list of ``#RRGGBB`` strings.
    """
    palette_rgb = np.array(
        [hex_to_rgb(h) for h in FUSE_BEAD_PALETTE], dtype=np.float64
    )
    palette_hex = list(FUSE_BEAD_PALETTE)
    pixels = np.array(img, dtype=np.float64).reshape(-1, 3)

    if n_colors is None:
        # direct nearest-neighbour — every pixel gets its closest bead colour
        diff = pixels[:, np.newaxis, :] - palette_rgb[np.newaxis, :, :]
        distances = np.sqrt(np.sum(diff ** 2, axis=2))
        nearest_idx = np.argmin(distances, axis=1)

        quantized_rgb = palette_rgb
        local_to_global = {i: i for i in range(len(palette_rgb))}
    else:
        # k-means → snap centroids → re-map pixels
        centers = _kmeans_pixels(pixels, n_colors)

        # snap each k-means centre to the nearest real bead colour (dedup)
        diff = centers[:, np.newaxis, :] - palette_rgb[np.newaxis, :, :]
        distances = np.sqrt(np.sum(diff ** 2, axis=2))
        global_idx = np.unique(np.argmin(distances, axis=1))

        quantized_rgb = palette_rgb[global_idx]
        local_to_global = {i: int(global_idx[i]) for i in range(len(global_idx))}

        # assign every pixel to the nearest snapped colour
        diff = pixels[:, np.newaxis, :] - quantized_rgb[np.newaxis, :, :]
        distances = np.sqrt(np.sum(diff ** 2, axis=2))
        nearest_idx = np.argmin(distances, axis=1)

    quantized = quantized_rgb[nearest_idx].astype(np.uint8).reshape(
        img.height, img.width, 3
    )

    # palette of actually-used colours, in original declaration order
    used_global = sorted({local_to_global[int(i)] for i in np.unique(nearest_idx)})
    used_hex = [palette_hex[g] for g in used_global]

    return Image.fromarray(quantized), used_hex


def build_beads_image(quantized_img, palette_hex, bead_size, grid,
                      show_numbers=True):
    """Render the quantized image as a fuse-bead canvas + numbered legend.

    *palette_hex* is a list of ``#RRGGBB`` strings (from
    :func:`match_bead_colors`).  When *show_numbers* is True each bead cell
    is labelled with its colour index so you can read exactly which bead
    goes where without colour-matching.
    """
    w, h = quantized_img.size
    canvas_w = w * (bead_size + grid) + grid
    canvas_h = h * (bead_size + grid) + grid

    grid_color = (60, 60, 60)
    canvas = Image.new("RGB", (canvas_w, canvas_h), grid_color)
    pixels = quantized_img.load()

    # RGB tuple → (0-based index, hex string)
    rgb_to_info = {
        hex_to_rgb(hex_color): (i, hex_color)
        for i, hex_color in enumerate(palette_hex)
    }

    font = None
    if show_numbers and bead_size >= 8:
        font_size = max(8, int(bead_size * 0.55))
        try:
            font = ImageFont.truetype(
                "/System/Library/Fonts/Helvetica.ttc", font_size,
            )
        except (IOError, OSError):
            font = ImageFont.load_default()

    draw = ImageDraw.Draw(canvas) if font else None

    for y in range(h):
        for x in range(w):
            x0 = grid + x * (bead_size + grid)
            y0 = grid + y * (bead_size + grid)
            r, g, b = pixels[x, y]
            for dy in range(bead_size):
                for dx in range(bead_size):
                    canvas.putpixel((x0 + dx, y0 + dy), (r, g, b))

            if draw:
                info = rgb_to_info.get((r, g, b))
                if info:
                    idx, _ = info
                    label = str(idx + 1)
                    bbox = draw.textbbox((0, 0), label, font=font)
                    tw = bbox[2] - bbox[0]
                    if tw <= bead_size - 2:
                        th = bbox[3] - bbox[1]
                        text_color = _text_color_for_bg(r, g, b)
                        tx = x0 + (bead_size - tw) // 2
                        ty = y0 + (bead_size - th) // 2
                        draw.text((tx, ty), label, fill=text_color, font=font)

    legend = _build_legend(palette_hex, bead_size, grid)
    combined = _hconcat(canvas, legend, grid_color)
    return combined


# ── Helpers ─────────────────────────────────────────────────────────────────


def _text_color_for_bg(r, g, b):
    """Black or white text to maximise contrast against the background."""
    luminance = 0.299 * r + 0.587 * g + 0.114 * b
    return (255, 255, 255) if luminance < 140 else (0, 0, 0)


def _build_legend(palette_hex, bead_size, grid):
    """Colour-swatch legend with ``#RRGGBB`` hex codes."""
    n = len(palette_hex)
    swatch_size = max(bead_size, 16)
    padding = grid * 4
    line_h = swatch_size + padding
    legend_w = swatch_size + padding * 3 + 120
    legend_h = n * line_h + padding * 2

    legend = Image.new("RGB", (legend_w, legend_h), (255, 255, 255))
    draw = ImageDraw.Draw(legend)

    try:
        font = ImageFont.truetype(
            "/System/Library/Fonts/Helvetica.ttc", swatch_size - 4,
        )
    except (IOError, OSError):
        font = ImageFont.load_default()

    for i, hex_color in enumerate(palette_hex):
        y = padding + i * line_h
        r, g, b = hex_to_rgb(hex_color)
        # colour swatch
        draw.rectangle(
            [padding, y, padding + swatch_size, y + swatch_size],
            fill=(r, g, b),
            outline=(40, 40, 40),
            width=2,
        )
        # label:  #1  #RRGGBB
        label = f"#{i + 1}  {hex_color}"
        draw.text(
            (padding + swatch_size + padding,
             y + (swatch_size - (swatch_size - 4)) // 2 - 2),
            label,
            fill=(30, 30, 30),
            font=font,
        )

    return legend


def _hconcat(left, right, fill_color):
    """Horizontally concatenate two images, matching heights."""
    lw, lh = left.size
    rw, rh = right.size
    max_h = max(lh, rh)
    out = Image.new("RGB", (lw + rw, max_h), fill_color)
    out.paste(left, (0, 0))
    out.paste(right, (lw, (max_h - rh) // 2))
    return out
