"""Read-only parser for Mewgenics save files (SQLite, cats = u32 size + LZ4 block).

Layout reverse-engineered on save v1.1 (2026-10), cross-checked against
mewgenics-cat-bridge's in-memory structs (CatData / CampaignStats):
  name(utf16) · nameplate str · sex i32 x2 (0 m, 1 f, 2 ?) · status flags u64 (bit 1 retired,
  5 dead, 10 died of old age, 11..17 given to Beanies / Butch / Tink / Tracy / Organ Grinder /
  Frank / Baby Jack, 18 died in battle) · str · u32 · libido f64 · sexuality f64 (the game shows
  < 0.1 straight, > 0.9 gay, else bi) · lover key i64 · lover affinity f64 · aggression f64
  · rival key i64 · rival affinity f64 · fertility f64 (p0lymeric/mewgenics_analysis) · body parts
  (texture, palette, collar, 14 x {part_idx,...} 20 B) · voice str · pitch f64
  · stats 3 x 7 i32 (base, levelling, injuries) · str · hp i32 · dead u8
  · abilities: 6 usable, 4 innate, 4 x (passive/disorder str + u32 tier)
  · equipment … · class str · level u32 · … · birthday i64
`dead` matches the house roster exactly (all 18 house cats dead=0).
"""
import sqlite3, struct, shutil, tempfile, os

STATS = ("str", "dex", "con", "int", "spd", "cha", "lck")
PARTS = ("body", "head", "tail", "leg1", "leg2", "arm1", "arm2", "lefteye", "righteye",
         "lefteyebrow", "righteyebrow", "leftear", "rightear", "mouth")

def lz4_block(src):
    dst = bytearray(); i = 0; n = len(src)
    while i < n:
        t = src[i]; i += 1; l = t >> 4
        if l == 15:
            while True:
                b = src[i]; i += 1; l += b
                if b != 255: break
        dst += src[i:i + l]; i += l
        if i >= n: break
        off = src[i] | src[i + 1] << 8; i += 2; m = (t & 15) + 4
        if (t & 15) == 15:
            while True:
                b = src[i]; i += 1; m += b
                if b != 255: break
        s = len(dst) - off
        if off >= m: dst += dst[s:s + m]
        else:
            for k in range(m): dst.append(dst[s + k])
    return bytes(dst)

def _str(d, o):
    l = struct.unpack_from("<Q", d, o)[0]
    if l > 4096: raise ValueError("bad string length at %d" % o)
    return d[o + 8:o + 8 + l].decode("utf-8", "replace"), o + 8 + l

def parse_cat(key, raw):
    d = lz4_block(raw[4:])
    o = 12; n = struct.unpack_from("<Q", d, o)[0]; o += 8
    c = {"id": key, "name": d[o:o + 2 * n].decode("utf-16-le", "replace")}; o += 2 * n
    _, o = _str(d, o)                                    # nameplate symbol
    c["sex"] = struct.unpack_from("<i", d, o)[0]; c["flags"] = int.from_bytes(d[o + 8:o + 16], "little"); o += 16
    _, o = _str(d, o)
    (c["libido"], c["sexuality"], c["lover"], c["lover_aff"], c["aggression"], c["hater"], c["hater_aff"],
     c["fertility"]) = struct.unpack_from("<ddqddqdd", d, o + 4)
    t = o + 68
    c["texture"], c["palette"], c["collar_palette"] = struct.unpack_from("<3i", d, t)
    r = t + 12
    c["parts"] = {p: struct.unpack_from("<i", d, r + 20 * i)[0] for i, p in enumerate(PARTS)}
    o = r + 280 + 8
    c["voice"], o = _str(d, o); o += 8
    st = struct.unpack_from("<21i", d, o); o += 84
    c["base"] = dict(zip(STATS, st[0:7])); c["lvlup"] = dict(zip(STATS, st[7:14])); c["inj"] = dict(zip(STATS, st[14:21]))
    _, o = _str(d, o)
    c["hp"] = struct.unpack_from("<i", d, o)[0]; c["dead"] = bool(d[o + 4])
    a = d.find(b"DefaultMove", o) - 8
    o = a; usable = []; innate = []; passives = []
    for _ in range(6): s, o = _str(d, o); usable.append(s)
    for _ in range(4): s, o = _str(d, o); innate.append(s)
    for _ in range(4):
        s, o = _str(d, o); tier = struct.unpack_from("<I", d, o)[0]; o += 4
        if s != "None": passives.append([s, tier])
    c["actives"] = [s for s in usable[2:] if s != "None"]
    c["basic"] = usable[1]
    c["innate"] = [s for s in innate if s != "None"]
    c["passives"] = passives
    # equipment + class: length-prefixed identifiers until the end; class is the last
    strs = []; i = o
    while i < len(d) - 8:
        l = struct.unpack_from("<Q", d, i)[0]
        if 2 <= l < 64 and i + 8 + l <= len(d):
            s = d[i + 8:i + 8 + l]
            if s.replace(b"_", b"").isalnum():
                strs.append((i, s.decode())); i += 8 + l; continue
        i += 1
    c["cls"] = strs[-1][1]
    c["items"] = [s for _, s in strs[:-1] if s != "None"]
    tail = strs[-1][0] + 8 + len(strs[-1][1])
    c["level"] = struct.unpack_from("<I", d, tail)[0]
    c["born"] = struct.unpack_from("<q", d, tail + 12)[0]
    return c

def read_save(path):
    tmp = os.path.join(tempfile.mkdtemp(prefix="mewtree"), "save.sav")
    shutil.copyfile(path, tmp)                      # never touch the original
    db = sqlite3.connect(tmp)
    try:
        cats, errors = {}, []
        for k, raw in db.execute("select key, data from cats"):
            try: cats[k] = parse_cat(k, raw)
            except Exception as e: errors.append((k, str(e)))
        files = dict(db.execute("select key, data from files"))
        props = dict(db.execute("select key, data from properties"))
        try: furniture = db.execute("select count(*) from furniture").fetchone()[0]
        except sqlite3.Error: furniture = None
    finally:
        db.close()
    # pedigree: Abseil swiss table. header {i64 ?, i64 size, i64 capacity-1},
    # ctrl bytes (cap + 16 clones), then cap slots of {i64 child, i64 sire, i64 dam, f64 coi}.
    # Only slots whose ctrl byte is < 0x80 are filled; empty ones hold stale memory.
    p = files.get("pedigree", b""); ped = {}
    if len(p) >= 24:
        cap = struct.unpack_from("<q", p, 16)[0] + 1
        ctrl = p[24:24 + cap]; base = 24 + cap + 16
        for i, cb in enumerate(ctrl):
            if cb < 0x80:
                ch, a, b = struct.unpack_from("<qqq", p, base + 32 * i)
                ped[ch] = (a, b, struct.unpack_from("<d", p, base + 32 * i + 24)[0])
    h = files.get("house_state", b""); house = {}
    if len(h) >= 8:
        n = struct.unpack_from("<I", h, 4)[0]; o = 8
        for _ in range(n):
            k, l = struct.unpack_from("<QQ", h, o); o += 16
            house[k] = h[o:o + l].decode(); o += l + 24
    for k, c in cats.items():
        a, b, f = ped.get(k, (-1, -1, 0.0))
        c["parents"] = [x for x in (a, b) if x in cats]
        c["coi"] = f
        c["room"] = house.get(k)
        c["status"] = "house" if k in house else ("dead" if c["dead"] else "gone")
    return {"cats": cats, "day": props.get("current_day"), "errors": errors, "props": props, "furniture": furniture}
