"""Mewgenics family tree -> one self-contained HTML page.

    python build_tree.py                 # finds the save, opens the page in a browser
    python build_tree.py --watch         # rebuild whenever the game writes the save
    python build_tree.py --pick          # choose another account / save (remembered)
    python build_tree.py --list          # show every save that was found
    python build_tree.py --save X.sav --out tree.html --no-open
    MewTree.exe                          # same as --watch; drag a .sav onto it to use that one

Reads a COPY of the save (never writes it). If the game folder is found, Russian
names and descriptions of abilities, passives, items and mutations are pulled
from resources.gpak (only the few text/data entries are read, not the whole 5 GB),
and every cat gets its real face and body, composed from the game's catparts.swf the
way the game does it, inside the game's own family tree card (catface.py).
"""
import argparse, base64, csv, io, json, os, re, struct, sys, time, webbrowser
from pathlib import Path

VERSION = "1.0.0"
FROZEN = getattr(sys, "frozen", False)                       # PyInstaller one-file exe


def os_lang():
    """'ru' on a Russian system, else 'en' (MEWTREE_LANG overrides). Console messages follow it;
    the page has its own switch and only starts in this language."""
    v = os.environ.get("MEWTREE_LANG", "").lower()[:2]
    if v in ("ru", "en"): return v
    try:
        if sys.platform == "win32":
            import ctypes
            return "ru" if ctypes.windll.kernel32.GetUserDefaultUILanguage() & 0x3FF == 0x19 else "en"
        import locale
        return "ru" if (locale.getlocale()[0] or os.environ.get("LANG", "")).lower().startswith("ru") else "en"
    except Exception:
        return "en"


LANG = os_lang()
tr = lambda ru, en: ru if LANG == "ru" else en
HERE = Path(__file__).resolve().parent
RES = Path(getattr(sys, "_MEIPASS", HERE))                    # bundled template.html
APP = Path(sys.executable).resolve().parent if FROZEN else HERE   # where output + settings live
sys.path.insert(0, str(HERE))
import mewsave, locate, catface, mewfont

CLASS_RU = {"Colorless": "Бесцветный", "Fighter": "Боец", "Hunter": "Охотник", "Mage": "Маг",
            "Tank": "Танк", "Medic": "Медик", "Thief": "Вор", "Necromancer": "Некромант",
            "Butcher": "Мясник", "Druid": "Друид", "Psychic": "Псионик", "Monk": "Монах",
            "Tinkerer": "Механик", "Jester": "Шут"}
# body part -> data/mutations/<file>.gon (arms share legs.gon), see mewgenics-cat-bridge
MUT_FILE = {"body": "body", "head": "head", "tail": "tail", "leg1": "legs", "leg2": "legs",
            "arm1": "legs", "arm2": "legs", "lefteye": "eyes", "righteye": "eyes",
            "lefteyebrow": "eyebrows", "righteyebrow": "eyebrows", "leftear": "ears",
            "rightear": "ears", "mouth": "mouth"}
SLOT = {"body": "body", "head": "head", "tail": "tail", "leg1": "legs", "leg2": "legs", "arm1": "arms",
        "arm2": "arms", "lefteye": "eyes", "righteye": "eyes", "lefteyebrow": "eyebrows",
        "righteyebrow": "eyebrows", "leftear": "ears", "rightear": "ears", "mouth": "mouth"}


# ------------------------------------------------------------------ game data (gpak + GON)

def read_gpak(path, want):
    """{name: bytes} for entries where want(name). gpak: u32 n, n x {u16 len, name, u32 size}, data."""
    out = {}
    with open(path, "rb") as f:
        (n,) = struct.unpack("<I", f.read(4)); idx = []
        for _ in range(n):
            (l,) = struct.unpack("<H", f.read(2)); name = f.read(l).decode("utf-8", "replace")
            (size,) = struct.unpack("<I", f.read(4)); idx.append((name, size))
        off = f.tell()
        for name, size in idx:
            if want(name):
                f.seek(off); out[name] = f.read(size)
            off += size
    return out


def _tokens(t):
    i, n = 0, len(t)
    while i < n:
        c = t[i]
        if c.isspace() or c == ",": i += 1
        elif t.startswith("//", i):
            i = t.find("\n", i); i = n if i < 0 else i
        elif t.startswith("/*", i):
            i = t.find("*/", i + 2); i = n if i < 0 else i + 2
        elif c in "{}[]": yield c; i += 1
        elif c == '"':
            j = i + 1
            while j < n and t[j] != '"': j += 2 if t[j] == "\\" else 1
            yield t[i + 1:j]; i = j + 1
        else:
            j = i
            while j < n and not t[j].isspace() and t[j] not in '{}[],"' and not t.startswith("//", j): j += 1
            yield t[i:j]; i = j


def parse_gon(text):
    toks = list(_tokens(text)); pos = 0
    def val():
        nonlocal pos
        tk = toks[pos]; pos += 1
        if tk == "{": return obj("}")
        if tk == "[":
            out = []
            while toks[pos] != "]": out.append(val())
            pos += 1; return out
        return tk
    def obj(end):
        nonlocal pos
        r = {}
        while pos < len(toks) and toks[pos] != end:
            k = toks[pos]; pos += 1; r[k] = val()
        pos += 1; return r
    return obj(None)


def clean(s, rich=False):
    """Game text without its markup. rich: [img:str] stays as the marker \x02str\x02, which the page
    turns into the game's glyph; otherwise it becomes the word STR."""
    s = re.sub(r"\[img:([A-Za-z_0-9]+)\]", (lambda m: "\x02%s\x02" % m.group(1)) if rich else (lambda m: m.group(1).upper()), s or "")
    s = re.sub(r"\[/?[a-z]+(:[^\]]*)?\]", "", s)
    return s.replace("\\n", " ").replace("\n", " ").strip()


class GameText:
    def __init__(self, gpak):
        self.ok = False; self.err = None
        self.text, self.abil, self.pas, self.items, self.mut = {}, {}, {}, {}, {}
        self.text_en, self.en = {}, False            # self.text is Russian (English where a line has no translation)
        if not gpak:
            self.err = tr("игра не найдена", "game not found"); return
        try:
            raw = read_gpak(gpak, lambda n: n == "data/text/combined.csv" or (n.endswith(".gon") and n.startswith(
                ("data/abilities/", "data/passives/", "data/items/", "data/mutations/"))))
        except OSError as e:
            self.err = str(e); return
        csvb = raw.pop("data/text/combined.csv", None)
        if csvb:
            rows = list(csv.reader(io.StringIO(csvb.decode("utf-8-sig"))))
            h = rows[0]; en = h.index("en"); ru = h.index("ru") if "ru" in h else en
            self.text = {r[0]: (r[ru] if len(r) > ru and r[ru] else r[en]) for r in rows[1:] if len(r) > en}
            self.text_en = {r[0]: r[en] for r in rows[1:] if len(r) > en}
        for name, b in raw.items():
            try:
                g = parse_gon(b.decode("utf-8", "replace"))
            except Exception:
                continue
            for key, block in g.items():
                if not isinstance(block, dict): continue
                if name.startswith("data/abilities/"): self.abil[key] = block
                elif name.startswith("data/passives/"): self.pas[key] = block
                elif name.startswith("data/items/"): self.items[key] = block
                else:  # mutations: one block per group, ids inside
                    self.mut[key] = {int(k): v for k, v in block.items() if k.lstrip("-").isdigit() and isinstance(v, dict)}
        self.ok = bool(self.text)

    def t(self, key, rich=False):
        return clean((self.text_en if self.en else self.text).get(key, ""), rich) if key else ""

    def in_en(self, f, *a):
        """f(*a) with the English texts, e.g. G.in_en(G.ability, key)."""
        self.en = True
        try: return f(*a)
        finally: self.en = False

    def class_name(self, cls):
        """The game's own name of a class (Colorless is "Collarless", Medic is "Cleric")."""
        return self.t(f"CAT_CLASS_{cls.upper()}_NAME") or (cls if self.en else CLASS_RU.get(cls, cls))

    def ability(self, k):
        b = self.abil.get(k) or {}; m = b.get("meta") or {}
        return self.t(m.get("name")) or human(k), self.t(m.get("desc"), True)

    def passive(self, k, tier):
        b = self.pas.get(k) or {}
        lvl = b.get(str(tier)) if isinstance(b.get(str(tier)), dict) else {}
        name = self.t(b.get("name")) or human(k)
        return name, self.t(lvl.get("desc") or b.get("desc"), True), (b.get("class") or "") == "Disorder"

    def item(self, k):
        b = self.items.get(k) or {}; m = b.get("meta") if isinstance(b.get("meta"), dict) else {}
        for cand in (b.get("name"), m.get("name"), f"ITEM_{k.upper()}_NAME", f"{k.upper()}_NAME"):
            if cand and self.t(cand): return self.t(cand), self.t(b.get("desc") or m.get("desc") or f"ITEM_{k.upper()}_DESC", True)
        return human(k), ""

    def quotes(self):
        """What cats say in the game (CAT_<moment>_QUOTES_<CLASS>_<n>), per class key as in the save."""
        names = {k.upper(): k for k in CLASS_RU}
        out = {}
        for key in self.text:
            m = re.fullmatch(r"CAT_[A-Z_]+?_QUOTES_([A-Z]+)_\d+", key)
            q = self.t(key) if m and m.group(1) in names else ""
            if q and "{" not in q and q not in out.setdefault(names[m.group(1)], []):
                out[names[m.group(1)]].append(q)
        return out

    def sticky(self, k):
        """Class gear the cat is born into and cannot take off (ButcherHook, MonkFist...)."""
        return (self.items.get(k) or {}).get("sticky") == "true"

    def npc_names(self):
        """Status flag bit -> who the cat was given to, in the game's language."""
        keys = {11: ("NPC_NAME_BEANIES", "Доктор Бинис", "Dr. Beanies"), 12: ("NPC_NAME_BUTCH", "Бутч", "Butch"),
                13: ("NPC_NAME_TINK", "Тинк", "Tink"), 14: ("NPC_NAME_TRACY", "Трейси", "Tracy"),
                15: ("EVENT_ORGANGRINDER_NAME", "Шарманщик", "Organ Grinder"), 16: ("NPC_NAME_FRANK", "Фрэнк", "Frank"),
                17: ("NPC_NAME_JACK", "Малыш Джек", "Baby Jack")}
        return {b: self.t(k) or (en if self.en else ru) for b, (k, ru, en) in keys.items()}

    def mutation(self, part, idx):
        if idx == -2:
            return (("missing part", "Birth defect: the body part is missing", True) if self.en else
                    ("нет части", "Врождённый дефект: часть тела отсутствует", True))
        b = self.mut.get(MUT_FILE[part], {}).get(idx) or {}
        return self.t(b.get("name")) or "", self.t(b.get("desc"), True), b.get("tag") == "birth_defect"


def human(k):
    k = re.sub(r"(\d+)$", r" \1", k or "")
    return re.sub(r"(?<=[a-z])(?=[A-Z])", " ", k).replace("_", " ").strip()


# ------------------------------------------------------------------ cat faces

_faces = {}


def cat_faces(gpak):
    """catface.Faces for this game install (parsed once, reused by --watch), or (None, why)."""
    key = str(gpak) if gpak else None
    if key not in _faces:
        try:
            if not gpak: raise ValueError(tr("игра не найдена", "game not found"))
            raw = read_gpak(gpak, lambda n: n in ("swfs/catparts.swf", "textures/palette.png", "swfs/familytree.swf",
                                                  "swfs/ui.swf", "swfs/ability_icons.swf"))
            _faces[key] = (catface.Faces(raw["swfs/catparts.swf"], raw["textures/palette.png"],
                                         raw.get("swfs/familytree.swf"), raw.get("swfs/ui.swf"),
                                         raw.get("swfs/ability_icons.swf")), None)
        except Exception as e:
            _faces[key] = (None, str(e) or type(e).__name__)
    return _faces[key]


_fonts = {}


def game_font(gpak):
    """The game's body font (TikaFontIntl, has Cyrillic) as base64 TrueType, or None. Parsed once."""
    key = str(gpak) if gpak else None
    if key not in _fonts:
        try:
            raw = read_gpak(gpak, lambda n: n == "swfs/international_fonts.swf")["swfs/international_fonts.swf"]
            f = mewfont.read_fonts(raw, ["TikaFontIntl"])["TikaFontIntl"]
            _fonts[key] = base64.b64encode(mewfont.to_ttf(f, "Mewgenics Tika")).decode()
        except Exception:
            _fonts[key] = None
    return _fonts[key]


# ------------------------------------------------------------------ build

def colony_numbers(S):
    """Counters the game keeps in the save's `properties` table, for the page's fun stats."""
    p = S.get("props") or {}
    num = lambda k: p.get(k) if isinstance(p.get(k), (int, float)) else None
    scum = [v for k, v in p.items() if k.startswith("NPCRSTRACKER_steven_savescum") and isinstance(v, int)]
    return {"birds": num("BonusBirdsKilled"), "flush": num("WorldEventLegacyCounter_ToiletFlushes"),
            "gold": num("house_gold"), "food": num("house_food"), "pct": num("save_file_percent"),
            "scum": sum(scum) if scum else None, "furn": S.get("furniture")}


_texts = {}


def game_text(gpak):
    key = str(gpak) if gpak else None
    if key not in _texts: _texts[key] = GameText(gpak)
    return _texts[key]


def build_save(save_path, gpak=None):
    """Everything the page needs about one save (the art and texts shared by all saves are added in build)."""
    S = mewsave.read_save(save_path)
    G = game_text(gpak)
    F, faces_err = cat_faces(gpak)
    lib = {}  # shared dictionary of ability/passive/item texts: key -> [name, desc, flag]
    lib_en = {}  # the same keys in English: key -> [name, desc]
    out = []
    for c in sorted(S["cats"].values(), key=lambda c: c["id"]):
        acts = []
        for k in c["actives"]:
            lib.setdefault("a:" + k, list(G.ability(k))); acts.append("a:" + k)
            lib_en.setdefault("a:" + k, list(G.in_en(G.ability, k)))
        lib.setdefault("a:" + c["basic"], list(G.ability(c["basic"])))
        lib_en.setdefault("a:" + c["basic"], list(G.in_en(G.ability, c["basic"])))
        pas = []
        for k, tier in c["passives"]:
            key = f"p:{k}:{tier}"; lib.setdefault(key, list(G.passive(k, tier))); pas.append(key)
            lib_en.setdefault(key, list(G.in_en(G.passive, k, tier))[:2])
        items = []
        for k in c["items"]:
            lib.setdefault("i:" + k, list(G.item(k)) + [False, G.sticky(k)]); items.append("i:" + k)
            lib_en.setdefault("i:" + k, list(G.in_en(G.item, k)))
        muts = {}
        for part, idx in c["parts"].items():
            if idx >= 300 or idx == -2:
                slot = SLOT[part]
                if (slot, idx) in muts: continue
                n, d, defect = G.mutation(part, idx)
                ne, de, _ = G.in_en(G.mutation, part, idx)
                muts[(slot, idx)] = [slot, idx, n, d, bool(defect or idx == -2), ne, de]
        bonus = [c["lvlup"][s] + c["inj"][s] for s in mewsave.STATS]
        face = body = None
        if F:
            try:
                f = F.face(catface.look_of(c)); face = f and [f["vb"], f["pal"], f["g"]]
                b = F.body(catface.look_of(c), c["parts"]); body = b and [b["vb"], b["g"]]
            except Exception as e:
                faces_err = faces_err or f"{tr('кот', 'cat')} {c['id']}: {e}"
        out.append({
            "id": c["id"], "n": c["name"] or f"#{c['id']}", "sex": c["sex"], "st": c["status"], "room": c["room"],
            "cls": c["cls"], "clsN": G.class_name(c["cls"]), "clsE": G.in_en(G.class_name, c["cls"]), "lvl": c["level"], "born": c["born"],
            "hp": c["hp"] if c["hp"] < 10 ** 6 else None, "p": c["parents"], "coi": round(c["coi"], 5),
            "base": [c["base"][s] for s in mewsave.STATS], "bonus": bonus,
            "basic": "a:" + c["basic"], "act": acts, "inn": ["a:" + k for k in c["innate"]], "pas": pas, "items": items,
            "mut": list(muts.values()),
            "look": [c["palette"], c["texture"], c["parts"]["lefteye"], c["parts"]["leftear"], c["parts"]["rightear"],
                     c["parts"]["head"], c["parts"]["tail"], c["parts"]["mouth"]],
            "face": face, "body": body, "inj": sum(c["inj"].values()), "voice": c["voice"],
            "fl": c["flags"] & 0xFFFFFF, "sx": round(c["sexuality"], 3), "lib": round(c["libido"], 3),
            "agg": round(c["aggression"], 3), "lover": c["lover"] if c["lover"] >= 0 else None,
            "hater": c["hater"] if c["hater"] >= 0 else None,
        })
    owner = (S.get("props") or {}).get("owner_steamid") or Path(save_path).resolve().parent.parent.name
    ico = {}                         # lib key -> the game's icon [viewBox, markup]
    for key in lib if F else ():
        kind, k = key.split(":")[:2]
        try:
            if kind == "a":
                b = G.abil.get(k) or {}
                base = b.get("variant_of") or (b.get("meta") or {}).get("variant_of") if isinstance(b.get("meta"), dict) else b.get("variant_of")
                ic = (F.label_icon("AbilityIcon", k) or (base and F.label_icon("AbilityIcon", base))
                      or F.label_icon("AbilityIcon", k.rstrip("0123456789")))        # Brainstorm2 -> Brainstorm
            elif kind == "p":
                ic = F.label_icon("PassiveIcon", k)
            else:
                b = G.items.get(k) or {}
                ic = F.item_icon(b.get("kind"), int(b.get("frame") or 0)) if str(b.get("frame") or "0").isdigit() else None
        except Exception:
            ic = None
        if ic: ico[key] = ic
    return {"ico": ico, "libEn": lib_en, "day": S["day"], "save": Path(save_path).name, "saveKey": f"{owner}/{Path(save_path).name}",
            "built": time.strftime("%Y-%m-%d %H:%M"), "lib": lib, "cats": out, "parseErrors": len(S["errors"]),
            "faces": sum(1 for c in out if c["face"]), "facesErr": faces_err, "fun": colony_numbers(S)}


def build(saves, default, gpak=None, force=None):
    """saves: [(path, label)], default: the path shown first -> (page html, page data, the default save's data).
    The page holds every save and switches between them itself; `force` (any new token) makes it
    drop the choice remembered in the browser and show `default`."""
    G = game_text(gpak)
    F, faces_err = cat_faces(gpak)
    per, main, seen = [], None, set()
    for path, label in saves:
        try:
            d = build_save(path, gpak)
        except Exception:
            if Path(path) == Path(default): raise
            continue                                         # a broken or foreign save must not hide the others
        if not d["cats"] and Path(path) != Path(default): continue   # empty test saves are just noise in the list
        while d["saveKey"] in seen: d["saveKey"] += "'"
        seen.add(d["saveKey"]); d["label"] = label; per.append(d)
        if Path(path) == Path(default): main = d
    data = {"saves": per, "def": main["saveKey"], "force": force, "texts": G.ok, "textsErr": G.err,
            "card": None, "wall": None, "statIcons": None, "uiIcons": None, "npc": G.npc_names(), "quotes": G.quotes(), "font": game_font(gpak),
            "npcEn": G.in_en(G.npc_names), "quotesEn": G.in_en(G.quotes), "lang": LANG, "ver": VERSION}
    if F:
        try:
            data["card"] = F.card(); data["wall"] = F.wallpaper()      # the game's own family tree art
            data["statIcons"] = F.stat_icons(mewsave.STATS)
            marks = set()                                   # [img:x] glyphs the descriptions mention
            for d in per:
                for v in list(d["lib"].values()) + list(d["libEn"].values()):
                    marks.update(re.findall("\x02(\\w+)\x02", v[1] or ""))
                for c in d["cats"]:
                    for m in c["mut"]: marks.update(re.findall("\x02(\\w+)\x02", m[3] or ""))
            img = {k: F.font_icon(k) or F.font_icon(k.capitalize()) or F.font_icon(k, "RawFontIcon_") for k in marks}
            data["uiIcons"] = {"cls": {c: F.font_icon("Cleric" if c == "Medic" else c) for c in CLASS_RU},
                               "sex": [F.font_icon(n) for n in ("male", "female", "neutral")],
                               "img": {k: v for k, v in img.items() if v}}
        except Exception as e:
            main["facesErr"] = faces_err or f"{tr('карточка', 'card')}: {e}"
    data["faceDefs"] = F.defs_svg() if F else ""; data["faceCss"] = F.css() if F else ""
    tpl = (RES / "template.html").read_text("utf-8")
    js = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    return tpl.replace("/*__MEWTREE_DATA__*/null", js), data, main


CONFIG = APP / "mewtree.json"


def _cfg():
    try:
        return json.loads(CONFIG.read_text("utf-8"))
    except (OSError, ValueError):
        return {}


def _save_cfg(d):
    try:
        CONFIG.write_text(json.dumps(d, ensure_ascii=False, indent=1), "utf-8")
    except OSError:
        pass


def choose_save(saves, pick=False):
    """Remembered save if still there; the only campaign save; otherwise ask (or take the newest)."""
    cfg = _cfg()
    if not pick and cfg.get("save") and Path(cfg["save"]).exists():
        return Path(cfg["save"]), tr("запомненный", "remembered")
    campaign = [s for s in saves if not s["test"]]
    if not pick and len(campaign) == 1:
        return campaign[0]["path"], tr("единственный", "the only one")
    if not sys.stdin or not sys.stdin.isatty():
        return saves[0]["path"], tr("самый свежий", "the newest")
    print(tr("\nНашёл несколько сейвов:", "\nFound several saves:"))
    for i, s in enumerate(saves, 1):
        print(f"  {i}. {locate.describe(s, lang=LANG)}")
    while True:
        ans = input(tr(f"Какой открыть? [1-{len(saves)}, Enter = 1]: ", f"Which one to open? [1-{len(saves)}, Enter = 1]: ")).strip()
        if not ans:
            ans = "1"
        if ans.isdigit() and 1 <= int(ans) <= len(saves):
            p = saves[int(ans) - 1]["path"]
            cfg["save"] = str(p); _save_cfg(cfg)
            print(tr("Запомнил. Сменить потом: --pick или список на странице", "Remembered. Change later: --pick, or the list on the page"))
            return p, tr("выбран", "picked")
        print(tr("Не понял, введи номер.", "Please type a number."))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("save_pos", nargs="?", help=argparse.SUPPRESS)       # drag & drop onto the exe
    ap.add_argument("--save"); ap.add_argument("--gpak"); ap.add_argument("--out", default=str(APP / "mewtree.html"))
    ap.add_argument("--watch", action="store_true"); ap.add_argument("--no-open", action="store_true")
    ap.add_argument("--pick", action="store_true", help=tr("выбрать аккаунт/сейв заново", "pick the account / save again"))
    ap.add_argument("--version", action="version", version="MewTree " + VERSION)
    ap.add_argument("--list", action="store_true", help=tr("показать все найденные сейвы и пути", "list every save found and where it looked"))
    a = ap.parse_args()
    if FROZEN and len(sys.argv) <= 2 and not a.list:
        a.watch = True                                   # double-click = live mode

    if a.list:
        print("Steam:", *(map(str, locate.steam_libraries()) or [tr("не найден", "not found")]), sep="\n  ")
        print(tr("Папки сейвов:", "Save folders:"), *(map(str, locate.save_roots()) or [tr("не найдены", "not found")]), sep="\n  ")
        for s in locate.find_saves():
            print("  -", locate.describe(s, lang=LANG), "\n     ", s["path"])
        print("resources.gpak:", locate.find_gpak() or tr("не найден", "not found"))
        return

    explicit = a.save or a.save_pos
    force = time.strftime("%Y%m%d%H%M%S") if explicit or a.pick else None   # an explicit choice beats the page's own
    if explicit:
        save, how = Path(explicit), tr("указан вручную", "given by hand")
    else:
        saves = locate.find_saves()
        if not saves:
            sys.exit(tr("Сейв не найден. Посмотри, где искал: --list. Или укажи путь: --save путь/к/steamcampaign01.sav\n"
                        "(можно просто перетащить .sav на MewTree.exe)",
                        "No save found. See where it looked: --list. Or give a path: --save path/to/steamcampaign01.sav\n"
                        "(you can also just drop a .sav onto MewTree.exe)"))
        save, how = choose_save(saves, a.pick)
    if not save.exists():
        sys.exit(tr(f"Нет такого файла: {save}", f"No such file: {save}"))
    gpak = Path(a.gpak) if a.gpak else locate.find_gpak()
    print(f"MewTree {VERSION}")
    print(f"{tr('Сейв', 'Save')} ({how}): {save}")
    print(tr("Игра: ", "Game: ") + str(gpak or tr("не найдена: без картинок и названий из игры", "not found: no art and no names from the game")))

    def entries():
        """Every save found (the page lets you switch between them), plus the one given by hand."""
        found = [(s["path"], locate.label(s)) for s in locate.find_saves()]
        if not any(p.resolve() == save.resolve() for p, _ in found):
            found.insert(0, (save, {"file": save.name}))
        return found

    def once():
        html, data, d = build(entries(), save, gpak, force)
        Path(a.out).write_text(html, "utf-8")
        d = dict(d, texts=data["texts"], textsErr=data["textsErr"], n=len(data["saves"]))
        alive = sum(c["st"] == "house" for c in d["cats"]); dead = sum(c["st"] == "dead" for c in d["cats"])
        err = f" ({d['facesErr']})" if d["facesErr"] else ""
        print(f"[{time.strftime('%H:%M:%S')}] " + tr(
            f"{len(d['cats'])} котов (дома {alive}, погибли {dead}), день {d['day']}, тексты игры: "
            f"{'да' if d['texts'] else 'нет (' + str(d['textsErr']) + ')'}, морды из игры: {d['faces']}{err}, "
            f"сейвов на странице: {d['n']}",
            f"{len(d['cats'])} cats ({alive} at home, {dead} dead), day {d['day']}, game texts: "
            f"{'yes' if d['texts'] else 'no (' + str(d['textsErr']) + ')'}, faces from the game: {d['faces']}{err}, "
            f"saves on the page: {d['n']}") + f" -> {a.out}")

    once()
    if not a.no_open:
        webbrowser.open(Path(a.out).resolve().as_uri())
    if a.watch:
        print(tr("Слежу за сейвами, закрой окно или Ctrl+C чтобы выйти. После сохранения в игре обнови вкладку (F5).\n"
                 "Сменить сейв можно прямо на странице (список под заголовком).",
                 "Watching the saves; close this window or press Ctrl+C to quit. After the game saves, refresh the tab (F5).\n"
                 "You can switch saves on the page itself (the list under the title)."))

        def stamp():
            out = {}
            for p, _ in entries():
                try: out[str(p)] = p.stat().st_mtime
                except OSError: pass
            return out

        last = stamp()
        while True:
            time.sleep(3)
            m = stamp()
            if m != last:
                time.sleep(1); last = stamp()
                try: once()
                except Exception as e: print(tr("не смог прочитать (игра ещё пишет файл?):", "could not read it (is the game still writing?):"), e)


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        try: stream.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
        except Exception: pass
    try:
        main()
    except KeyboardInterrupt:
        pass
    except SystemExit as e:
        if FROZEN and e.code not in (None, 0):
            print(e.code); input(tr("\nНажми Enter, чтобы закрыть...", "\nPress Enter to close..."))
            raise SystemExit(1)
        raise
    except Exception:
        import traceback; traceback.print_exc()
        if FROZEN: input(tr("\nНажми Enter, чтобы закрыть...", "\nPress Enter to close..."))
        sys.exit(1)
