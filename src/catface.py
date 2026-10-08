"""Cat faces the way the game builds them, as SVG.

Mewgenics has no ready-made picture of a bred cat: glaiel::CatParts composes it at
runtime from swfs/catparts.swf. `CatHeadPlacements`, frame = head index - 1, holds
the head (fill = clip mask, `tex` fur texture slot, outline) and named markers the
game puts the other parts on:
    lear / rear   CatEar      full marker matrix (rear is mirrored)
    leye / reye   CatEye      marker position only, scale 1 (reye mirrored), + CatEyebrow
    mouth         CatMouth    marker position only
    tex           frame = texture index - 1 (also inside the ears)
Colour is a palette shader: a grey source colour r picks entry round(r*15) of the
cat's row in textures/palette.png; anything coloured is left alone.

Shapes become shared <path> defs (coordinates stay in twips), greys become CSS
classes f0..f15 / s0..s15 resolved through --p0..--p15 of the cat's palette class,
so one copy of every part serves all cats. Standard library only.
"""
import base64, re, struct, zlib

PLACEMENTS = "CatHeadPlacements"
CARD, RIG = "FamilyTreePortrait", "familytree_fla.cat_6"       # swfs/familytree.swf
HEAD, BG, CAT = "\x01H", "\x01B", "\x01C"                       # placeholders the page fills in
ID = (1.0, 0.0, 0.0, 1.0, 0, 0)


class Bits:
    def __init__(s, b, p): s.b, s.q = b, p * 8
    def ub(s, n):
        if not n: return 0
        q = s.q; e = q + n; s.q = e
        v = int.from_bytes(s.b[q >> 3:(e + 7) >> 3], "big")
        return (v >> (-e & 7)) & ((1 << n) - 1)
    def sb(s, n):
        v = s.ub(n)
        return v - (1 << n) if n and v >> (n - 1) else v
    def align(s): s.q = (s.q + 7) & ~7
    def u8(s): s.align(); v = s.b[s.q >> 3]; s.q += 8; return v
    def u16(s): s.align(); v = struct.unpack_from("<H", s.b, s.q >> 3)[0]; s.q += 16; return v
    def rect(s):
        n = s.ub(5); r = [s.sb(n) for _ in range(4)]; s.align(); return r        # x0 x1 y0 y1
    def matrix(s):
        s.align(); a = d = 1.0; b = c = 0.0
        if s.ub(1): n = s.ub(5); a = s.sb(n) / 65536; d = s.sb(n) / 65536
        if s.ub(1): n = s.ub(5); b = s.sb(n) / 65536; c = s.sb(n) / 65536
        n = s.ub(5); tx = s.sb(n); ty = s.sb(n); s.align()
        return (a, b, c, d, tx, ty)                # x' = a*x + c*y + tx ; y' = b*x + d*y + ty
    def cxform(s):
        """-> (r, g, b, a multipliers, r, g, b, a offsets)."""
        s.align(); ha, hm = s.ub(1), s.ub(1); n = s.ub(4)
        mult = [s.sb(n) / 256 for _ in range(4)] if hm else [1.0] * 4
        add = [s.sb(n) for _ in range(4)] if ha else [0] * 4
        s.align(); return tuple(mult) + tuple(add)
    def color(s, alpha):
        s.align(); p = s.q >> 3; n = 4 if alpha else 3; s.q += 8 * n
        c = tuple(s.b[p:p + n]); return c if alpha else c + (255,)
    def cstr(s):
        s.align(); p = s.q >> 3; e = s.b.index(0, p); s.q = (e + 1) * 8
        return s.b[p:e].decode("utf-8", "replace")


def tags(b, pos, end):
    while pos + 2 <= end:
        h = b[pos] | b[pos + 1] << 8; pos += 2
        code, ln = h >> 6, h & 0x3F
        if ln == 0x3F: ln = struct.unpack_from("<I", b, pos)[0]; pos += 4
        yield code, pos, ln
        pos += ln
        if code == 0: break


def mul(m, n):  # m applied after n
    a, b, c, d, tx, ty = n; A, B, C, D, TX, TY = m
    return (A * a + C * b, B * a + D * b, A * c + C * d, B * c + D * d, A * tx + C * ty + TX, B * tx + D * ty + TY)


def box_of(m, bb):
    if bb is None: return None
    x0, y0, x1, y1 = bb
    pts = [(m[0] * x + m[2] * y + m[4], m[1] * x + m[3] * y + m[5]) for x in (x0, x1) for y in (y0, y1)]
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return (min(xs), min(ys), max(xs), max(ys))


def union(a, b):
    if a is None: return b
    if b is None: return a
    return (min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3]))


def _n(v):
    s = "%.4f" % v
    return s.rstrip("0").rstrip(".") if "." in s else s


def _tf(m):
    if m == ID: return ""
    if m[:4] == (1.0, 0.0, 0.0, 1.0): return ' transform="translate(%d %d)"' % (m[4], m[5])
    return ' transform="matrix(%s)"' % " ".join(_n(v) for v in m)


def _grey(c):
    """Palette slot for a grey colour, else None (the game's paletted shader)."""
    if abs(c[0] - c[1]) <= 1 and abs(c[0] - c[2]) <= 1: return int(c[0] / 255 * 15 + 0.5)
    return None


def _paint(kind, c, pal=True):
    """kind: 'f' fill / 's' stroke -> (class or None, attribute text)."""
    g = _grey(c) if pal else None; prop = "stroke" if kind == "s" else "fill"
    attr = "" if g is not None else ' %s="#%02x%02x%02x"' % ((prop,) + c[:3])
    if c[3] < 255: attr += ' %s-opacity="%s"' % (prop, _n(c[3] / 255))
    return (kind + str(g) if g is not None else None), attr


class Swf:
    """One SWF, parsed lazily into SVG. `defs` (id -> markup) is shared between documents, `px`
    keeps their ids apart; `pal` turns greys into palette classes (cat parts only)."""

    def __init__(self, swf_bytes, defs, px, pal):
        if swf_bytes[:3] == b"CWS": b = zlib.decompress(swf_bytes[8:])
        elif swf_bytes[:3] == b"FWS": b = swf_bytes[8:]
        else: raise ValueError("unknown SWF container")
        self.b = b; self.defs = defs; self.px = px; self.pal = pal
        self.chars, self.sym = {}, {}
        pos = (5 + 4 * (b[0] >> 3) + 7) // 8 + 4
        for code, p, ln in tags(b, pos, len(b)):
            if code in (2, 22, 32, 83): self.chars[b[p] | b[p + 1] << 8] = ("shape", p, ln, code)
            elif code == 39: self.chars[b[p] | b[p + 1] << 8] = ("sprite", p + 4, ln - 4, code)
            elif code in (20, 36): self.chars[b[p] | b[p + 1] << 8] = ("bitmap", p, ln, code)
            elif code == 76:
                q = p + 2
                for _ in range(b[p] | b[p + 1] << 8):
                    e = b.index(0, q + 2); self.sym[b[q + 2:e].decode()] = b[q] | b[q + 1] << 8; q = e + 1
        self._shape, self._dl, self._sprite, self._clip, self._nfr = {}, {}, {}, {}, {}
        self._names = {}          # (sprite, frame) -> instance names anywhere below it
        self._bm, self._cx = {}, {}
        self._grad = 0

    # ---------------------------------------------------------------- shapes

    def _fills(self, bs, ver):
        n = bs.u8()
        if n == 0xFF and ver >= 2: n = bs.u16()
        out = []
        for _ in range(n):
            t = bs.u8()
            if t == 0x00: out.append(("solid", bs.color(ver >= 3)))
            elif t in (0x10, 0x12, 0x13):
                m = bs.matrix(); bs.ub(4); ng = bs.ub(4)
                stops = [(bs.u8(), bs.color(ver >= 3)) for _ in range(ng)]
                if t == 0x13: bs.u16()
                out.append(("linear" if t == 0x10 else "radial", m, stops))
            elif 0x40 <= t <= 0x43:
                bid = bs.u16(); out.append(("bitmap", bid, bs.matrix()))
            else: raise ValueError("fill type %x" % t)
        return out

    def _lines(self, bs, ver):
        n = bs.u8()
        if n == 0xFF: n = bs.u16()
        out = []
        for _ in range(n):
            w = bs.u16()
            if ver == 4:
                bs.ub(2); join = bs.ub(2); hasfill = bs.ub(1); bs.ub(11)
                if join == 2: bs.u16()
                if hasfill:
                    f = self._fills_one(bs)
                    col = f[1] if f[0] == "solid" else f[2][0][1] if f[0] == "linear" else (0, 0, 0, 255)
                else: col = bs.color(True)
            else: col = bs.color(ver >= 3)
            out.append((w, col))
        return out

    def _fills_one(self, bs):
        t = bs.u8()
        if t == 0x00: return ("solid", bs.color(True))
        if t in (0x10, 0x12, 0x13):
            m = bs.matrix(); bs.ub(4); ng = bs.ub(4)
            stops = [(bs.u8(), bs.color(True)) for _ in range(ng)]
            if t == 0x13: bs.u16()
            return ("linear", m, stops)
        bid = bs.u16(); return ("bitmap", bid, bs.matrix())

    def _bitmap(self, bid):
        """Bitmap character as a <pattern> def (the PNG is embedded once); None if it is not there
        (Flash leaves fills pointing at bitmap 65535 behind)."""
        c = self.chars.get(bid)
        if not c or c[0] != "bitmap": return None
        pid = "%sb%d" % (self.px, bid)
        if pid not in self.defs:
            try: png, w, h = swf_bitmap_png(self.b, c[1], c[2], c[3])
            except Exception: return None
            self.defs[pid] = ('<image id="%s" width="%d" height="%d" preserveAspectRatio="none" href="data:image/png;base64,%s"/>'
                              % (pid, w, h, base64.b64encode(png).decode()))
            self._bm[bid] = (w, h)
        return pid

    def _parse_shape(self, cid):
        _, p, ln, code = self.chars[cid]
        ver = {2: 1, 22: 2, 32: 3, 83: 4}[code]
        bs = Bits(self.b, p); bs.u16(); x0, x1, y0, y1 = bs.rect()
        if ver == 4: bs.rect(); bs.u8()
        cur = {"fills": self._fills(bs, ver), "lines": self._lines(bs, ver), "edges": []}
        groups = [cur]
        bs.align(); nf = bs.ub(4); nl = bs.ub(4)
        x = y = 0; f0 = f1 = l = 0
        while True:
            if bs.ub(1) == 0:
                fl = bs.ub(5)
                if not fl: break
                if fl & 1: n = bs.ub(5); x = bs.sb(n); y = bs.sb(n)
                if fl & 2: f0 = bs.ub(nf)
                if fl & 4: f1 = bs.ub(nf)
                if fl & 8: l = bs.ub(nl)
                if fl & 16:
                    cur = {"fills": self._fills(bs, ver), "lines": self._lines(bs, ver), "edges": []}
                    groups.append(cur); bs.align(); nf = bs.ub(4); nl = bs.ub(4)
            elif bs.ub(1):
                n = bs.ub(4) + 2
                if bs.ub(1): dx = bs.sb(n); dy = bs.sb(n)
                elif bs.ub(1): dx = 0; dy = bs.sb(n)
                else: dx = bs.sb(n); dy = 0
                cur["edges"].append((f0, f1, l, (x, y), None, (x + dx, y + dy))); x += dx; y += dy
            else:
                n = bs.ub(4) + 2
                cx = x + bs.sb(n); cy = y + bs.sb(n); ex = cx + bs.sb(n); ey = cy + bs.sb(n)
                cur["edges"].append((f0, f1, l, (x, y), (cx, cy), (ex, ey))); x, y = ex, ey
        return (x0, y0, x1, y1), groups

    @staticmethod
    def _d(segs, close):
        """segs: [(start, ctrl|None, end)] already chained -> compact relative path data."""
        out = []; pos = None
        for a, c, e in segs:
            if pos != a:
                if close and pos is not None: out.append("z")
                out.append("M%d %d" % a)
            if c is None: out.append("l%d %d" % (e[0] - a[0], e[1] - a[1]))
            else: out.append("q%d %d %d %d" % (c[0] - a[0], c[1] - a[1], e[0] - a[0], e[1] - a[1]))
            pos = e
        if close and out: out.append("z")
        return "".join(out).replace(" -", "-")

    @staticmethod
    def _loops(edges):
        """Chain directed edges (fill on one side) into closed loops; winding is what matters."""
        by = {}
        for i, e in enumerate(edges): by.setdefault(e[0], []).append(i)
        used = [False] * len(edges); out = []
        for i in range(len(edges)):
            if used[i]: continue
            used[i] = True; out.append(edges[i]); start, cur = edges[i][0], edges[i][2]
            while cur != start:
                nxt = next((j for j in by.get(cur, ()) if not used[j]), None)
                if nxt is None: break
                used[nxt] = True; out.append(edges[nxt]); cur = edges[nxt][2]
            if cur != start: out.append((cur, None, start))
        return out

    def _fill_edges(self, g):
        per = {}
        for f0, f1, l, a, c, e in g["edges"]:
            if f1: per.setdefault(f1, []).append((a, c, e))
            if f0: per.setdefault(f0, []).append((e, c, a))
        return per

    def shape(self, cid):
        """-> (def id, bbox). The def is a <g> of fill paths then stroke paths."""
        if cid in self._shape: return self._shape[cid]
        bb, groups = self._parse_shape(cid)
        out = []
        for g in groups:
            for fi, edges in sorted(self._fill_edges(g).items()):
                if fi - 1 >= len(g["fills"]): continue
                st = g["fills"][fi - 1]
                d = self._d(self._loops(edges), True)
                if st[0] == "solid":
                    cls, attr = _paint("f", st[1], self.pal)
                    if st[1][3] == 0: continue
                elif st[0] == "bitmap":
                    pid = self._bitmap(st[1])
                    if not pid: continue
                    self._grad += 1; gid = "%sr%d" % (self.px, self._grad)
                    self.defs[gid] = ('<pattern id="%s" patternUnits="userSpaceOnUse" width="%d" height="%d" patternTransform="matrix(%s)">'
                                      '<use href="#%s"/></pattern>' % ((gid,) + self._bm[st[1]] + (" ".join(_n(v) for v in st[2]), pid)))
                    cls, attr = None, ' fill="url(#%s)"' % gid
                else:
                    cls, attr = None, ' fill="url(#%s)"' % self._gradient(st)
                out.append('<path%s%s d="%s"/>' % (' class="%s"' % cls if cls else "", attr, d))
            per_l = {}
            for f0, f1, l, a, c, e in g["edges"]:
                if l: per_l.setdefault(l, []).append((a, c, e))
            for li, segs in sorted(per_l.items()):
                if li - 1 >= len(g["lines"]): continue
                w, col = g["lines"][li - 1]
                if col[3] == 0: continue
                cls, attr = _paint("s", col, self.pal)
                out.append('<path class="ln%s" stroke-width="%d"%s d="%s"/>' % (" " + cls if cls else "", max(w, 20), attr,
                                                                                 self._d(segs, False)))
        sid = "%sh%d" % (self.px, cid)
        self.defs[sid] = '<g id="%s">%s</g>' % (sid, "".join(out))
        self._shape[cid] = (sid, bb)
        return self._shape[cid]

    def _gradient(self, st):
        kind, m, stops = st
        self._grad += 1; gid = "%sr%d" % (self.px, self._grad)
        ss = []
        for r, c in stops:
            g = _grey(c) if self.pal else None
            col = "var(--p%d)" % g if g is not None else "#%02x%02x%02x" % c[:3]
            op = ";stop-opacity:%s" % _n(c[3] / 255) if c[3] < 255 else ""
            ss.append('<stop offset="%s" style="stop-color:%s%s"/>' % (_n(r / 255), col, op))
        geo = 'x1="-16384" x2="16384"' if kind == "linear" else 'cx="0" cy="0" r="16384"'
        self.defs[gid] = '<%sGradient id="%s" gradientUnits="userSpaceOnUse" %s gradientTransform="matrix(%s)">%s</%sGradient>' % (
            kind, gid, geo, " ".join(_n(v) for v in m), "".join(ss), kind)
        return gid

    # ---------------------------------------------------------------- sprites

    def frames(self, cid):
        if cid not in self._nfr:
            _, p, ln, _c = self.chars[cid]
            self._nfr[cid] = max(1, sum(1 for code, _p, _l in tags(self.b, p, p + ln) if code == 1))
        return self._nfr[cid]

    def labels(self, cid):
        """Frame labels of a sprite: {label: 0-based frame}."""
        key = ("labels", cid)
        if key not in self._nfr:
            _, p, ln, _c = self.chars[cid]; f = 0; out = {}
            for code, q, _l in tags(self.b, p, p + ln):
                if code == 1: f += 1
                elif code == 43: out.setdefault(self.b[q:self.b.index(0, q)].decode("utf-8", "replace"), f)
            self._nfr[key] = out
        return self._nfr[key]

    def display_list(self, cid, frame):
        key = (cid, frame)
        if key in self._dl: return self._dl[key]
        _, p0, ln0, _c = self.chars[cid]
        dl = {}; f = 0
        for code, p, ln in tags(self.b, p0, p0 + ln0):
            if code in (26, 70):
                bs = Bits(self.b, p); fl = bs.u8(); fl2 = bs.u8() if code == 70 else 0
                depth = bs.u16()
                if fl2 & 0x08: bs.cstr()
                e = dict(dl[depth]) if fl & 1 and depth in dl else {"cid": None, "m": ID, "cx": None, "name": "", "clip": 0}
                if fl & 0x02: e["cid"] = bs.u16()
                if fl & 0x04: e["m"] = bs.matrix()
                if fl & 0x08: e["cx"] = bs.cxform()
                if fl & 0x10: bs.u16()
                if fl & 0x20: e["name"] = bs.cstr()
                if fl & 0x40: e["clip"] = bs.u16()
                dl[depth] = e
            elif code == 28: dl.pop(self.b[p] | self.b[p + 1] << 8, None)
            elif code == 5: dl.pop(self.b[p + 2] | self.b[p + 3] << 8, None)
            elif code == 1:
                if f == frame: break
                f += 1
        self._dl[key] = [dl[d] | {"depth": d} for d in sorted(dl)]
        return self._dl[key]

    def _clip_paths(self, cid, frame, m, depth=0):
        """A mask layer flattened to <path>s (fills only, like Flash) in the parent's space."""
        kind = self.chars.get(cid, (None,))[0]
        if kind == "shape":
            bb, groups = self._parse_shape(cid)
            edges = [e for g in groups for _fi, es in sorted(self._fill_edges(g).items()) for e in es]
            return ['<path%s d="%s"/>' % (_tf(m), self._d(self._loops(edges), True))], box_of(m, bb)
        out, bb = [], None
        if kind == "sprite" and depth < 8:
            for e in self.display_list(cid, min(frame, self.frames(cid) - 1)):
                if e["cid"] is None or e["clip"]: continue
                o, b = self._clip_paths(e["cid"], 0, mul(m, e["m"]), depth + 1)
                out += o; bb = union(bb, b)
        return out, bb

    def clip(self, cid, frame, m):
        key = (cid, frame, m)
        if key not in self._clip:
            paths, bb = self._clip_paths(cid, frame, m)
            cid_ = "%sc%d" % (self.px, len(self._clip))
            self.defs[cid_] = '<clipPath id="%s">%s</clipPath>' % (cid_, "".join(paths))
            self._clip[key] = (cid_, bb)
        return self._clip[key]

    def _fx(self, cx):
        """Colour transform of a placement: plain opacity, or an feColorMatrix filter def."""
        if not cx or cx == (1.0, 1.0, 1.0, 1.0, 0, 0, 0, 0): return ""
        if cx[:3] == (1.0, 1.0, 1.0) and not any(cx[4:]): return ' opacity="%s"' % _n(max(0.0, min(1.0, cx[3])))
        if cx not in self._cx:
            fid = "%sx%d" % (self.px, len(self._cx)); z = ["0"] * 4
            rows = [" ".join(z[:i] + [_n(cx[i])] + z[i + 1:] + [_n(cx[4 + i] / 255)]) for i in range(4)]
            self.defs[fid] = ('<filter id="%s" color-interpolation-filters="sRGB"><feColorMatrix type="matrix" values="%s"/></filter>'
                              % (fid, " ".join(rows)))
            self._cx[cx] = fid
        return ' filter="url(#%s)"' % self._cx[cx]

    def draw(self, cid, frame, ov=None, depth=0):
        """-> (markup in the character's own space, bbox, touched by overrides)."""
        kind = self.chars.get(cid, (None,))[0]
        if kind == "shape":
            sid, bb = self.shape(cid)
            return '<use href="#%s"/>' % sid, bb, False
        if kind != "sprite" or depth > 12: return "", None, False
        frame = max(0, min(frame, self.frames(cid) - 1))
        key = (cid, frame)
        if key in self._sprite and not (ov and not self._names[key].isdisjoint(ov)): return self._sprite[key]
        out, bb, dirty = [], None, False
        names = self._names.setdefault(key, set())
        open_clips = []                                   # (until depth, bbox before the clipped run)
        for e in self.display_list(cid, frame):
            while open_clips and e["depth"] > open_clips[-1][0]:
                out.append("</g>"); bb = open_clips.pop()[1]      # clipped content cannot grow the box
            if e["cid"] is None: continue
            ccid, cfr, m, extra, doc = e["cid"], 0, e["m"], None, self
            names.add(e["name"] or "#%d" % ccid)
            o = ov.get(e["name"] or "#%d" % ccid) if ov else None      # by instance name, else "#<character id>"
            if o is not None:
                dirty = True
                if o.get("hide"): continue
                if "raw" in o:
                    out.append("<g%s%s>%s</g>" % (_tf(m), self._fx(e["cx"]), o["raw"])); continue
                if o.get("sym"): doc = o.get("doc", self); ccid = doc.sym[o["sym"]]
                cfr = o.get("frame", 0); extra = o.get("extra")
                if o.get("pos"): m = (-1.0 if m[0] < 0 else 1.0, 0.0, 0.0, 1.0, m[4], m[5])
            if e["clip"]:
                cl, cbb = doc.clip(ccid, cfr, m)
                bb = union(bb, cbb)
                out.append('<g clip-path="url(#%s)">' % cl); open_clips.append((e["clip"], bb))
                continue
            for xc, xf in ((ccid, cfr),) + ((extra,) if extra else ()):
                mk, b, dt = doc.draw(xc, xf, ov, depth + 1)
                dirty |= dt
                if doc.chars.get(xc, ("",))[0] == "sprite":
                    names |= doc._names.get((xc, max(0, min(xf, doc.frames(xc) - 1))), set())
                if not mk: continue
                bb = union(bb, box_of(m, b))
                op = self._fx(e["cx"])
                if o and o.get("cls"): op += ' class="%s"' % o["cls"]      # a hook for the page's CSS
                if mk.startswith("<use ") and mk.count("<") == 1: out.append(mk[:-2] + _tf(m) + op + "/>")
                else: out.append("<g%s%s>%s</g>" % (_tf(m), op, mk))
        while open_clips: out.append("</g>"); bb = open_clips.pop()[1]
        mk = "".join(out)
        if dirty or not mk: return mk, bb, dirty
        gid = "%sg%d_%d" % (self.px, cid, frame)
        self.defs[gid] = '<g id="%s">%s</g>' % (gid, mk)
        self._sprite[key] = ('<use href="#%s"/>' % gid, bb, False)
        return self._sprite[key]


class Faces:
    """Cat art for a game install: faces (catparts.swf) and whole cats in the pose of the game's
    own family tree card (familytree.swf, optional)."""

    def __init__(self, swf_bytes, palette_png, tree_swf=None, ui_swf=None, abil_swf=None):
        self.defs = {}            # id -> markup, insertion-ordered, shared by all cats
        self.parts = Swf(swf_bytes, self.defs, "p", True)
        if PLACEMENTS not in self.parts.sym: raise ValueError("catparts.swf: no " + PLACEMENTS)
        self.sym, self.frames, self.draw = self.parts.sym, self.parts.frames, self.parts.draw
        self.tree = Swf(tree_swf, self.defs, "t", False) if tree_swf else None
        self.ui = Swf(ui_swf, self.defs, "u", False) if ui_swf else None
        self.abil = Swf(abil_swf, self.defs, "a", False) if abil_swf else None
        self.rows = read_png_rows(palette_png)
        self.used_pal = set()
        self._face, self._ov = {}, {}

    def face(self, look):
        """look: dict(head, lear, rear, leye, reye, lbrow, rbrow, mouth, tex, palette), 1-based part
        indices as stored in the save (<= 0: the part is missing). -> {"vb": viewBox, "g": markup, "pal": row}."""
        key = tuple(sorted(look.items()))
        if key in self._face: return self._face[key]

        def part(sym, idx, pos=False, brow=0):
            if idx <= 0 or idx > self.frames(self.sym[sym]): return {"hide": True}
            o = {"sym": sym, "frame": idx - 1, "pos": pos}
            if brow > 0: o["extra"] = (self.sym["CatEyebrow"], brow - 1)
            return o

        ov = {"tex": {"frame": max(0, look["tex"] - 1)}, "scars": {"hide": True},
              "greyhair": {"hide": True}, "wrinkles": {"hide": True},      # age layers inside tex
              "lear": part("CatEar", look["lear"]), "rear": part("CatEar", look["rear"]),
              "leye": part("CatEye", look["leye"], True, look["lbrow"]),
              "reye": part("CatEye", look["reye"], True, look["rbrow"]),
              "mouth": part("CatMouth", look["mouth"], True),
              "ahead": {"hide": True}, "aface": {"hide": True}, "aneck": {"hide": True}}
        mk, bb, _ = self.draw(self.sym[PLACEMENTS], max(0, look["head"] - 1), ov)
        if not mk or bb is None:
            self._face[key] = None; return None
        self._ov[key] = ov
        x0, y0, x1, y1 = bb
        side = max(x1 - x0, y1 - y0) * 1.04                 # square box, a little air for the outline
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        pal = look["palette"] if 0 <= look["palette"] < len(self.rows) else 0
        self.used_pal.add(pal)
        self._face[key] = {"vb": "%d %d %d %d" % (cx - side / 2, cy - side / 2, side, side), "g": mk, "pal": pal}
        return self._face[key]

    def body(self, look, parts):
        """The whole cat in the pose of the family tree card of the game (`cat` clip of
        FamilyTreePortrait: markers tail, leg2, arm2, body, leg1, arm1, head; arms are CatLeg
        frames too). parts: part indices from the save. -> {"vb", "g"}; in "g" the head is the
        placeholder HEAD (the face() markup goes there), or None."""
        f = self.face(look)
        if not f or not self.tree or RIG not in self.tree.sym: return None

        def part(sym, idx):
            if idx <= 0 or idx > self.frames(self.sym[sym]): return {"hide": True}
            return {"sym": sym, "doc": self.parts, "frame": idx - 1}

        ov = dict(self._ov[tuple(sorted(look.items()))])
        ov.update({"tail": part("CatTail", parts["tail"]), "body": part("CatBody", parts["body"]),
                   "leg1": part("CatLeg", parts["leg1"]), "leg2": part("CatLeg", parts["leg2"]),
                   "arm1": part("CatLeg", parts["arm1"]), "arm2": part("CatLeg", parts["arm2"]),
                   "head": part(PLACEMENTS, parts["head"]), "aux": {"hide": True}})
        mk, bb, _ = self.tree.draw(self.tree.sym[RIG], 0, ov)
        if not mk or bb is None or f["g"] not in mk: return None
        x0, y0, x1, y1 = bb
        side = max(x1 - x0, y1 - y0) * 1.04; cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        return {"vb": "%d %d %d %d" % (cx - side / 2, cy - side / 2, side, side), "g": mk.replace(f["g"], HEAD, 1)}

    def card(self):
        """The family tree card of the game around the cat: {"vb", "tpl": [male, female, neutral]
        markup with BG and CAT placeholders, "bgs": the backdrops, "plate": name plate x, y, width}."""
        t = self.tree
        if not t or CARD not in t.sym or RIG not in t.sym: return None
        cid = t.sym[CARD]; rig = "#%d" % t.sym[RIG]
        bgc = next((e["cid"] for e in t.display_list(cid, 0) if e["name"] == "bg"), None)
        if bgc is None: return None
        tpl, box = [], None
        for fr in (0, 2, 4):                                  # labels male / female / neutral
            mk, bb, _ = t.draw(cid, fr, {"bg": {"raw": BG}, rig: {"raw": CAT}, "fg": {"cls": "frm"}})
            tpl.append(mk); box = union(box, bb)
        bgs = [t.draw(bgc, k)[0] for k in range(t.frames(bgc))]
        plate = None
        for e in t.display_list(cid, 0):                      # the small sprite under the frame = name plate
            if e["cid"] is not None and not e["name"] and e["depth"] > 155:
                b = box_of(e["m"], t.draw(e["cid"], 0)[1])
                if b: plate = [int((b[0] + b[2]) / 2), int((b[1] + b[3]) / 2), int(b[2] - b[0])]
        x0, y0, x1, y1 = box
        return {"vb": "%d %d %d %d" % (x0, y0, x1 - x0, y1 - y0), "tpl": tpl, "bgs": bgs, "plate": plate}

    def stat_icons(self, stats):
        """The stat glyphs of the game (swfs/ui.swf FontIcon_<stat>) as [viewBox, markup] per stat, or
        None. They are white there, tinted by the text colour; here they take currentColor."""
        u = self.ui
        if not u or any("FontIcon_" + s not in u.sym for s in stats): return None
        out = []
        for s in stats:
            mk, bb, _ = u.draw(u.sym["FontIcon_" + s], 0)
            if not mk or bb is None: return None
            out.append(["%d %d %d %d" % (bb[0], bb[1], bb[2] - bb[0] + 1, bb[3] - bb[1] + 1), mk])
        self._mono()
        return out

    def _mono(self):
        """The ui.swf font icons are black shapes whitened by a filter: make them take currentColor."""
        for k in [k for k in self.defs if k.startswith(("uh", "ug"))]:
            self.defs[k] = re.sub(r' filter="url\(#ux\d+\)"', "", self.defs[k]).replace('fill="#000000"', 'fill="currentColor"').replace('fill="#ffffff"', 'fill="currentColor"')

    @staticmethod
    def _icon(doc, cid, frame):
        mk, bb, _ = doc.draw(cid, frame, {"sloticon": {"hide": True}, "label": {"hide": True}})
        if not mk or bb is None: return None
        return ["%d %d %d %d" % (bb[0], bb[1], bb[2] - bb[0] + 1, bb[3] - bb[1] + 1), mk]

    def font_icon(self, name, prefix="FontIcon_"):
        """ui.swf FontIcon_<name> (stats, classes, male / female / neutral), in currentColor."""
        u = self.ui
        if not u or prefix + name not in u.sym: return None
        ic = self._icon(u, u.sym[prefix + name], 0); self._mono()
        return ic

    def label_icon(self, symbol, label):
        """ability_icons.swf: the frame of AbilityIcon / PassiveIcon labelled with the ability's id."""
        a = self.abil
        if not a or symbol not in a.sym: return None
        fr = a.labels(a.sym[symbol]).get(label)
        return None if fr is None else self._icon(a, a.sym[symbol], fr)

    def item_icon(self, kind, frame):
        """catparts.swf <Slot>Icon, frame = the item's GON `frame` - 1."""
        sym = {"head": "HeadItemIcon", "face": "FaceItemIcon", "neck": "NeckItemIcon", "weapon": "WeaponIcon",
               "trinket": "TrinketIcon"}.get(kind)
        if not sym or sym not in self.sym or not 0 < frame <= self.frames(self.sym[sym]): return None
        return self._icon(self.parts, self.sym[sym], frame - 1)

    def wallpaper(self):
        """The family tree wallpaper bitmap as a PNG data URI, or None."""
        t = self.tree
        if not t or "FamilyTreeWallpaper" not in t.sym: return None
        try:
            for e in t.display_list(t.sym["FamilyTreeWallpaper"], 0):
                for g in t._parse_shape(e["cid"])[1]:
                    for st in g["fills"]:
                        c = t.chars.get(st[1]) if st[0] == "bitmap" else None
                        if c and c[0] == "bitmap":
                            return "data:image/png;base64," + base64.b64encode(swf_bitmap_png(t.b, c[1], c[2], c[3])[0]).decode()
        except Exception:
            pass
        return None

    def css(self):
        out = [".ln{fill:none;stroke-linecap:round;stroke-linejoin:round}"]
        out += [".f%d{fill:var(--p%d)}.s%d{stroke:var(--p%d)}" % (i, i, i, i) for i in range(16)]
        for r in sorted(self.used_pal):
            out.append(".pal%d{%s}" % (r, ";".join("--p%d:#%02x%02x%02x" % ((i,) + c) for i, c in enumerate(self.rows[r]))))
        return "".join(out)

    def defs_svg(self):
        return "<defs>%s</defs>" % "".join(self.defs.values())


def read_png_rows(data):
    """Rows of RGB tuples from an 8-bit, non-interlaced PNG (textures/palette.png: 16 x 256)."""
    if data[:8] != b"\x89PNG\r\n\x1a\n": raise ValueError("palette.png: not a PNG")
    pos = 8; idat = b""; plte = None
    while pos < len(data):
        ln, typ = struct.unpack_from(">I4s", data, pos)
        body = data[pos + 8:pos + 8 + ln]; pos += 12 + ln
        if typ == b"IHDR": w, h, depth, ctype, _c, _f, inter = struct.unpack(">IIBBBBB", body)
        elif typ == b"PLTE": plte = body
        elif typ == b"IDAT": idat += body
        elif typ == b"IEND": break
    if depth != 8 or inter: raise ValueError("palette.png: unsupported PNG flavour")
    bpp = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[ctype]
    raw = zlib.decompress(idat); stride = w * bpp
    prev = bytearray(stride); rows = []; p = 0
    for _ in range(h):
        ft = raw[p]; line = bytearray(raw[p + 1:p + 1 + stride]); p += 1 + stride
        for i in range(stride):
            a = line[i - bpp] if i >= bpp else 0; b = prev[i]; c = prev[i - bpp] if i >= bpp else 0
            if ft == 1: line[i] = (line[i] + a) & 255
            elif ft == 2: line[i] = (line[i] + b) & 255
            elif ft == 3: line[i] = (line[i] + (a + b) // 2) & 255
            elif ft == 4:
                pa, pb, pc = abs(b - c), abs(a - c), abs(a + b - 2 * c)
                line[i] = (line[i] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        prev = line
        if ctype == 3: rows.append([tuple(plte[3 * v:3 * v + 3]) for v in line])
        elif ctype in (2, 6): rows.append([tuple(line[i * bpp:i * bpp + 3]) for i in range(w)])
        else: rows.append([(line[i * bpp],) * 3 for i in range(w)])
    return rows


def look_of(cat):
    """Appearance of a mewsave cat as face() wants it."""
    p = cat["parts"]
    return {"head": p["head"], "lear": p["leftear"], "rear": p["rightear"], "leye": p["lefteye"], "reye": p["righteye"],
            "lbrow": p["lefteyebrow"], "rbrow": p["righteyebrow"], "mouth": p["mouth"],
            "tex": cat["texture"], "palette": cat["palette"]}


def swf_bitmap_png(b, p, ln, code):
    """DefineBitsLossless(2), 32-bit -> (PNG bytes, w, h). Lossless2 pixels are premultiplied ARGB."""
    fmt = b[p + 2]; w, h = struct.unpack_from("<HH", b, p + 3)
    if fmt != 5: raise ValueError("bitmap format %d" % fmt)
    raw = zlib.decompress(b[p + 7:p + ln]); n = w * h
    px = bytearray(n * 4)
    a = raw[0:n * 4:4] if code == 36 else b"\xff" * n
    for k in range(3): px[k::4] = raw[k + 1:n * 4:4]
    px[3::4] = a
    if code == 36:
        for i, v in enumerate(a):
            if 0 < v < 255:
                for k in range(3): px[4 * i + k] = min(255, px[4 * i + k] * 255 // v)
    rows = b"".join(b"\x00" + bytes(px[y * w * 4:(y + 1) * w * 4]) for y in range(h))
    def chunk(t, d): return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d))
    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0)) + \
        chunk(b"IDAT", zlib.compress(rows, 9)) + chunk(b"IEND", b"")
    return png, w, h
