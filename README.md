# 1G1R DAT Filter for FinalBurn Neo

A Python script that filters FinalBurn Neo (and other Logiqx XML) DAT files to produce a clean **1 Game 1 Region (1G1R)** set — one ROM per game, prioritized by region preference.

## What It Does

- **Removes clones** — entries with `cloneof` attribute are filtered out
- **Removes non-game content** — BIOS, add-ons, applications, audio, bonus discs, coverdiscs, kiosks, samples, educationals, manuals, MIAs, multimedia, videos, system/device entries
- **Removes bad/modified dumps** — bad dumps, hacks, bootlegs, fixed ROMs, cracked ROMs, pirates, unlicensed, aftermarket, not working
- **Removes pre-release content** — demos, prototypes, preproductions, betas, promotionals, location tests
- **Removes homebrew** — homebrew games and tech demos
- **Removes games with comments** — any ROM entry that has a `<comment>` field is excluded, as comments typically indicate emulation issues, quality problems, or other known defects
- **Removes niche/non-mainstream genres:**
  - *BIOS / System / Device / Utilities* — system firmware, hardware, carts, protection chips, utilities, updates; names ending in `_bios`; prefixes `neocart_*`, `ng_*`
  - *Mahjong / Adult Mahjong* — titles containing "mahjong"; ROM prefixes `mj*`, `jan*`
  - *Adult / Hentai / Strip / Mature* — titles containing "adult", "hentai", "strip", "sexy", "explicit"; specific ROMs like `fantsia`, `galhustl`, `zipzap`, etc.; plus all ROMs listed in `mature.ini` and `* Mature *` categories in `catver.ini`
  - *Gambling / Casino / Slot / Fruit / Medal* — titles containing "casino", "poker", "gambling", "medal", "slot", "jackpot", "blackjack", "roulette", "bingo", "hanafuda", "skill drop", "fortune teller"; ROM prefixes `casino*`, `lucky*`, `slot*`, `m4*`, `m5*`, `c3_*`, `j6*`, `sc*`, `nfb*`, `fb*`
  - *Pachinko / Pachislo* — titles containing "pachinko", "pachislo"; ROM prefix `pach*`
  - *Fruit machines* — titles containing "fruit"; ROM prefix `fruit*`
  - *Quiz / Trivia / Educational* — titles containing "quiz", "trivia", "educational"
  - *Pinball / Mechanical / EM / Redemption* — titles containing "pinball", "electro", "redemption", "crane", "strength tester"; ROM prefix `pb*`
  - *Tabletop / Board / Card* — titles containing "tabletop", "board game", "card game", "hanafuda", "shougi", "reversi"
  - *Horse Racing / Fishing / Crane* — titles containing "horse rac", "fishing", "crane"
- **Category-based filtering via Progetto Snaps INI files:**
  - `catver.ini` — ROM-to-category mapping; excludes System/Device, Slot Machine, Gambling, Casino, Mahjong, Adult/Mature, Pinball, Electromechanical, Quiz, Tabletop, Board Game, Card Game, Medal, Handheld, Game Console, Computer, Utilities, Redemption, Horse Racing, Crane, Fishing, Multigame, Plug n Play, Unknown, and more
  - `mature.ini` — explicit list of adult/mature-rated ROMs
  - `catlist.ini` — section-based ROM lists with same exclusion keywords
- **Deduplicates** — groups identical titles and picks the best regional variant
- **Region-prioritized selection** — selects the preferred region version when multiple exist
- **Clone-count priority** — when scores are tied, prefers the ROM that has the most clones referencing it (indicating the canonical/primary version)
- **Include list override** — ROMs listed in `include.txt` bypass all exclusion filters and are always kept, even if they match excluded categories (e.g., mahjong, adult, clones)
- **Exclude list override** — ROMs listed in `exclude.txt` are always excluded, even if they would normally pass all filters
- **Conflict detection** — if a ROM appears in both `include.txt` and `exclude.txt`, the script stops and lists the conflicting entries
- **Deprioritizes dedicated hardware** — PCB, JAMMA PCB, and Bubble System variants are deprioritized in favor of standard board/cartridge versions

## Region Priority

The script selects ROMs based on the following region preference (highest to lowest):

```
USA > World > Europe > Japan > Canada > UK > Australia > Spain > Mexico >
Argentina > Peru > Latin America > New Zealand > Singapore > Ireland >
Thailand > Hong Kong > Asia > Brazil > Portugal > France > Belgium >
Netherlands > Germany > Austria > Italy > Switzerland > China > Taiwan >
Korea > Russia > Ukraine > Estonia > Poland > Latvia > Lithuania > Denmark >
Norway > Sweden > Scandinavia > Finland > Iceland > Hungary > Czech > Greece >
Macedonia > India > South Africa > Israel > Slovakia > Turkey > Croatia >
Slovenia > United Arab Emirates > Bulgaria > Romania > Albania > Serbia >
Indonesia > Unknown
```

## Requirements

- Python 3.6+
- No external dependencies (uses only standard library)

## Getting DAT Files

The latest FinalBurn Neo DAT files can be obtained from the official repository:

https://github.com/libretro/FBNeo/tree/master/dats

## Getting mature.ini (Adult/Mature ROM List)

The script uses the **Progetto Snaps CatVer** category pack for comprehensive category-based filtering. It reads:

- `catver.ini` — ROM-to-category mapping (excludes BIOS/System/Device, Slot Machine, Gambling, Casino, Mahjong, Adult/Mature, Pinball, Electromechanical, Quiz/Trivia, Tabletop, Board/Card Game, Medal Game, Horse Racing, Crane, Fishing, Handheld, Game Console, Computer, Utilities, Redemption, Multigame, Plug n Play, Unknown, and anything marked `* Mature *`)
- `mature.ini` — explicit list of adult/mature-rated ROMs
- `catlist.ini` — section-based ROM lists (excludes ROMs in any section matching the same category keywords)
- `genre.ini` / `genre_ows.ini` — genre groupings (loaded for reference)

Download the pack from:

https://www.progettosnaps.net/catver/

Extract the archive so you have a `pS_CatVer_XXX` folder (e.g. `pS_CatVer_287`, `pS_CatVer_286`, etc.) in the same directory as the script. The script auto-detects the latest `pS_CatVer_*` folder (or specify its path with `--catver-folder`).

## Include List (Force-Keep ROMs)

The script supports an `include.txt` file that lists ROMs which should **never** be excluded, regardless of any filtering rules. This is useful for keeping specific games that would otherwise be filtered out (e.g., a mahjong game you enjoy, or a clone you prefer).

**Format:** One ROM name per line, with or without `.zip` extension. Lines starting with `;` or `#` are comments.

```
# My must-keep ROMs
mahretsu.zip
janshin.zip
bakatono
```

By default, the script looks for `include.txt` in the current directory. Use `--include-file` to specify a different path, or `--include-file ""` to disable.

## Exclude List (Force-Remove ROMs)

The script supports an `exclude.txt` file that lists ROMs which should **always** be excluded, even if they would normally pass all filters. This is useful for removing specific games you don't want in your set.

**Format:** One ROM name per line, with or without `.zip` extension. Lines starting with `;` or `#` are comments.

```
# ROMs I don't want
some_game.zip
another_game
```

By default, the script looks for `exclude.txt` in the current directory. Use `--exclude-file` to specify a different path, or `--exclude-file ""` to disable.

**Note:** If a ROM appears in both `include.txt` and `exclude.txt`, the script will stop with an error and list the conflicting entries. Resolve the conflict by removing the ROM from one of the files.

## Usage

```bash
# Process all .dat files in the current directory
python 1g1r_filter.py

# Process specific file(s)
python 1g1r_filter.py "FinalBurn Neo (ClrMame Pro XML, Arcade only).dat"

# Output to a subdirectory
python 1g1r_filter.py --output-dir 1g1r

# Show detailed filtering info (which games are excluded/kept and why)
python 1g1r_filter.py --verbose

# Use a specific pS_CatVer folder for category-based exclusion
python 1g1r_filter.py --catver-folder pS_CatVer_286

# Combine options
python 1g1r_filter.py -o 1g1r -v "FinalBurn Neo (ClrMame Pro XML, NES Games only).dat"

# Use a custom include list
python 1g1r_filter.py --include-file my_favorites.txt

# Use a custom exclude list
python 1g1r_filter.py --exclude-file my_blacklist.txt

# Disable the include list (process without overrides)
python 1g1r_filter.py --include-file ""

# Disable the exclude list
python 1g1r_filter.py --exclude-file ""
```

### Options

| Flag | Description |
|------|-------------|
| `files` | Input `.dat` file(s). If omitted, processes all `.dat` files in the current directory. |
| `-o`, `--output-dir` | Output directory for filtered DAT files. Defaults to the same directory as the input. |
| `-v`, `--verbose` | Show per-game exclusion and selection details. |
| `-c`, `--catver-folder` | Path to `pS_CatVer_*` folder containing `catver.ini` and `UI_files/`. Auto-detected if not specified. |
| `-i`, `--include-file` | Path to a text file listing ROMs to always keep (one per line, with or without `.zip`). Default: `include.txt` in the current directory. |
| `-e`, `--exclude-file` | Path to a text file listing ROMs to always exclude (one per line, with or without `.zip`). Default: `exclude.txt` in the current directory. |

## Output

The script generates a new DAT file with `[1G1R]` appended to the filename. The game count in the filename and header is updated to reflect the filtered set.

**Example:**

```
Input:  FinalBurn Neo (ClrMame Pro XML, ZX Spectrum Games only).dat  (3278 entries)
Output: FinalBurn Neo (ClrMame Pro XML, ZX Spectrum Games only) [1G1R].dat  (1489 games)
```

### Sample Output

```
Processing: FinalBurn Neo (ClrMame Pro XML, ZX Spectrum Games only).dat
------------------------------------------------------------
  Total entries    : 3278
  Excluded         : 1778
    Comment: homebrew               1101
    Clone                           642
    Comment: demo                   12
    Comment: hack                   9
    Homebrew (HB)                   5
    BIOS (isbios)                   3
    Demo                            2
    Comment: prototype              2
    Video                           2
  Duplicates removed: 11
  Final 1G1R set   : 1489 games
  Written to: FinalBurn Neo (ClrMame Pro XML, ZX Spectrum Games only) [1G1R].dat
```

## How It Works

1. **Parse** — Reads the Logiqx XML DAT file
2. **Exclude** — Filters out clones, BIOS, non-game content, hacks, demos, homebrew, bad dumps, etc. using XML attributes (`cloneof`, `isbios`), `<comment>` keywords, `<description>` regex patterns, `<category>`, and `<manufacturer>` fields
3. **Group** — Groups remaining games by normalized title (strips parenthetical metadata, punctuation, and leading "The"), disambiguated by source driver file so different games that share a normalized title (e.g. SNK's *Main Event* vs Konami's *The Main Event*) are kept as separate entries
4. **Score & Select** — For each group, scores candidates by region priority, PCB/dedicated-hardware penalty, clone count (more clones = canonical parent), alt/set flags, revision number, and picks the best one
5. **Write** — Outputs a new DAT file with only the selected games, sorted alphabetically

## Supported DAT Formats

Any Logiqx XML DAT file, including all FinalBurn Neo platform DATs:

- Arcade
- NES / FDS
- SNES
- Megadrive / Master System / Game Gear / SG-1000
- PC-Engine / TurboGrafx-16 / SuperGrafx
- Neo Geo / Neo Geo Pocket
- ColecoVision / Fairchild Channel F
- MSX 1
- ZX Spectrum

## Acknowledgments

This script is inspired by [Retool](https://github.com/unexpectedpanda/retool), a more comprehensive ROM management tool with GUI support and advanced filtering capabilities.

## License

This project is licensed under the [MIT License](LICENSE).
