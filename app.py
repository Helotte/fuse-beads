"""Flask web app for the fuse-beads image converter."""

import io

from flask import Flask, render_template, request, send_file

from beads import (
    build_beads_image,
    load_image,
    match_bead_colors,
    resize_to_beads,
)

app = Flask(__name__)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/generate", methods=["POST"])
def generate():
    # read uploaded image
    file = request.files.get("image")
    if not file or file.filename == "":
        return "No image uploaded", 400

    img = load_image(file.stream)

    # parse parameters
    width = int(request.form.get("width", 50))
    n_colors = int(request.form.get("n_colors", 12))
    bead_size = int(request.form.get("bead_size", 20))
    grid = int(request.form.get("grid", 2))
    show_numbers = request.form.get("show_numbers", "1") == "1"

    # pipeline
    small = resize_to_beads(img, width, None)
    quantized, palette = match_bead_colors(small, n_colors)
    result = build_beads_image(quantized, palette, bead_size, grid,
                               show_numbers=show_numbers)

    # send result as PNG
    buf = io.BytesIO()
    result.save(buf, format="PNG")
    buf.seek(0)

    return send_file(
        buf,
        mimetype="image/png",
        as_attachment=True,
        download_name="fuse_beads_result.png",
    )


if __name__ == "__main__":
    app.run(debug=True, port=8080)
