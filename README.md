# brpack

Encode arbitrary data into a font with color glyphs and package it as WOFF2, which uses Brotli internally.

At runtime, recover the original data by rendering the font onto a canvas.

## Use Case

For larger assets served through CDNs without Brotli support, where the size savings justify the extra deployment complexity.

## Demo

https://etherdream.github.io/brpack

Firefox 147+ and Safari 18.4+ support Brotli decompression via the [DecompressionStream API](https://caniuse.com/mdn-api_decompressionstream_decompressionstream_brotli), but Chrome does not yet support it. Use Chrome to see the WOFF2 path.

![brpack demo showing characters 1, 2, 3 rendered as color glyph images](https://github.com/user-attachments/assets/2a0a312e-8c05-4e5d-a3a5-a648f4eb9b1d)

> As shown, characters 1, 2, and 3 are rendered as images.

In the demo, compression results for a text file:

| Format        | Size      | vs Raw |
|---------------|-----------|--------|
| Raw           | 412,226 B |        |
| Brotli        | 146,749 B | −64.4% |
| WOFF2         | 148,944 B | −63.9% |
| gzip (zopfli) | 174,493 B | −57.7% |

WOFF2 is only ~1.5% larger than raw Brotli, but still ~15% smaller than the best gzip.

## How It Works

Raw data is encoded as RGB pixels, stored as PNG images, and embedded in the font’s CBDT table, much like emoji glyphs. The resulting font is then packaged as WOFF2, so it can be handled by the browser’s native Brotli-based WOFF2 pipeline.

PNG uses zlib internally, so its compression level is set to 0 (store only). This preserves the payload’s original redundancy, adding only a small amount of PNG and zlib container overhead.

To decode it, the page loads the WOFF2 font, renders the glyphs to a canvas, reads back the pixel data, and reconstructs the original byte stream. Since WOFF2 decoding is performed natively by the browser, the JavaScript glue code is only a few hundred bytes minified.

**Why RGB Instead of RGBA?**

Canvas 2D uses premultiplied alpha, which can alter transparent pixel values. To avoid this, only RGB channels are used.

PNG supports RGB natively, and the JavaScript decoder simply skips the alpha channel when reading back from the canvas.

> The payload is padded to a multiple of 3 bytes for RGB packing. The current encoder uses spaces as padding, which tends to be benign for text-heavy inputs such as JS and CSS.

## Installation

Clone this repository and run:

```bash
python -m venv .venv
source .venv/bin/activate

pip install fonttools brotli
```

## Usage

Write a WOFF2 file:

```bash
./brpack.py demo/test.txt \
  --woff2 demo/test.txt.woff2
```

To also write a plain Brotli file:

```bash
./brpack.py demo/test.txt \
  --woff2 demo/test.txt.woff2 \
  --br demo/test.txt.brotli
```

For debugging, use `--ttf`, `--ttx`, or `--png-dir` to write intermediate files:

```bash
./brpack.py demo/test.txt \
  --woff2 demo/test.txt.woff2 \
  --br demo/test.txt.brotli \
  --ttf test.ttf \
  --ttx test.ttx \
  --png-dir .
```

### Character Mapping

Each embedded image is limited to 255 × 255 pixels, so a single glyph can store at most 195,075 bytes. Larger payloads must be split across multiple glyph images and characters.

Use `--chars` to specify the characters mapped to those glyphs. The default is `1234567890` (~1.9 MB max). Add more unique characters for larger payloads.

The JavaScript side must also know which characters were used. For example, "123" means the payload spans three glyph images.

## Size Optimization

Glyphs are rendered top-to-bottom on the canvas (one per row) rather than left-to-right, so the byte stream stays sequential across images and compresses better.

To squeeze out every byte, nonessential font fields are zeroed out where possible, including creation and modification timestamps. This removes unnecessary variation and can slightly improve compressibility. See [template.ttx](template.ttx) for details.

## License

MIT