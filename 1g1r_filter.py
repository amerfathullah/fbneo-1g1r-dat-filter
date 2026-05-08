#!/usr/bin/env python3
"""
1G1R (1 Game 1 Region) DAT file filter for FinalBurn Neo / Logiqx XML DAT files.

Removes clones, duplicates, demos, prototypes, homebrew, hacks, bootlegs,
add-ons, applications, audios, bad dumps, bonus discs, coverdiscs, kiosks,
samples, educationals, manuals, MIAs, multimedias, preproductions,
promotionals, unlicensed, aftermarkets, pirates, videos, BIOS/chips,
fixed/cracked ROMs, and non-game content.

Selects the best regional variant per game based on configurable region priority.

Usage:
    python 1g1r_filter.py                          # Process all .dat files in current dir
    python 1g1r_filter.py game1.dat game2.dat      # Process specific files
    python 1g1r_filter.py --output-dir 1g1r        # Output to a subdirectory
    python 1g1r_filter.py --verbose                # Show detailed filtering info
"""

import xml.etree.ElementTree as ET
import re
import sys
import os
import glob
import argparse
from collections import defaultdict

# ---------------------------------------------------------------------------
# Region priority (lower index = higher priority)
# ---------------------------------------------------------------------------
REGION_PRIORITY = [
    "USA", "World", "Europe", "Japan", "Canada", "UK", "Australia",
    "Spain", "Mexico", "Argentina", "Peru", "Latin America", "New Zealand",
    "Singapore", "Ireland", "Thailand", "Hong Kong", "Asia", "Brazil",
    "Portugal", "France", "Belgium", "Netherlands", "Germany", "Austria",
    "Italy", "Switzerland", "China", "Taiwan", "Korea", "Russia",
    "Ukraine", "Estonia", "Poland", "Latvia", "Lithuania", "Denmark",
    "Norway", "Sweden", "Scandinavia", "Finland", "Iceland", "Hungary",
    "Czech", "Greece", "Macedonia", "India", "South Africa", "Israel",
    "Slovakia", "Turkey", "Croatia", "Slovenia", "United Arab Emirates",
    "Bulgaria", "Romania", "Albania", "Serbia", "Indonesia", "Unknown",
]

UNKNOWN_REGION_SCORE = len(REGION_PRIORITY) - 1

# ---------------------------------------------------------------------------
# Map aliases, abbreviations, and language names to canonical region names
# ---------------------------------------------------------------------------
REGION_MAP = {}

# Build map from the priority list itself (lowercase -> canonical)
for _r in REGION_PRIORITY:
    REGION_MAP[_r.lower()] = _r

# Extra aliases
_EXTRA = {
    "us": "USA", "u.s.a.": "USA", "america": "USA", "united states": "USA",
    "worldwide": "World",
    "euro": "Europe", "eur": "Europe", "eu": "Europe",
    "jpn": "Japan", "jp": "Japan",
    "ca": "Canada",
    "gb": "UK", "great britain": "UK", "united kingdom": "UK", "england": "UK",
    "au": "Australia", "aus": "Australia",
    "es": "Spain",
    "mx": "Mexico",
    "ar": "Argentina",
    "nz": "New Zealand",
    "sg": "Singapore",
    "ie": "Ireland",
    "th": "Thailand",
    "hk": "Hong Kong",
    "br": "Brazil", "bra": "Brazil",
    "pt": "Portugal",
    "fr": "France",
    "be": "Belgium",
    "nl": "Netherlands", "holland": "Netherlands",
    "de": "Germany",
    "at": "Austria",
    "it": "Italy",
    "ch": "Switzerland",
    "cn": "China",
    "tw": "Taiwan",
    "kr": "Korea", "korean": "Korea",
    "ru": "Russia",
    "ua": "Ukraine",
    "pl": "Poland",
    "dk": "Denmark",
    "se": "Sweden",
    "fi": "Finland",
    "hu": "Hungary",
    "cz": "Czech", "czech republic": "Czech", "czechia": "Czech",
    "gr": "Greece",
    "za": "South Africa",
    "il": "Israel",
    "uae": "United Arab Emirates",
    "bg": "Bulgaria",
    "ro": "Romania",
    "pe": "Peru",
    "ee": "Estonia",
    "lv": "Latvia",
    "lt": "Lithuania",
    "is": "Iceland",
    "mk": "Macedonia", "north macedonia": "Macedonia",
    "al": "Albania",
    "rs": "Serbia",
    "id": "Indonesia",
    "sk": "Slovakia", "slovak republic": "Slovakia",
    # Language -> primary region
    "spanish": "Spain", "portuguese": "Portugal", "french": "France",
    "german": "Germany", "italian": "Italy", "dutch": "Netherlands",
    "swedish": "Sweden", "norwegian": "Norway", "danish": "Denmark",
    "finnish": "Finland", "polish": "Poland", "russian": "Russia",
    "chinese": "China", "korean release": "Korea", "japanese": "Japan",
}
REGION_MAP.update(_EXTRA)


# ===================================================================
# Exclusion rules
# ===================================================================

# Keywords in the <comment> field that trigger exclusion
_COMMENT_EXCLUDES = [
    "hack", "bootleg", "demo", "prototype", "homebrew",
    "bios only", "hacked out protection", "unprotected version",
    "add-on", "application", "audio", "bonus disc", "coverdisc",
    "kiosk", "sample", "educational", "manual", "mia", "multimedia",
    "preproduction", "promotional", "unlicensed", "aftermarket",
    "pirate", "video", "bad dump", "fixed", "cracked",
]

# Regex patterns matched against the lowercase <description>
_DESC_EXCLUDE_PATTERNS = [
    # Hacks, bootlegs, piracy
    (r"\bhack\b",                "Hack"),
    (r"\(hack\)",               "Hack"),
    (r"\bbootleg\b",             "Bootleg"),
    (r"\bpirate\b",              "Pirate"),
    (r"\bpiracy\b",              "Piracy"),
    (r"\(unl\)",                 "Unlicensed"),
    (r"\bunlicensed\b",          "Unlicensed"),
    (r"\baftermarket\b",         "Aftermarket"),
    # Demos, prototypes, preproduction
    (r"\bdemo\b",                "Demo"),
    (r"\(demo\)",               "Demo"),
    (r"\btech[\s-]*demo\b",     "Tech demo"),
    (r"\bprototype\b",           "Prototype"),
    (r"\(proto\)",              "Prototype"),
    (r"\bpreproduction\b",       "Preproduction"),
    (r"\bpre-production\b",      "Preproduction"),
    (r"\bbeta\b",                "Beta"),
    # Homebrew
    (r"\bhomebrew\b",            "Homebrew"),
    (r"\(hb[,\s\)]",             "Homebrew (HB)"),
    (r"\(hb\)",                  "Homebrew (HB)"),
    # Bad dumps, fixed, cracked
    (r"\bbad\s*dump\b",          "Bad dump"),
    (r"\[b\]",                   "Bad dump [b]"),
    (r"\[b[0-9]\]",              "Bad dump [b#]"),
    (r"\bcracked\b",             "Cracked ROM"),
    (r"\[cr\d?\]",               "Cracked ROM [cr]"),
    (r"\[f\d?\]",                "Fixed ROM [f]"),
    (r"\(fixed\)",               "Fixed ROM"),
    # BIOS & system chips
    (r"\bbios\b",                "BIOS"),
    # Non-game content
    (r"\badd-on\b",              "Add-on"),
    (r"\bapplication\b",         "Application"),
    (r"\baudio\b",               "Audio"),
    (r"\bbonus\s*disc\b",        "Bonus disc"),
    (r"\bcoverdisc\b",           "Coverdisc"),
    (r"\bkiosk\b",               "Kiosk"),
    (r"\(sample[\s,\)]",         "Sample"),
    (r"\bsample\s*version\b",    "Sample"),
    (r"\beducational\b",         "Educational"),
    (r"\bmanual\b",              "Manual"),
    (r"\bmia\b",                 "MIA"),
    (r"\bmultimedia\b",          "Multimedia"),
    (r"\bpromotional\b",         "Promotional"),
    (r"\bpromo\b",               "Promotional"),
    (r"\bvideo\b",               "Video"),
    # Test / utility
    (r"\btest\s*(?:cart|program|cartridge)\b", "Test cart"),
    (r"\binput\s*test\b",        "Input test"),
    (r"\bnetwork\s*tool\b",     "Network tool"),
    (r"\bdiagnostic\b",          "Diagnostic"),
]


def is_excluded(game_elem):
    """Return (True, reason) if the game should be filtered out, else (False, '')."""

    # ---- clone filtering ----
    if game_elem.get("cloneof"):
        return True, "Clone"

    # ---- BIOS filtering (isbios attribute) ----
    if game_elem.get("isbios", "").lower() == "yes":
        return True, "BIOS (isbios)"

    desc = game_elem.findtext("description", "")
    comment = game_elem.findtext("comment", "")
    manufacturer = game_elem.findtext("manufacturer", "")
    category = game_elem.findtext("category", "")

    desc_lower = desc.lower()
    comment_lower = comment.lower()
    mfr_lower = manufacturer.lower().strip()

    # ---- comment-based exclusion ----
    for kw in _COMMENT_EXCLUDES:
        if kw in comment_lower:
            return True, f"Comment: {kw}"

    # ---- description-based exclusion ----
    for pattern, reason in _DESC_EXCLUDE_PATTERNS:
        if re.search(pattern, desc_lower):
            return True, reason

    # ---- category ----
    if category and category.lower() not in ("games", ""):
        return True, f"Category: {category}"

    # ---- manufacturer ----
    if mfr_lower in ("hack", "bootleg", "pirate") or mfr_lower.startswith("hack "):
        return True, f"Manufacturer: {manufacturer}"

    return False, ""


# ===================================================================
# Region detection
# ===================================================================

def detect_regions(description):
    """Return a list of canonical region names found in the description."""
    regions = set()

    # Check each parenthetical group  e.g. "(Euro, USA)"
    for paren in re.findall(r"\(([^)]+)\)", description):
        for part in paren.split(","):
            key = part.strip().lower()
            if key in REGION_MAP:
                regions.add(REGION_MAP[key])

    # Fallback: scan for longer keyword matches in the full description
    dl = description.lower()
    for key, region in REGION_MAP.items():
        if len(key) > 5 and key in dl:
            regions.add(region)

    return list(regions) if regions else ["Unknown"]


# ===================================================================
# Title normalisation & grouping
# ===================================================================

def normalize_title(description):
    """Strip all parenthetical metadata to get the bare game title."""
    title = re.sub(r"\s*\([^)]*\)", "", description)
    return re.sub(r"\s+", " ", title).strip()


def grouping_key(title):
    """Lowercase, no-punctuation key used to group equivalent titles."""
    key = title.lower()
    key = re.sub(r"^the\s+", "", key)        # drop leading "The "
    key = re.sub(r"[^\w\s]", "", key)         # drop punctuation
    return re.sub(r"\s+", " ", key).strip()


# ===================================================================
# Scoring (lower = better)
# ===================================================================

def _region_score(regions):
    best = UNKNOWN_REGION_SCORE
    for r in regions:
        try:
            s = REGION_PRIORITY.index(r)
            if s < best:
                best = s
        except ValueError:
            pass
    return best


def _set_number(desc):
    m = re.search(r"\(set\s+(\d+)\)", desc, re.IGNORECASE)
    return int(m.group(1)) if m else 0


def _is_alt(desc):
    return 1 if re.search(r"\balt\b", desc, re.IGNORECASE) else 0


def _revision(desc):
    """Higher revision = newer, so we negate for sorting (lower is better)."""
    m = re.search(r"rev\.?\s*([a-z0-9]+)", desc, re.IGNORECASE)
    if m:
        v = m.group(1)
        if v.isdigit():
            return -int(v)
        if len(v) == 1 and v.isalpha():
            return -(ord(v.upper()) - ord("A") + 1)
    return 0


def score_game(game_elem):
    """Return a sort-key tuple (lower = better candidate to keep)."""
    desc = game_elem.findtext("description", "")
    return (
        _region_score(detect_regions(desc)),
        _is_alt(desc),
        _set_number(desc),
        _revision(desc),
    )


# ===================================================================
# DAT I/O
# ===================================================================

def read_dat(filepath):
    """Parse a DAT file, returning (preamble_text, ElementTree, root)."""
    with open(filepath, "r", encoding="utf-8") as fh:
        raw = fh.read()

    # Keep the <?xml ...?> and <!DOCTYPE ...> lines verbatim
    preamble_lines = []
    for line in raw.split("\n"):
        s = line.strip()
        if s.startswith("<?xml") or s.startswith("<!DOCTYPE"):
            preamble_lines.append(line)
        elif s:
            break

    tree = ET.parse(filepath)
    root = tree.getroot()
    return "\n".join(preamble_lines), tree, root


def write_dat(filepath, preamble, root, selected):
    """Write a new DAT file containing only the selected <game> elements."""
    # Remove old games
    for g in root.findall("game"):
        root.remove(g)

    # Append selected (sorted by name attribute)
    for g in sorted(selected, key=lambda x: x.get("name", "").lower()):
        root.append(g)

    # Update <header>
    header = root.find("header")
    if header is not None:
        for tag in ("description", "name"):
            el = header.find(tag)
            if el is not None and el.text:
                el.text = re.sub(r"\([\d,]+\)", f"({len(selected)})", el.text, count=1)
                if "[1G1R]" not in el.text:
                    el.text += " [1G1R]"

    # Pretty-indent
    try:
        ET.indent(root, space="\t")
    except AttributeError:
        pass  # Python < 3.9

    xml_body = ET.tostring(root, encoding="unicode")

    with open(filepath, "w", encoding="utf-8") as fh:
        if preamble:
            fh.write(preamble + "\n")
        fh.write(xml_body)
        fh.write("\n")


# ===================================================================
# Main processing
# ===================================================================

def process_dat(input_path, output_dir=None, verbose=False):
    """Filter one DAT file -> 1G1R version.  Returns (kept, total)."""
    basename = os.path.basename(input_path)
    print(f"\nProcessing: {basename}")
    print("-" * 60)

    preamble, tree, root = read_dat(input_path)

    all_games = root.findall("game")
    total = len(all_games)

    # --- Phase 1: exclude ---
    kept = []
    reasons = defaultdict(int)
    for g in all_games:
        ex, reason = is_excluded(g)
        if ex:
            reasons[reason] += 1
            if verbose:
                print(f"  EXCLUDE [{reason}]: {g.findtext('description','')}")
        else:
            kept.append(g)

    print(f"  Total entries    : {total}")
    print(f"  Excluded         : {total - len(kept)}")
    for r, c in sorted(reasons.items(), key=lambda x: -x[1]):
        print(f"    {r:30s}  {c}")

    # --- Phase 2: group by title ---
    groups = defaultdict(list)
    for g in kept:
        desc = g.findtext("description", "")
        title = normalize_title(desc)
        groups[grouping_key(title)].append(g)

    # --- Phase 3: pick best per group ---
    selected = []
    dupes = 0
    for key, games in groups.items():
        if len(games) == 1:
            selected.append(games[0])
            continue

        scored = sorted(games, key=score_game)
        selected.append(scored[0])
        dupes += len(scored) - 1

        if verbose:
            sel_desc = scored[0].findtext("description", "")
            print(f"  KEEP : {sel_desc}")
            for g in scored[1:]:
                print(f"    drop : {g.findtext('description','')}")

    print(f"  Duplicates removed: {dupes}")
    print(f"  Final 1G1R set   : {len(selected)} games")

    # --- Phase 4: write ---
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    else:
        output_dir = os.path.dirname(input_path) or "."

    name_no_ext = os.path.splitext(basename)[0]
    name_updated = re.sub(r"\([\d,]+\)", f"({len(selected)})", name_no_ext)
    out_name = name_updated + " [1G1R].dat"
    out_path = os.path.join(output_dir, out_name)

    write_dat(out_path, preamble, root, selected)
    print(f"  Written to: {out_name}")

    return len(selected), total


def main():
    ap = argparse.ArgumentParser(
        description="1G1R DAT filter for FinalBurn Neo / Logiqx XML DAT files. "
                    "Removes hacks, bootlegs, demos, prototypes, homebrew, bad dumps, "
                    "fixed/cracked ROMs, and picks the best regional variant per game."
    )
    ap.add_argument("files", nargs="*",
                    help="Input .dat file(s).  If omitted, processes all .dat in the cwd.")
    ap.add_argument("-o", "--output-dir", default=None,
                    help="Output directory (default: same directory as input)")
    ap.add_argument("-v", "--verbose", action="store_true",
                    help="Show per-game exclusion and selection details")
    args = ap.parse_args()

    files = args.files or glob.glob("*.dat")
    # Never re-process an existing 1G1R output
    files = [f for f in files if "[1G1R]" not in f and os.path.isfile(f)]

    if not files:
        print("No .dat files found to process.")
        sys.exit(1)

    grand_selected = 0
    grand_total = 0

    for fp in sorted(files):
        try:
            sel, tot = process_dat(fp, args.output_dir, args.verbose)
            grand_selected += sel
            grand_total += tot
        except Exception as e:
            print(f"  ERROR: {e}")

    print(f"\n{'=' * 60}")
    print(f"All done!  {grand_selected} games kept from {grand_total} total entries "
          f"across {len(files)} file(s).")


if __name__ == "__main__":
    main()
