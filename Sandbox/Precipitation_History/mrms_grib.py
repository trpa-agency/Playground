"""
Fast reader for MRMS GRIB2 files.

MRMS packs its CONUS field with packingType=grid_png (data representation
template 5.41): section 7 holds a complete 16-bit greyscale PNG of the
7000x3500 grid. eccodes will decode that, but it insists on inflating all
24.5 million points to float64, which costs ~6.5 s per file -- roughly 80
CPU-hours across a 12-season pull.

Decoding the PNG directly and cropping to the Tahoe rows costs a fraction
of that. The integer-to-physical conversion is the standard GRIB2 one,
value = (R + X * 2**E) / 10**D, with R/E/D read from section 5.
"""

import struct

import numpy as np


def split_sections(msg):
    """Return {section_number: payload_bytes} for one GRIB2 message."""
    assert msg[:4] == b"GRIB", "not a GRIB message"
    out = {}
    pos = 16                                   # section 0 is always 16 bytes
    while pos < len(msg) - 4:
        if msg[pos:pos + 4] == b"7777":
            break
        length = struct.unpack(">I", msg[pos:pos + 4])[0]
        num = msg[pos + 4]
        out[num] = msg[pos:pos + length]
        pos += length
    return out


def grid_shape(sec3):
    """(nj, ni) from the grid definition section."""
    ni = struct.unpack(">I", sec3[30:34])[0]
    nj = struct.unpack(">I", sec3[34:38])[0]
    return nj, ni


def unpack_params(sec5):
    """Reference value R, binary scale E, decimal scale D, bit depth."""
    R = struct.unpack(">f", sec5[11:15])[0]
    E = struct.unpack(">h", sec5[15:17])[0]
    D = struct.unpack(">h", sec5[17:19])[0]
    bits = sec5[19]
    return R, E, D, bits


def decode_rows(msg, row0, row1):
    """Decode only rows [row0, row1) of the field, as float32 physical units.

    Rows run north to south, matching the MRMS grid.
    """
    from PIL import Image
    import io

    sec = split_sections(msg)
    nj, ni = grid_shape(sec[3])
    R, E, D, bits = unpack_params(sec[5])

    png = sec[7][5:]                           # strip the 5-byte section header
    im = Image.open(io.BytesIO(png))
    # 16-bit greyscale PNG arrives as mode "I" (32-bit int) in Pillow.
    arr = np.asarray(im)[row0:row1]

    vals = (R + arr.astype("float64") * (2.0 ** E)) / (10.0 ** D)
    return vals.astype("float32"), nj, ni
