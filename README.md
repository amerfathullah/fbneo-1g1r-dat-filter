# 1G1R DAT Filter for FinalBurn Neo

A Python script that filters FinalBurn Neo (and other Logiqx XML) DAT files to produce a clean **1 Game 1 Region (1G1R)** set — one ROM per game, prioritized by region preference.

## What It Does

- **Removes clones** — entries with `cloneof` attribute are filtered out
- **Removes non-game content** — BIOS, add-ons, applications, audio, bonus discs, coverdiscs, kiosks, samples, educationals, manuals, MIAs, multimedia, videos
- **Removes bad/modified dumps** — bad dumps, hacks, bootlegs, fixed ROMs, cracked ROMs, pirates, unlicensed, aftermarket
- **Removes pre-release content** — demos, prototypes, preproductions, betas, promotionals
- **Removes homebrew** — homebrew games and tech demos
- **Removes games with comments** — any ROM entry that has a `<comment>` field is excluded, as comments typically indicate emulation issues, quality problems, or other known defects (e.g. imperfect sound, graphics corruption, unemulated protection, bad dump, etc.)
- **Deduplicates** — groups identical titles and picks the best regional variant
- **Region-prioritized selection** — selects the preferred region version when multiple exist

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

# Combine options
python 1g1r_filter.py -o 1g1r -v "FinalBurn Neo (ClrMame Pro XML, NES Games only).dat"
```

### Options

| Flag | Description |
|------|-------------|
| `files` | Input `.dat` file(s). If omitted, processes all `.dat` files in the current directory. |
| `-o`, `--output-dir` | Output directory for filtered DAT files. Defaults to the same directory as the input. |
| `-v`, `--verbose` | Show per-game exclusion and selection details. |

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
3. **Group** — Groups remaining games by normalized title (strips parenthetical metadata, punctuation, and leading "The")
4. **Score & Select** — For each group, scores candidates by region priority, revision number, alt/set flags, and picks the best one
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
