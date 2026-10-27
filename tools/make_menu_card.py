#!/usr/bin/env python3
"""Makes the new menu's files on a GAMES card (or a folder standing in for one): /menu/index.bin and
/menu/covers.bin. Without them the firmware falls back to a plain list (no Settings tab).

Anyone (2026-10-26, for sharing): python3 make_menu_card.py <the card's folder>
  Needs Python 3 with Pillow and numpy (pip install pillow numpy). Each game gets a name tile made from its file name,
  or its own cover: a picture named like the game file, in a folder called covers on the card
  (covers/Tetris DX.png for gbc/Tetris DX.gbc; .png or .jpg).
This build's own rig, with names, genres and box art by checksum, after the box-art matcher has run:
  ~/.local/state/roms/boxart/match.py gb gbc   (names, genres, box art, by checksum)
  ~/.local/state/roms/boxart/fetch_covers.py gb gbc
  make_menu_card.py /run/media/aaron/GAMES
Every .gb/.gbc on the card (top folder and one folder down, like the firmware) gets a record; games in
custom/ are marked special (the special games' tab, named by -DGBKIT_NAME) and borrow the cover and genre of the game they were made from.

index.bin (little-endian):
  header 16 bytes: "GBMN", version u16 = 1, count u16, record size u16 = 64, genres u8, 0 x 5
  genre names: genres x 16 bytes
  records, sorted by display name (A-Z order, a leading "The " ignored), 64 bytes each:
    u32 key     FNV-1a of the path on the card without the leading slash, in code page 437 with A-Z lower-cased ("gbc/tetris dx.gbc")
    u8  genre   0 .. genres-1
    u8  flags   1 = special (custom/), 2 = has a cover (else a name tile), 4 = Game Boy Color
    u16 cover   cover number in covers.bin
    char name[56]  display name, NUL-terminated
covers.bin: per cover 160x160, then 80x80, then 24x24 pixels, RGB565, high byte first (the screen's
byte order), 65152 bytes each.
"""
import glob, hashlib, io, json, os, re, struct, sys
import numpy as np
from PIL import Image, ImageDraw

BOXART = os.environ.get("GBKIT_BOXART", os.path.expanduser("~/.local/state/roms/boxart"))   # the rig's matcher
HERE = os.path.dirname(os.path.abspath(__file__))
SIZES = (160, 80, 24)
COVER_BYTES = sum(s * s * 2 for s in SIZES)
PANEL = (30, 38, 58)
GENRES = ["Platform", "Sports", "Action", "Racing", "Puzzle", "RPG", "Adventure", "Shooter", "Strategy", "Other"]
GROUP = {"Platform": "Platform", "Sports": "Sports", "Hunting and Fishing": "Sports", "Action": "Action",
         "Beat'em Up": "Action", "Fighting": "Action", "Racing": "Racing", "Puzzle": "Puzzle", "Board": "Puzzle",
         "Card": "Puzzle", "Quiz": "Puzzle", "Thinking": "Puzzle", "Casual Game": "Puzzle",
         "Role-playing (RPG)": "RPG", "Adventure": "Adventure", "Shooter": "Shooter", "Shoot'em Up": "Shooter",
         "Strategy": "Strategy", "Simulation": "Strategy"}
# custom builds: the game they were made from (a file name stem in the master library's match lists)
CUSTOM_BASE = {"Pokemon Crystal": "Pokemon-Crystal Version", "Kirby's Dream Land 2": "Kirby's Dream Land 2"}


def fnv1a(s):
    """The firmware's key: FatFs hands it names in code page 437 (ffconf.h), and it lower-cases A-Z only."""
    h = 0x811C9DC5
    for b in s.encode("cp437", errors="replace"):
        if 65 <= b <= 90:
            b += 32
        h = ((h ^ b) * 0x01000193) & 0xFFFFFFFF
    return h


def clean(name):
    t = re.sub(r"\s*[\(\[].*", "", name).strip()          # drop (USA, Europe) [!] and the rest
    m = re.match(r"^(.*?), (The|A|An)( - .*|$)", t)       # "Legend of Zelda, The - X" -> "The Legend of Zelda - X"
    if m:
        t = f"{m.group(2)} {m.group(1)}{m.group(3)}"
    return t


def sort_key(t):
    return re.sub(r"^(the|a|an) ", "", t.lower())


def font():
    p = os.path.join(HERE, "..", "inc", "font8x8_basic.h")
    if not os.path.exists(p):
        p = os.path.join(HERE, "font8x8_basic.h")                 # shared copies: the font file next to this one
    src = open(p).read()
    f = {}
    for m in re.finditer(r"\{((?:\s*0x[0-9A-Fa-f]{2},?){8})\s*\},\s*// U\+00([0-9A-F]{2})", src):
        f[int(m.group(2), 16)] = [int(x, 16) for x in re.findall(r"0x([0-9A-Fa-f]{2})", m.group(1))]
    return f


FONT = font()


def name_tile(title, size=160):
    """A cover for a game without box art: its name in the kit's font on a coloured card."""
    hue = fnv1a(title) % 6
    colours = [(60, 90, 150), (130, 70, 140), (50, 120, 100), (150, 90, 50), (90, 100, 60), (120, 60, 70)]
    im = Image.new("RGB", (size, size), colours[hue])
    d = ImageDraw.Draw(im)
    words, lines, cur = title.split(), [], ""
    for w in words:
        if len(cur) + len(w) + (1 if cur else 0) <= 9:
            cur = (cur + " " + w).strip()
        else:
            if cur:
                lines.append(cur)
            cur = w[:9]
    if cur:
        lines.append(cur)
    lines = lines[:7]
    y = (size - len(lines) * 20) // 2
    for ln in lines:
        x = (size - len(ln) * 16) // 2
        for i, ch in enumerate(ln):
            g = FONT.get(ord(ch), FONT[ord("?")])
            for py in range(8):
                for px in range(8):
                    if g[py] >> px & 1:
                        d.rectangle([x + (i * 8 + px) * 2, y + py * 2, x + (i * 8 + px) * 2 + 1, y + py * 2 + 1],
                                    fill=(240, 240, 240))
        y += 20
    return im


def rgb565(im, size):
    im = im.copy()
    im.thumbnail((size, size), Image.LANCZOS)
    sq = Image.new("RGB", (size, size), PANEL)
    sq.paste(im, ((size - im.width) // 2, (size - im.height) // 2))
    a = np.asarray(sq, dtype=np.uint16)
    v = (a[:, :, 0] >> 3) << 11 | (a[:, :, 1] >> 2) << 5 | a[:, :, 2] >> 3
    return v.astype(">u2").tobytes()


def main(card):
    # the master library's matches, by checksum
    by_sha = {}
    for system in ("gb", "gbc"):
        lst = os.path.join(BOXART, system + ".json")
        if not os.path.exists(lst):
            continue
        for e in json.load(open(lst)):
            e["system"] = system
            by_sha.setdefault(e["sha1"], e)
    if not by_sha:
        print("no box-art lists: name tiles, or pictures from the card's covers folder")
    by_stem = {os.path.splitext(os.path.basename(e["file"]))[0]: e for e in by_sha.values()}
    games = []
    for f in sorted(glob.glob(os.path.join(card, "*.gb*")) + glob.glob(os.path.join(card, "*", "*.gb*"))):
        if not f.lower().endswith((".gb", ".gbc")) or "/saves/" in f:
            continue
        rel = os.path.relpath(f, card)
        data = open(f, "rb").read()
        e = by_sha.get(hashlib.sha1(data).hexdigest().upper())
        stem = os.path.splitext(os.path.basename(f))[0]
        special = rel.lower().startswith("custom/")
        if special:
            base = next((v for k, v in CUSTOM_BASE.items() if stem.startswith(k)), None)
            e = by_stem.get(base) if base else None
            name = stem
        else:
            name = clean(e["no_intro"]) if e and e.get("no_intro") else clean(stem)
        cover = None
        for ext in (".png", ".jpg", ".jpeg", ".PNG", ".JPG"):     # the builder's own picture on the card
            own = os.path.join(card, "covers", stem + ext)
            if os.path.exists(own):
                cover = own
                break
        if cover is None and e and e.get("art"):
            p = os.path.join(BOXART, "covers", e["system"], os.path.splitext(os.path.relpath(e["file"], e["system"]))[0] + ".jpg")
            if os.path.exists(p):
                cover = p
        genre = GENRES.index(GROUP.get(e.get("genre"), "Other")) if e else GENRES.index("Other")
        color = len(data) > 0x143 and data[0x143] & 0x80
        games.append(dict(rel=rel, key=fnv1a(rel), name=name, genre=genre, special=special,
                          cover=cover, color=bool(color)))
    keys = [g["key"] for g in games]
    assert len(keys) == len(set(keys)), "two files with the same key"
    games.sort(key=lambda g: (not g["special"] and False, sort_key(g["name"]), g["rel"].lower()))
    os.makedirs(os.path.join(card, "menu"), exist_ok=True)
    with open(os.path.join(card, "menu", "covers.bin.part"), "wb") as cf:
        for n, g in enumerate(games):
            im = Image.open(g["cover"]).convert("RGB") if g["cover"] else name_tile(g["name"])
            blob = b"".join(rgb565(im, s) for s in SIZES)
            assert len(blob) == COVER_BYTES
            cf.write(blob)
            g["cover_no"] = n
    head = b"GBMN" + struct.pack("<HHHB5x", 1, len(games), 64, len(GENRES))
    head += b"".join(gn.encode().ljust(16, b"\0")[:16] for gn in GENRES)
    recs = []
    for g in games:
        flags = (1 if g["special"] else 0) | (2 if g["cover"] else 0) | (4 if g["color"] else 0)
        nm = g["name"].encode("ascii", "replace")[:55]
        recs.append(struct.pack("<IBBH56s", g["key"], g["genre"], flags, g["cover_no"], nm))
    with open(os.path.join(card, "menu", "index.bin.part"), "wb") as f:
        f.write(head + b"".join(recs))
    os.replace(os.path.join(card, "menu", "covers.bin.part"), os.path.join(card, "menu", "covers.bin"))
    os.replace(os.path.join(card, "menu", "index.bin.part"), os.path.join(card, "menu", "index.bin"))
    if hasattr(os, "sync"):                                    # not on Windows
        os.sync()
    counts = [sum(1 for g in games if g["genre"] == i) for i in range(len(GENRES))]
    print(f"{len(games)} games: {sum(1 for g in games if g['cover'])} with a cover picture, "
          f"{sum(1 for g in games if not g['cover'])} with a name tile, {sum(1 for g in games if g['special'])} special")
    print("genres:", ", ".join(f"{n} {c}" for n, c in zip(GENRES, counts)))
    print("covers.bin", os.path.getsize(os.path.join(card, "menu", "covers.bin")), "bytes")


if __name__ == "__main__":
    main(sys.argv[1])
