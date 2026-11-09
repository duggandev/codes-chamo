"""Genera el favicon del proyecto sin dependencias externas."""

import struct
import zlib
from pathlib import Path


SIZE = 64


def png_chunk(kind: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)


def pixel(x: int, y: int) -> tuple[int, int, int, int]:
    # Cuadrado oscuro con esquinas redondeadas.
    radius = 13
    inside = radius <= x < SIZE - radius or radius <= y < SIZE - radius
    if not inside:
        cx = radius if x < radius else SIZE - radius - 1
        cy = radius if y < radius else SIZE - radius - 1
        inside = (x - cx) ** 2 + (y - cy) ** 2 <= radius**2
    if not inside:
        return 0, 0, 0, 0

    # Triangulo de reproduccion rojo centrado.
    if 20 <= x <= 47 and 15 <= y <= 49:
        half_height = (x - 20) * 17 / 27
        if abs(y - 32) <= half_height:
            return 229, 9, 20, 255
    return 10, 10, 10, 255


rows = []
for y in range(SIZE):
    rows.append(b"\x00" + b"".join(bytes(pixel(x, y)) for x in range(SIZE)))

png = b"\x89PNG\r\n\x1a\n"
png += png_chunk(b"IHDR", struct.pack(">IIBBBBB", SIZE, SIZE, 8, 6, 0, 0, 0))
png += png_chunk(b"IDAT", zlib.compress(b"".join(rows), level=9))
png += png_chunk(b"IEND", b"")

# Los navegadores modernos admiten un PNG encapsulado dentro de ICO.
header = struct.pack("<HHH", 0, 1, 1)
entry = struct.pack("<BBBBHHII", SIZE, SIZE, 0, 0, 1, 32, len(png), 22)
Path(__file__).with_name("favicon.ico").write_bytes(header + entry + png)
