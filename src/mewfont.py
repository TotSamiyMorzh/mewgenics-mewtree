"""The game's own fonts for the page: DefineFont3 outlines from a SWF -> a TrueType file.

Mewgenics keeps its fonts as Flash fonts (swfs/international_fonts.swf: "TikaFontIntl" is the
hand-written body font, "Mewgenics Organ Grinder Cyr" the title font; both have Cyrillic).
A DefineFont3 glyph is a SHAPE of straight and quadratic edges on a 1024 x 20 em, which is
exactly what a TrueType `glyf` outline holds, so the conversion is lossless: divide by 20,
flip y, write the tables. Standard library only.
"""
import struct
from catface import Bits, tags

EM = 1024


def _glyph(b, start, end):
    """SHAPE without style arrays -> contours [[(x, y, on_curve)...]] in font units, y up."""
    bs = Bits(b, start); nf = bs.ub(4); nl = bs.ub(4)
    x = y = 0; cur = None; out = []
    P = lambda px, py: (int(round(px / 20)), int(round(-py / 20)))
    while (bs.q >> 3) < end:
        if bs.ub(1) == 0:
            fl = bs.ub(5)
            if not fl: break
            if fl & 1:
                n = bs.ub(5); x = bs.sb(n); y = bs.sb(n); cur = None
            if fl & 2: bs.ub(nf)
            if fl & 4: bs.ub(nf)
            if fl & 8: bs.ub(nl)
            if fl & 16: break                                  # new styles: never in glyphs
            continue
        if cur is None:
            cur = [P(x, y) + (True,)]; out.append(cur)
        if bs.ub(1):
            n = bs.ub(4) + 2
            if bs.ub(1): dx = bs.sb(n); dy = bs.sb(n)
            elif bs.ub(1): dx = 0; dy = bs.sb(n)
            else: dx = bs.sb(n); dy = 0
            x += dx; y += dy
        else:
            n = bs.ub(4) + 2
            cx = x + bs.sb(n); cy = y + bs.sb(n); x = cx + bs.sb(n); y = cy + bs.sb(n)
            cur.append(P(cx, cy) + (False,))
        cur.append(P(x, y) + (True,))
    res = []
    for c in out:
        if len(c) > 1 and c[-1] == c[0]: c = c[:-1]            # closed: the last point repeats the first
        if len(c) >= 3: res.append(c)
    return res


def read_fonts(swf_bytes, wanted):
    """{wanted name: font dict} for DefineFont3 fonts whose name starts with a wanted name."""
    if swf_bytes[:3] != b"FWS": raise ValueError("fonts: unknown SWF container")
    b = swf_bytes[8:]
    pos = (5 + 4 * (b[0] >> 3) + 7) // 8 + 4
    out = {}
    for code, p, ln in tags(b, pos, len(b)):
        if code != 75: continue
        flags = b[p + 2]; nl = b[p + 4]
        name = b[p + 5:p + 5 + nl].rstrip(b"\0").decode("utf-8", "replace")
        want = next((w for w in wanted if name.startswith(w) and w not in out), None)
        if not want: continue
        q = p + 5 + nl; ng = struct.unpack_from("<H", b, q)[0]; q += 2
        wide_off, wide_codes = flags & 8, flags & 4
        off = (lambda i: struct.unpack_from("<I", b, q + 4 * i)[0]) if wide_off else (lambda i: struct.unpack_from("<H", b, q + 2 * i)[0])
        codes = q + off(ng)
        cps = [struct.unpack_from("<H", b, codes + 2 * i)[0] if wide_codes else b[codes + i] for i in range(ng)]
        lay = codes + (2 if wide_codes else 1) * ng
        asc, desc, lead = 900, 250, 0; adv = [EM // 2] * ng
        if flags & 0x80 and lay + 6 + 2 * ng <= p + ln:
            asc, desc, lead = (int(round(v / 20)) for v in struct.unpack_from("<HHh", b, lay))
            adv = [max(0, int(round(v / 20))) for v in struct.unpack_from("<%dh" % ng, b, lay + 6)]
        glyphs = {}
        for i, cp in enumerate(cps):
            if cp and cp not in glyphs:
                glyphs[cp] = (adv[i], _glyph(b, q + off(i), q + (off(i + 1) if i + 1 < ng else off(ng))))
        if 32 in glyphs: glyphs.setdefault(0xA0, (glyphs[32][0], []))
        out[want] = {"name": want, "ascent": asc, "descent": desc, "leading": lead, "glyphs": glyphs}
    return out


def _table_glyf(order, glyphs):
    data, loca, boxes, maxp_pts, maxp_cnt = b"", [0], [], 0, 0
    for cp in order:
        cs = glyphs[cp][1] if cp is not None else []
        g = b""; box = (0, 0, 0, 0)
        if cs:
            pts = [p for c in cs for p in c]
            xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
            box = (min(xs), min(ys), max(xs), max(ys))
            ends, n = [], 0
            for c in cs: n += len(c); ends.append(n - 1)
            dx = [xs[0]] + [xs[i] - xs[i - 1] for i in range(1, len(xs))]
            dy = [ys[0]] + [ys[i] - ys[i - 1] for i in range(1, len(ys))]
            g = (struct.pack(">hhhhh", len(cs), *box) + struct.pack(">%dH" % len(ends), *ends) + struct.pack(">H", 0)
                 + bytes(1 if p[2] else 0 for p in pts) + struct.pack(">%dh" % len(dx), *dx) + struct.pack(">%dh" % len(dy), *dy))
            g += b"\0" * (-len(g) % 4)
            maxp_pts = max(maxp_pts, len(pts)); maxp_cnt = max(maxp_cnt, len(cs))
        data += g; loca.append(len(data)); boxes.append(box)
    return data, struct.pack(">%dI" % len(loca), *loca), boxes, maxp_pts, maxp_cnt


def _table_cmap(order):
    """Format 4; glyphs are in code point order, so every run of consecutive code points is one segment."""
    segs = []                                              # (start, end, delta)
    for gid, cp in enumerate(order):
        if cp is None: continue
        if segs and segs[-1][1] == cp - 1: segs[-1][1] = cp
        else: segs.append([cp, cp, (gid - cp) & 0xFFFF])
    segs.append([0xFFFF, 0xFFFF, 1])
    n = len(segs); sr = 2 * (1 << (n.bit_length() - 1))
    sub = (struct.pack(">HHHHHHH", 4, 16 + 8 * n, 0, 2 * n, sr, (sr // 2).bit_length() - 1, 2 * n - sr)
           + struct.pack(">%dH" % n, *(s[1] for s in segs)) + b"\0\0" + struct.pack(">%dH" % n, *(s[0] for s in segs))
           + struct.pack(">%dH" % n, *(s[2] for s in segs)) + b"\0\0" * n)
    return struct.pack(">HHHHIHHI", 0, 2, 0, 3, 20, 3, 1, 20) + sub


def _table_name(family):
    recs = {1: family, 2: "Regular", 3: family + " (from the game files)", 4: family, 5: "1.0", 6: family.replace(" ", "")}
    strs = b""; hdr = b""
    for nid, s in sorted(recs.items()):
        e = s.encode("utf-16-be"); hdr += struct.pack(">HHHHHH", 3, 1, 0x409, nid, len(e), len(strs)); strs += e
    return struct.pack(">HHH", 0, len(recs), 6 + len(hdr)) + hdr + strs


def to_ttf(font, family):
    """font dict from read_fonts -> TrueType bytes with the given family name."""
    glyphs = font["glyphs"]
    order = [None] + sorted(cp for cp in glyphs if cp < 0xFFFF)          # glyph 0 = .notdef
    glyf, loca, boxes, mp, mc = _table_glyf(order, glyphs)
    adv = [EM // 2] + [glyphs[cp][0] for cp in order[1:]]
    used = [bx for bx, cp in zip(boxes, order) if cp is not None and glyphs[cp][1]] or [(0, 0, 0, 0)]
    x0, y0 = min(b[0] for b in used), min(b[1] for b in used); x1, y1 = max(b[2] for b in used), max(b[3] for b in used)
    asc, desc, n = max(font["ascent"], y1), max(font["descent"], -y0), len(order)
    head = struct.pack(">IIIIHHqqhhhhHHhhh", 0x00010000, 0x00010000, 0, 0x5F0F3CF5, 3, EM, 0, 0, x0, y0, x1, y1, 0, 8, 2, 1, 0)
    hhea = struct.pack(">IhhhHhhhhhhhhhhhH", 0x00010000, asc, -desc, 0, max(adv), min(b[0] for b in used),
                       min(a - b[2] for a, b in zip(adv, boxes)), x1, 1, 0, 0, 0, 0, 0, 0, 0, n)
    hmtx = b"".join(struct.pack(">Hh", a, b[0]) for a, b in zip(adv, boxes))
    maxp = struct.pack(">IHHHHHHHHHHHHHH", 0x00010000, n, mp, mc, 0, 0, 2, 0, 0, 0, 0, 0, 0, 0, 0)
    cps = order[1:]
    os2 = struct.pack(">HhHHHhhhhhhhhhhh10sIIII4sHHHhhhHHIIhhHHH", 3, sum(adv) // n, 400, 5, 0, 650, 600, 0, 75, 650, 600, 0, 350,
                      50, 250, 0, b"\0" * 10, 0x00000203, 0, 0, 0, b"MEWT", 0x40, min(cps), min(max(cps), 0xFFFF), asc, -desc, 0,
                      asc, desc, 0x00000005, 0, EM // 2, EM * 7 // 10, 0, 32, 0)
    post = struct.pack(">IIhhIIIII", 0x00030000, 0, -100, 50, 0, 0, 0, 0, 0)
    tables = {b"OS/2": os2, b"cmap": _table_cmap(order), b"glyf": glyf, b"head": head, b"hhea": hhea, b"hmtx": hmtx,
              b"loca": loca, b"maxp": maxp, b"name": _table_name(family), b"post": post}
    csum = lambda d: sum(struct.unpack(">%dI" % (len(d) // 4), d)) & 0xFFFFFFFF
    pad = lambda d: d + b"\0" * (-len(d) % 4)
    nt = len(tables); sr = 16 * (1 << (nt.bit_length() - 1))
    out = struct.pack(">IHHHH", 0x00010000, nt, sr, (sr // 16).bit_length() - 1, 16 * nt - sr)
    offset = 12 + 16 * nt; body = b""; head_at = 0
    for tag in sorted(tables):
        d = pad(tables[tag])
        if tag == b"head": head_at = offset + len(body)
        out += tag + struct.pack(">III", csum(d), offset + len(body), len(tables[tag])); body += d
    ttf = bytearray(out + body)
    struct.pack_into(">I", ttf, head_at + 8, (0xB1B0AFBA - csum(bytes(ttf))) & 0xFFFFFFFF)   # checkSumAdjustment
    return bytes(ttf)
