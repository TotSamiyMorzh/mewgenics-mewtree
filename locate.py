"""Find Steam, Mewgenics saves and resources.gpak on Windows, Linux (native Steam,
Flatpak, Snap, Steam Deck via Proton) and macOS.

Overrides: STEAM_DIR (Steam root), MEWGENICS_SAVES (folder that holds <steamid>/saves),
MEWGENICS_GPAK (path to resources.gpak).
"""
import os, re, sqlite3, shutil, struct, sys, tempfile, time
from pathlib import Path

HOME = Path.home()
GAME_SUBDIR = Path("Glaiel Games") / "Mewgenics"


def _uniq(paths):
    seen, out = set(), []
    for p in paths:
        try:
            r = p.resolve()
        except OSError:
            continue
        if r not in seen and r.exists():
            seen.add(r); out.append(r)
    return out


def steam_roots():
    c = []
    if os.environ.get("STEAM_DIR"):
        c.append(Path(os.environ["STEAM_DIR"]))
    if sys.platform == "win32":
        try:
            import winreg
            for hive, key, val in ((winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam", "SteamPath"),
                                   (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam", "InstallPath"),
                                   (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Valve\Steam", "InstallPath")):
                try:
                    with winreg.OpenKey(hive, key) as k:
                        c.append(Path(winreg.QueryValueEx(k, val)[0]))
                except OSError:
                    pass
        except ImportError:
            pass
        for env in ("ProgramFiles(x86)", "ProgramFiles"):
            if os.environ.get(env):
                c.append(Path(os.environ[env]) / "Steam")
    elif sys.platform == "darwin":
        c.append(HOME / "Library" / "Application Support" / "Steam")
    else:
        c += [HOME / ".steam" / "steam", HOME / ".steam" / "root", HOME / ".local" / "share" / "Steam",
              HOME / ".var" / "app" / "com.valvesoftware.Steam" / ".local" / "share" / "Steam",
              HOME / "snap" / "steam" / "common" / ".local" / "share" / "Steam"]
    return _uniq(c)


def steam_libraries(roots=None):
    roots = steam_roots() if roots is None else roots
    libs = list(roots)
    for r in roots:
        for vdf in (r / "steamapps" / "libraryfolders.vdf", r / "config" / "libraryfolders.vdf"):
            try:
                txt = vdf.read_text("utf-8", "replace")
            except OSError:
                continue
            libs += [Path(m.group(1).replace("\\\\", "\\")) for m in re.finditer(r'"path"\s+"([^"]+)"', txt)]
    return _uniq(libs)


def persona_names(roots=None):
    """SteamID64 -> profile name, from Steam's config/loginusers.vdf."""
    names = {}
    for r in (steam_roots() if roots is None else roots):
        try:
            txt = (r / "config" / "loginusers.vdf").read_text("utf-8", "replace")
        except OSError:
            continue
        for m in re.finditer(r'"(7656\d{13})"\s*\{(.*?)\}', txt, re.S):
            p = re.search(r'"PersonaName"\s+"([^"]*)"', m.group(2))
            if p:
                names[m.group(1)] = p.group(1)
    return names


def save_roots(libs=None):
    c = []
    if os.environ.get("MEWGENICS_SAVES"):
        c.append(Path(os.environ["MEWGENICS_SAVES"]))
    if os.environ.get("APPDATA"):
        c.append(Path(os.environ["APPDATA"]) / GAME_SUBDIR)
    if sys.platform == "darwin":
        c.append(HOME / "Library" / "Application Support" / GAME_SUBDIR)
    # Proton prefixes (Linux, Steam Deck): compatdata/<appid>/pfx/drive_c/users/<user>/AppData/Roaming
    for lib in (steam_libraries() if libs is None else libs):
        c += (lib / "steamapps" / "compatdata").glob("*/pfx/drive_c/users/*/AppData/Roaming/" + GAME_SUBDIR.as_posix())
    return _uniq(c)


def peek(path):
    """(current_day, cats in the house) without touching the original file."""
    tmp = Path(tempfile.mkdtemp(prefix="mewpeek")) / "s.sav"
    try:
        shutil.copyfile(path, tmp)
        db = sqlite3.connect(tmp)
        try:
            day = db.execute("select data from properties where key='current_day'").fetchone()
            h = db.execute("select data from files where key='house_state'").fetchone()
        finally:
            db.close()
        house = struct.unpack_from("<I", h[0], 4)[0] if h and len(h[0]) >= 8 else None
        return (day[0] if day else None), house
    except Exception:
        return None, None
    finally:
        shutil.rmtree(tmp.parent, ignore_errors=True)


def find_saves():
    """Every *.sav, newest first, as dicts with account info."""
    names = persona_names()
    out = []
    for root in save_roots():
        for p in root.glob("*/saves/*.sav"):
            sid = p.parent.parent.name
            out.append({"path": p, "steamid": sid, "account": names.get(sid), "mtime": p.stat().st_mtime,
                        "test": p.stem.lower().startswith("test"),
                        "proton": "compatdata" in p.parts})
    out.sort(key=lambda s: (s["test"], -s["mtime"]))
    return out


def find_gpak():
    if os.environ.get("MEWGENICS_GPAK"):
        p = Path(os.environ["MEWGENICS_GPAK"])
        return p if p.exists() else None
    for lib in steam_libraries():
        for p in (lib / "steamapps" / "common" / "Mewgenics" / "resources.gpak",
                  lib / "steamapps" / "common" / "Mewgenics" / "Mewgenics.app" / "Contents" / "Resources" / "resources.gpak"):
            if p.exists():
                return p
    return None


def label(s):
    """What tells one save from another, as data (the page words it in its own language)."""
    day, house = peek(s["path"])
    return {"account": s["account"], "steamid": s["steamid"], "file": s["path"].name, "mtime": int(s["mtime"]),
            "day": day, "house": house, "test": s["test"], "proton": s["proton"]}


def describe(s, with_peek=True, lang="ru"):
    ru = lang == "ru"
    who = s["account"] or f"Steam {s['steamid']}"
    when = time.strftime("%d.%m %H:%M", time.localtime(s["mtime"]))
    extra = ""
    if with_peek:
        day, house = peek(s["path"])
        if day is not None:
            extra = f" · {'день' if ru else 'day'} {day}" + (f", {'дома' if ru else 'at home'} {house}" if house is not None else "")
    tags = ((" [тест]" if ru else " [test]") if s["test"] else "") + (" [Proton]" if s["proton"] else "")
    return f"{who} · {s['path'].name}{tags} · {when}{extra}"
