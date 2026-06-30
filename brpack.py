#!/usr/bin/env python3
from fontTools.ttLib.tables._g_l_y_f import Glyph
from fontTools.ttLib import TTFont
from pathlib import Path
import logging
import argparse
import struct
import brotli
import copy
import math
import zlib
import sys

# Must match JS decoder's lastIndexOf(99)
END_MARK = 99

IMG_WIDTH = 255
IMG_HEIGHT = 255
IMG_PIXELS = IMG_WIDTH * IMG_HEIGHT
IMG_BYTES = IMG_PIXELS * 3  # RGB


def u32be(n: int) -> bytes:
    return struct.pack('>I', n & 0xFFFFFFFF)


def png_chunk(type4: str, data: bytes) -> bytes:
    chunk_type = type4.encode('ascii')
    body = chunk_type + data
    crc = u32be(zlib.crc32(body))
    return u32be(len(data)) + body + crc


def gen_png(src_buf: bytes, width: int, height: int) -> bytes:
    row_bytes = width * 3

    dst_buf = bytearray(height * (1 + row_bytes))
    dst_pos = 0
    src_pos = 0

    for _ in range(height):
        dst_buf[dst_pos] = 0    # filter: none
        dst_pos += 1

        dst_buf[dst_pos : dst_pos + row_bytes] = \
        src_buf[src_pos : src_pos + row_bytes]

        dst_pos += row_bytes
        src_pos += row_bytes

    idat = zlib.compress(dst_buf, level=0)
    ihdr = bytearray(13)

    ihdr[0:4] = u32be(width)
    ihdr[4:8] = u32be(height)
    ihdr[8]   = 8   # bit depth
    ihdr[9]   = 2   # color type RGB
    ihdr[10]  = 0   # compression method
    ihdr[11]  = 0   # filter method
    ihdr[12]  = 0   # interlace method

    return b''.join([
        b'\x89PNG\r\n\x1A\n',
        png_chunk('IHDR', bytes(ihdr)),
        png_chunk('IDAT', idat),
        png_chunk('IEND', b''),
    ])


def unique_chars(s: str) -> str:
    if len(set(s)) != len(s):
        raise argparse.ArgumentTypeError('must contain unique characters')
    return s


def msg(text: str, file=sys.stdout):
    print(f'[brpack] {text}', file=file)


class TimestampFilter(logging.Filter):
    def filter(self, record):
        return "timestamp seems very low" not in record.getMessage()


def main():
    logging.getLogger("fontTools.ttLib.tables._h_e_a_d").addFilter(TimestampFilter())

    parser = argparse.ArgumentParser()
    parser.add_argument('infile', help='The input file')
    parser.add_argument('--woff2', help='Output path for the .woff2 file.')
    parser.add_argument('--ttx', help='Output path for the .ttx file.')
    parser.add_argument('--ttf', help='Output path for the .ttf file.')
    parser.add_argument('--br', help='Output path for the .br file.')
    parser.add_argument('--png-dir', help='Output directory for image files.')
    parser.add_argument('--chars',
        help='Character sequence (must be unique).',
        type=unique_chars,
        default='1234567890'
    )
    args = parser.parse_args()

    file_data = Path(args.infile).read_bytes()

    # Pad with spaces so that the total length
    # (data + padding + END_MARK) is divisible by 3.
    in_buf = bytearray(file_data)
    while (len(in_buf) + 1) % 3 != 0:
        in_buf.append(0x20)
    in_buf.append(END_MARK)

    pixel_num = len(in_buf) // 3
    image_num = math.ceil(pixel_num / IMG_PIXELS)
    msg(f'Input: {len(in_buf)} bytes, images: {image_num}')

    if image_num > len(args.chars):
        parser.error('not enough characters for the number of images')

    cur_dir = Path(__file__).resolve().parent
    font = TTFont()
    font.importXML(cur_dir / 'template.ttx')

    # .notdef must be included
    font['maxp'].numGlyphs = 1 + image_num

    template_bitmap = font['CBDT'].strikeData[0]['glyf0']

    if args.png_dir:
        Path(args.png_dir).mkdir(parents=True, exist_ok=True)

    glyph_order = font.getGlyphOrder()

    for i in range(image_num):
        name = f'glyf{i}'
        part = in_buf[i * IMG_BYTES : (i + 1) * IMG_BYTES]

        img_buf = bytearray(IMG_BYTES)
        img_buf[:len(part)] = part
        png_data = gen_png(img_buf, IMG_WIDTH, IMG_HEIGHT)

        bitmap = copy.deepcopy(template_bitmap)
        bitmap.imageData = png_data

        if args.png_dir:
            png_path = Path(args.png_dir) / f'0x{ord(args.chars[i]):04x}.png'
            png_path.write_bytes(png_data)

        font['CBDT'].strikeData[0][name] = bitmap
        font['CBLC'].strikes[0].indexSubTables[0].names.append(name)
        font['hmtx'].metrics[name] = (0, 0)
        font['glyf'].glyphs[name] = Glyph()

        code = ord(args.chars[i])
        font['cmap'].tables[0].cmap[code] = name

        glyph_order.append(name)

    font.setGlyphOrder(glyph_order)
    font.recalcTimestamp = False
    font.recalcBBoxes = False

    if args.ttx:
        font.saveXML(args.ttx)

    if args.ttf:
        font.save(args.ttf)

    if args.woff2:
        font.flavor = 'woff2'
        font.save(args.woff2)

    if args.br:
        pure_brotli = brotli.compress(
            file_data,
            quality=11,
            mode=brotli.MODE_TEXT,
            lgwin=24,
        )
        Path(args.br).write_bytes(pure_brotli)


if __name__ == '__main__':
    main()
