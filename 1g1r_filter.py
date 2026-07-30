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

# Regex patterns matched against the lowercase <description>
_DESC_EXCLUDE_PATTERNS = [
    # Hacks, bootlegs, piracy
    (r"\(hack[,\s\)]",           "Hack"),

    (r"\bbootleg\b",             "Bootleg"),
    (r"\bboot\b",                "Bootleg"),
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
    (r"\blocation\s*test\b",     "Location test"),
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
    (r"\bnot\s*working\b",       "Not working"),
    # BIOS (description only — System/Device handled by catver.ini)
    (r"\bbios\b",                "BIOS"),
    # Non-game content
    (r"\badd-on\b",              "Add-on"),
    (r"\bapplication\b",         "Application"),
    (r"\baudio\s*(?:disc|cd|track|collection)\b", "Audio"),
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
    (r"\bvideo\s*(?:disc|cd|collection)\b", "Video"),
    # Test / utility
    (r"\btest\s*(?:cart|program|cartridge)\b", "Test cart"),
    (r"\binput\s*test\b",        "Input test"),
    (r"\bnetwork\s*tool\b",     "Network tool"),
    (r"\bdiagnostic\b",          "Diagnostic"),
    # Mahjong
    (r"\bmahjong\b",             "Mahjong"),
    # Adult / Hentai / Strip / Explicit
    (r"\badult\b",               "Adult"),
    (r"\bhentai\b",              "Adult/Hentai"),
    (r"\bstrip\b",               "Adult/Strip"),
    (r"\bsexy\b",                "Adult/Sexy"),
    (r"\bexplicit\b",            "Explicit"),
    # Gambling / Casino / Medal / Pachinko / Slot
    (r"\bcasino(?!\s*tech)\b",   "Casino/Gambling"),
    (r"\bpoker\b",               "Poker/Gambling"),
    (r"\bgambling\b",            "Gambling"),
    (r"\bmedal\b",               "Medal game"),
    (r"\bpachinko\b",            "Pachinko"),
    (r"\bpachislo\b",            "Pachislo"),
    (r"\bslot\b",                "Slot machine"),
    (r"\bjackpot\b",             "Jackpot/Gambling"),
    (r"\bblackjack\b",           "Blackjack/Gambling"),
    (r"\broulette\b",            "Roulette/Gambling"),
    (r"\bbingo\b",               "Bingo/Gambling"),
    (r"\bhanafuda\b",            "Hanafuda"),
    # Fruit machines
    (r"\bfruit\b",               "Fruit machine"),
    # Quiz / Trivia
    (r"\bquiz\b",                "Quiz/Trivia"),
    (r"\btrivia\b",              "Quiz/Trivia"),
    # Pinball / Mechanical / Electro-mechanical
    (r"\bpinball\b",             "Pinball"),
    (r"\belectro\b",             "Electro-mechanical"),
    # Ticket / Redemption
    (r"\bticket\b",              "Ticket/Redemption"),
    (r"\bredemption\b",          "Ticket/Redemption"),
    # Tabletop / Non-video
    (r"\bshougi\b",              "Shougi/Tabletop"),
    (r"\breversi\b",             "Reversi/Tabletop"),
    (r"\btabletop\b",            "Tabletop"),
    (r"\bboard\s*game\b",        "Board game"),
    (r"\bcard\s*game\b",         "Card game"),
    # Horse Racing / Crane / Fishing (niche)
    (r"\bhorse\s*rac",            "Horse racing"),
    (r"\bcrane\b",               "Crane game"),
    (r"\bfishing\b",             "Fishing game"),
    # Fortune / Luck-based
    (r"\bfortune\s*tell",         "Fortune teller"),
    (r"\bskill\s*drop\b",        "Skill drop"),
    # Strength / Physical
    (r"\bstrength\s*test",        "Strength tester"),
]

# ROM name prefixes that indicate niche/excluded families (matched against game "name" attr)
# NOTE: Broad prefixes like sc*, pb*, fb*, lucky* were removed because they cause
# false positives on legitimate games (Scramble, Puzzle Bobble, Football Frenzy, Lucky & Wild).
# Category filtering via catver.ini now handles those families correctly.
_NAME_EXCLUDE_PREFIXES = [
    # Pachinko / Pachislo
    "pach",
    # Fruit machines
    "fruit",
    # Casino
    "casino",
    # Slot machines
    "slot",
    # UK fruit/slot machine families (massive filler, unambiguous prefixes)
    "m4", "m5", "c3_", "j6", "nfb",
    # Arcade system carts / protection chips
    "neocart_",
]

# Specific ROM names to exclude (adult/mature content — from MAME mature.ini 0.287)
# This list is embedded so mature ROMs are excluded even without mature.ini present.
# If mature.ini is also provided, its entries are merged with this set.
_NAME_EXCLUDE_EXACT = {
    "3kokushi", "3x3puzzl", "3x3puzzla", "4psimasy", "7jigen", "7ordi",
    "7toitsu", "abunai", "adults", "adultsa", "akiss", "apparel",
    "av2mj1bb", "av2mj2rg", "bakatono", "bakuhatu", "bananadr", "bballs",
    "bballsa", "bigjoke", "bigtwin", "bijokkog", "bijokkoy", "billlist",
    "bishjan", "bjtwinpa", "blandia", "blandiap", "blockgal", "blockgalb",
    "bnstars", "bnstars1", "boonggab", "bowmen", "bubl2000", "bubl2000a",
    "bublpong", "cabaret", "cafedoll", "cannball", "cannballv", "canvas",
    "casanova", "ccasino", "chance32", "chinmoku", "choko", "chsuper2",
    "chsuper3", "citalcup", "citylove", "club90s", "club90sa", "cmehyou",
    "couple", "couplei", "couplep", "cpoker", "cpoker2", "cpokerpk",
    "cpokerpkg", "cpokert", "cpokerx", "crystal2", "crystalg", "cs1_spp",
    "cs1_spp2", "cs10_sps", "cs11_sps", "cs11_sps2", "cs11_ssp", "cs12_sps",
    "cs2_sps", "cs3_qps", "cs5_spp", "cs5_ssp", "cs6_sps", "cs6_ssp",
    "cs8_spp", "cs8_sps", "cs8_ssp", "cs9_qps", "cs9_spp", "csk227it",
    "csk234it", "cspe_qps", "csv1_qps", "cultures", "daisyari", "daiyogen",
    "dakkochn", "danceyes", "danceyesj", "danceyesu", "danchih", "dblpoint",
    "dblpointd", "ddealer", "ddenlovj", "ddenlovr", "ddenlovrb", "ddenlovrk",
    "deluxe5", "discoboy", "discoboyp", "djgirl", "dokyusei", "dokyusp",
    "dondenmj", "drgnwrld", "drgnwrldv10c", "drgnwrldv11h", "drgnwrldv20j",
    "drgnwrldv21", "drgnwrldv21j", "drgnwrldv30", "drgnwrldv40k", "drgpunch",
    "drtomy", "dtrvwz5", "dwpc", "dwpc101j", "egghunt", "ejanhs",
    "ejsakura", "ejsakura12", "eldoralg", "elfin", "emjjoshi", "emjscanb",
    "emjtrapz", "ertictac", "ertictaca", "ertictacb", "excelsr", "excelsra",
    "fantasia", "fantasiaa", "fantasiab", "fantasian", "fantsia2", "fantsia2a",
    "fantsia2n", "fantsy95", "finalbny", "findlove", "fkddz2", "froman2b",
    "fromanc2", "fromanc2o", "fromanc4", "fromance", "fromancr", "funybubl",
    "funybublc", "funystrp", "gakusai", "gakusai2", "gal10ren", "galhustl",
    "galhustla", "galkaika", "galkoku", "galpani2", "galpani2e", "galpani2e2",
    "galpani2g", "galpani2gs", "galpani2i", "galpani2i2", "galpani2j",
    "galpani2k", "galpani2t", "galpani3", "galpani3hk", "galpani3j",
    "galpani3k", "galpani4", "galpani4a", "galpani4j", "galpani4k",
    "galpanic", "galpanica", "galpanicb", "galpanicc", "galpanicms",
    "galpanidx", "galpaniex", "galpanis", "galpanisa", "galpanise",
    "galpanisj", "galpanisk", "galpaniska", "galpanisu", "galpans2",
    "galpans2a", "galpans2j", "galpans3", "galpansu", "galpansua",
    "galsnew", "galsnewj", "galsnewk", "galsnewt", "galsnewu", "galspnbl",
    "gangonta", "gemcrush", "genie", "geniea", "gfire2", "gionbana",
    "glass", "glass10", "glass10a", "glass10b", "glass10c", "glass10d",
    "glassa", "glassat", "glasskr", "glasskra", "goori", "gp2quiz",
    "gp2se", "grndtour", "gt103asx", "gt103asxa", "gumbo", "gundealr",
    "gundealra", "gundealrbl", "gundealrt", "gundl94", "hanakanz", "hanamai",
    "hanamomb", "hanamomo", "hanaoji", "hanaojia", "hapytour", "haremchl",
    "hexa", "hexaa", "hgkairak", "hgokbang", "hgokou", "hkagerou",
    "hnageman", "hnayayoi", "hnfubuki", "hnkochou", "honeydol", "hotblock",
    "hotblocka", "hotblockb", "hotbody", "hotbody2", "hotbubl", "hotgm4ev",
    "hotgmck", "hotgmck3", "hotgmcki", "hotmemry", "hotmemry11", "hotnight",
    "hotpinbl", "hourouki", "housemn2", "housemnq", "hparadis", "hyhoo",
    "hyhoo2", "hyouban", "hypreac2", "hypreact", "idhimitu", "idolmj",
    "iemoto", "iemotom", "imekura", "inca", "intrgirl", "janbari",
    "janjans1", "janjans2", "janoh", "janoha", "janptr96", "janshin",
    "jansou", "jansoua", "jantouki", "jbell133i", "jbell141ue", "jbell153ue",
    "jbell155ue", "jbell157us", "jituroku", "jjparad2", "jjparads",
    "jngolady", "jogakuen", "jongbou", "jongkyo", "jongshin", "jongtei",
    "jumpjump", "kaguya", "kaguya2", "kaguya2f", "kakumei", "kakumei2",
    "kanatuen", "kirarast", "koikoip2", "koikois2", "koinomp", "komocomo",
    "kongball", "konhaji", "korinai", "korinaim", "kotbinyo", "kyuhito",
    "ladykill", "ladylinr", "ladymakr", "lagirl", "landbrk", "landbrka",
    "landbrkb", "lasstixx", "lastforte", "lastfortea", "lastfortg",
    "lemnangl", "livegal", "lovehous", "loverboy", "luckgrln", "lucky74",
    "lucky74a", "lucky74b", "lucky8", "lucky8a", "lucky8b", "lucky8c",
    "lucky8d", "lucky8e", "luckygrl", "luckypkr", "luplup", "luplup29",
    "lvcards", "lvgirl94", "lvpoker", "madball", "madballn", "maddonna",
    "maddonnab", "magicbuba", "magicbubb", "magicbubc", "magix", "magixb",
    "mahretsu", "maiko", "majorpkr20", "majorpkra", "majorpkrb", "majorpkrc",
    "majrjhdx", "majs101b", "majxtal7", "marukin", "marukina", "matchem",
    "matchit2", "maya", "mayaa", "mayab", "mayac", "mayumi", "mchampdx",
    "mchampdxa", "mchampdxb", "mcitylov", "mcnpshnt", "mcontest", "megastrp",
    "mfunclub", "mgakuen", "mgakuen2", "mgion", "mgmen89", "mhgaiden",
    "mhhonban", "mil4000", "mil4000a", "mil4000b", "mil4000c", "mirage",
    "missb2", "missmw96", "missw02", "missw02d", "missw96", "missw96a",
    "missw96b", "missw96c", "mj4simai", "mjanbari", "mjangels", "mjapinky",
    "mjcamera", "mjcameram", "mjcamerao", "mjchuuka", "mjclinic", "mjclinica",
    "mjcomv1", "mjdejav2", "mjdejavu", "mjderngr", "mjdialq2", "mjdialq2a",
    "mjdiplob", "mjegolf", "mjelct3", "mjelct3a", "mjelctrb", "mjelctrn",
    "mjembase", "mjflove", "mjfocus", "mjfocusm", "mjfriday", "mjgalpri",
    "mjgnight", "mjgottsu", "mjgottub", "mjgtaste", "mjhokite", "mjikaga",
    "mjkinjas", "mjkjidai", "mjkoiura", "mjkojink", "mjlaman", "mjlstory",
    "mjnanpaa", "mjnanpas", "mjnanpau", "mjnatsu", "mjnquest", "mjprivat",
    "mjreach1", "mjreachbl", "mjschuka", "mjsikakb", "mjsikakc", "mjsikakd",
    "mjsikaku", "mjsister", "mjsiyoub", "mjtensina", "mjuraden", "mjyougo",
    "mjyuugi", "mjyuugia", "mjzoomin", "mkeibaou", "mkoiuraa", "mladyhtr",
    "mmaiko", "mmehyou", "mmsikaku", "moegonta", "mogitate", "mosaicf2",
    "mrokumei", "msbingo", "mscoutm", "msjiken", "mspuzzle", "mspuzzlea",
    "mspuzzleb", "mspuzzleg", "musclem", "musobana", "myfairld", "natsuiro",
    "nekkyoku", "neruton", "nerutona", "newfant", "newfanta", "news",
    "newsa", "ngalsumr", "ngpgal", "ngtbunny", "nichisel", "nightgal",
    "nightlov", "nmg5", "nmg5a", "nmg5e", "nmsengen", "ns8linew",
    "nsupertr3", "ntopstar", "number10", "number10l", "nuretemi", "nyanpai",
    "odeontw2", "ohpaipee", "ojanko2", "ojankoc", "ojankoca", "ojankohs",
    "ojankoy", "ojousan", "ojousanm", "omotesnd", "onetwo", "onetwoe",
    "orangec", "orangeci", "otatidai", "otonano", "ougonhai", "ougonhaib1",
    "ougonhaib2", "ougonhaib3", "pachiten", "paintlad", "pairlove", "pairs",
    "pairsa", "pairsnb", "pairsten", "pangpang", "paprazzi", "para2dx",
    "paradise", "paradisea", "paradisee", "paradlx", "pastelg", "patimono",
    "pcktgal", "pcktgal2", "pcktgal2j", "pcktgalb", "pcktgalba", "pclubys",
    "pclubysa", "peekaboo", "peekaboou", "peepshow", "penfan", "penfana",
    "perestro", "perestrof", "pgalvip", "pgalvipa", "pgm3in1", "pgm3in1c100",
    "phrcrazev", "pipibibs", "pipibibsa", "pipibibsbl", "pipibibsbl2",
    "pipibibsbl3", "pipibibsp", "pkgnsh", "pkgnshdx", "pkladies",
    "pkladiesbl", "pkladiesbl2", "pkladiesblu", "pkladiesl", "pkladiesla",
    "pktgaldx", "pktgaldxb", "pktgaldxj", "plgirls", "plgirls2",
    "plgirls2b", "pokechmp", "pokechmpa", "pokoachu", "ponchin", "ponchina",
    "popbingo", "ppcar", "primella", "promutrva", "prtytime", "psailor1",
    "psailor2", "pstadium", "puckpepl", "pushman", "pushmana", "pushmant",
    "puzlbang", "puzlbanga", "puzzlet", "puzznic", "puzznicba", "puzznici",
    "puzznicj", "puzznicu", "py2k2100", "pzlestar", "pzletime", "qmhayaku",
    "quiz18k", "rbmk", "realbrk", "realbrkj", "realbrkk", "realbrko",
    "record", "reelquak", "renaiclb", "renaimj", "ringball", "rmgoldyh",
    "rmhaihai", "rmhaihai2", "rmhaihaibl", "rmhaihib", "rmhaijin",
    "rmhaisei", "rocktris", "roldfrog", "roldfroga", "rongrong", "rongrongg",
    "rongrongj", "royalngt", "royalpk2", "ryuuha", "sadari", "sailorwa",
    "sailorwr", "sailorws", "saklove", "scandal", "scandalm", "secolove",
    "seiha", "seiham", "seljan2", "sengomjk", "sexappl", "sextriv",
    "sextriv1", "sextriv2", "sexyboom", "sexygal", "sexyparo", "sexyparoa",
    "sgaltrop", "sgaltropa", "shisena", "sichuan2", "sichuan2a", "sjryuko",
    "sjryuko1", "sliver", "slivera", "smissw", "sos", "spbactn", "spbactnj",
    "spbactnp", "splash", "splash10", "splashms", "sprpuzzle", "srmp1",
    "srmp2", "srmp3", "srmp4", "srmp4o", "srmp6", "srmp7", "srmvsa",
    "ss2005", "ss2005o", "sshanghab", "sshanghaj", "ssingles", "sstar97",
    "sstar97a", "sstar97b", "sstar97jb", "star100", "starseek", "stealsee",
    "steaser", "stoffy", "stoffyu", "streakng", "streaknga", "suchie2",
    "suchie2o", "suchie3", "suchiesp", "superbar", "superten", "supertr",
    "supertr2", "supertr3", "suplup", "supmodel", "supmodl2", "sutjarod",
    "suzume", "sweetgal", "swinggal", "sxyreac2", "sxyreact", "taiwanmb",
    "teljan", "telmahjn", "tenkai", "tenkai2b", "tenkaibb", "tenkaicb",
    "tenkaie", "texasrls", "tgtbal96", "tgtball", "tgtballn", "themj",
    "themj2", "tinkerbl", "tmmjprd", "tmosh", "tmoshs", "tmoshsp",
    "tmoshspa", "tmpdoki", "togenkyo", "tokimbsj", "tokyogal", "tontonb",
    "tonypok", "torarech", "toride2gg", "torus", "trikitri", "triplew1",
    "triplew2", "trvgns", "trvmstr", "trvmstra", "trvmstrb", "trvmstrc",
    "tsuwaku", "twinbrat", "twinbrata", "twinbratb", "twins", "twinsa",
    "twinsed1", "twinsed2", "uchuuai", "ultramhm", "unkch1", "unkch2",
    "unkch3", "unkch4", "untoucha", "usg182", "usg185", "usg187c", "usg32",
    "usg82", "usg83x", "usgames", "vanilla", "vipclub", "vitaminc",
    "vivdolls", "vmahjong", "wcatcher", "whoopee", "wiggie", "wondstck",
    "worldadv", "wownfant", "wownfanta", "xfiles", "yarunara", "yosimotm",
    "yosimoto", "zerozone", "zipzap", "zipzapa", "zokumahj",
}


# ===================================================================
# Progetto Snaps INI loaders (catver.ini, catlist.ini, genre.ini, etc.)
# ===================================================================

# Categories in catver.ini that should be excluded (case-insensitive substring match)
_CATVER_EXCLUDE_KEYWORDS = [
    # BIOS / System / Device / Utilities
    "system / device", "system / bios", "utilities",
    "computer / home system", "computer / business", "computer / terminal",
    "game console", "handheld",
    "device",
    # Gambling / Casino / Slot / Fruit / Medal
    "slot machine", "gambling", "casino", "fruit machine", "medal game",
    "poker", "pachinko", "pachislot", "pachislo", "hanafuda",
    "skill drop", "fortune teller",
    # Mahjong / Adult Mahjong
    "mahjong",
    # Adult / Hentai / Strip / Mature
    "mature", "adult", "hentai", "strip",
    # Pinball / Mechanical / EM / Redemption
    "pinball", "electromechanical", "physical ability",
    "redemption", "crane machine", "strength tester",
    # Quiz / Trivia / Educational
    "quiz", "trivia", "educational",
    # Unknown / Prototype / Non-final
    "unknown",
    # Optional removals (niche/non-standard)
    "tabletop", "board game", "card game",
    "horse racing", "fishing", "crane",
    "multigame", "plug n play",
]


def find_catver_folder():
    """Auto-detect pS_CatVer_* folder in the current directory."""
    candidates = sorted(glob.glob("pS_CatVer_*"), reverse=True)
    for d in candidates:
        if os.path.isdir(d):
            return d
    return None


def load_mature_ini(filepath):
    """Parse a MAME mature.ini and return a set of lowercase ROM names."""
    names = set()
    in_root = False
    with open(filepath, "r", encoding="utf-8", errors="ignore") as fh:
        for line in fh:
            line = line.strip()
            if line == "[ROOT_FOLDER]":
                in_root = True
                continue
            if in_root:
                if line.startswith("["):
                    break  # next section
                if line and not line.startswith(";"):
                    names.add(line.lower())
    return names


def load_catver_ini(filepath):
    """Parse catver.ini and return a dict {romname: category} for excluded categories."""
    excluded = {}
    in_category = False
    with open(filepath, "r", encoding="utf-8", errors="ignore") as fh:
        for line in fh:
            line = line.strip()
            if line == "[Category]":
                in_category = True
                continue
            if in_category:
                if line.startswith("["):
                    break
                if "=" in line and not line.startswith(";"):
                    rom, cat = line.split("=", 1)
                    cat_lower = cat.strip().lower()
                    for kw in _CATVER_EXCLUDE_KEYWORDS:
                        if kw in cat_lower:
                            excluded[rom.strip().lower()] = cat.strip()
                            break
    return excluded


def load_catlist_ini(filepath):
    """Parse catlist.ini and return ROM names from excluded sections (Mature, Pinball, etc.)."""
    names = set()
    in_excluded_section = False
    with open(filepath, "r", encoding="utf-8", errors="ignore") as fh:
        for line in fh:
            line = line.strip()
            if line.startswith("["):
                section_lower = line.lower()
                in_excluded_section = any(
                    kw in section_lower for kw in _CATVER_EXCLUDE_KEYWORDS
                )
                continue
            if in_excluded_section and line and not line.startswith(";"):
                names.add(line.lower())
    return names


def load_genre_ini(filepath):
    """Parse genre.ini or genre_ows.ini — currently used for informational merge only.
    All ROMs in these files are arcade games; filtering is done via catver/catlist/mature."""
    # These files don't add exclusion info beyond catver.ini, but we load them
    # to catch any ROMs categorized in excluded sections
    names = set()
    in_excluded_section = False
    with open(filepath, "r", encoding="utf-8", errors="ignore") as fh:
        for line in fh:
            line = line.strip()
            if line.startswith("["):
                # genre.ini sections are genre names; we don't exclude by section here
                in_excluded_section = False
                continue
            # genre files list all arcade ROMs — no exclusion logic needed here
    return names


def _load_rom_list(filepath):
    """Load a text file and return a set of lowercase ROM names (without .zip)."""
    names = set()
    if not filepath or not os.path.isfile(filepath):
        return names
    with open(filepath, "r", encoding="utf-8", errors="ignore") as fh:
        for line in fh:
            line = line.strip()
            if line and not line.startswith(";") and not line.startswith("#"):
                # Strip .zip extension if present
                if line.lower().endswith(".zip"):
                    line = line[:-4]
                names.add(line.lower())
    return names


def load_include_list(filepath):
    """Load an include list file and return a set of lowercase ROM names (without .zip)."""
    return _load_rom_list(filepath)


def load_exclude_list(filepath):
    """Load an exclude list file and return a set of lowercase ROM names (without .zip)."""
    return _load_rom_list(filepath)


def check_include_exclude_conflicts(include_names, exclude_names):
    """Check for ROMs present in both include and exclude lists.
    Returns the set of conflicting names, or an empty set if none."""
    return include_names & exclude_names


def load_all_ini_exclusions(catver_folder=None):
    """Load all INI files and return a merged set of excluded ROM names + catver dict."""
    excluded_names = set()
    catver_map = {}

    if catver_folder is None:
        catver_folder = find_catver_folder()

    if catver_folder and os.path.isdir(catver_folder):
        print(f"Using category data from: {catver_folder}")

        # catver.ini (in root of folder)
        catver_path = os.path.join(catver_folder, "catver.ini")
        if os.path.isfile(catver_path):
            catver_map = load_catver_ini(catver_path)
            print(f"  catver.ini: {len(catver_map)} ROMs in excluded categories")

        ui_dir = os.path.join(catver_folder, "UI_files")

        # mature.ini
        mature_path = os.path.join(ui_dir, "mature.ini")
        if os.path.isfile(mature_path):
            mature = load_mature_ini(mature_path)
            excluded_names.update(mature)
            print(f"  mature.ini: {len(mature)} ROMs")

        # catlist.ini
        catlist_path = os.path.join(ui_dir, "catlist.ini")
        if os.path.isfile(catlist_path):
            catlist = load_catlist_ini(catlist_path)
            excluded_names.update(catlist)
            print(f"  catlist.ini: {len(catlist)} ROMs from excluded sections")

        # genre.ini (informational — currently no extra exclusions)
        genre_path = os.path.join(ui_dir, "genre.ini")
        if os.path.isfile(genre_path):
            print(f"  genre.ini: loaded")

        # genre_ows.ini (informational)
        genre_ows_path = os.path.join(ui_dir, "genre_ows.ini")
        if os.path.isfile(genre_ows_path):
            print(f"  genre_ows.ini: loaded")
    else:
        print("No pS_CatVer_* folder found. Using built-in exclusion lists only.")

    return excluded_names, catver_map


def is_excluded(game_elem, mature_names=None, catver_map=None, include_names=None, exclude_names=None):
    """Return (True, reason) if the game should be filtered out, else (False, '')."""

    # ---- include list override (never exclude these ROMs) ----
    if include_names:
        name_check = game_elem.get("name", "").lower()
        if name_check in include_names:
            return False, ""

    # ---- exclude list override (always exclude these ROMs) ----
    if exclude_names:
        name_check = game_elem.get("name", "").lower()
        if name_check in exclude_names:
            return True, "Exclude list"

    # ---- clone filtering ----
    if game_elem.get("cloneof"):
        return True, "Clone"

    # ---- BIOS filtering (isbios attribute) ----
    if game_elem.get("isbios", "").lower() == "yes":
        return True, "BIOS (isbios)"

    name = game_elem.get("name", "").lower()
    desc = game_elem.findtext("description", "")
    comment = game_elem.findtext("comment", "")
    manufacturer = game_elem.findtext("manufacturer", "")
    category = game_elem.findtext("category", "")

    desc_lower = desc.lower()
    mfr_lower = manufacturer.lower().strip()

    # ---- comment-based exclusion (keyword match, not blanket) ----
    # Exclude comments indicating broken/non-final/non-game content.
    # Keep games with informational comments (tips, cosmetic notes).
    if comment and comment.strip():
        cl = comment.strip().lower()
        _COMMENT_EXCLUDE_KEYWORDS = [
            "prototype", "homebrew", "bootleg", "hack", "demo",
            "bios only", "internal rom", "internal prom",
            "not currently emulated", "not emulated", "emulation not complete",
            "unemulated protection", "game unplayable",
            "not working",
        ]
        for kw in _COMMENT_EXCLUDE_KEYWORDS:
            if kw in cl:
                return True, f"Comment: {comment.strip()}"

    # ---- catver.ini category exclusion ----
    if catver_map and name in catver_map:
        return True, f"Category (catver): {catver_map[name]}"

    # ---- mature.ini / catlist.ini exclusion (supplements built-in list) ----
    if mature_names and name in mature_names and name not in _NAME_EXCLUDE_EXACT:
        return True, f"Mature/Adult (INI): {name}"

    # ---- ROM name exact match exclusion (built-in mature list) ----
    if name in _NAME_EXCLUDE_EXACT:
        return True, f"Mature/Adult: {name}"

    # ---- BIOS-like name pattern exclusion ----
    if name.endswith("_bios"):
        return True, "BIOS (name pattern)"

    # ---- ROM name prefix exclusion ----
    for prefix in _NAME_EXCLUDE_PREFIXES:
        if name.startswith(prefix):
            return True, f"Name prefix: {prefix}*"

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


def _is_pcb(desc):
    """Return 1 if the description indicates a dedicated PCB/hardware variant."""
    return 1 if re.search(r"\b(?:jamma\s*)?pcb\b|bubble\s*system\b", desc, re.IGNORECASE) else 0


def score_game(game_elem, clone_counts=None):
    """Return a sort-key tuple (lower = better candidate to keep)."""
    desc = game_elem.findtext("description", "")
    name = game_elem.get("name", "").lower()
    # Negate clone count so more clones = lower (better) score
    clone_score = -(clone_counts.get(name, 0)) if clone_counts else 0
    return (
        _region_score(detect_regions(desc)),
        _is_pcb(desc),
        clone_score,
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

def process_dat(input_path, output_dir=None, verbose=False, mature_names=None, catver_map=None, include_names=None, exclude_names=None):
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
        ex, reason = is_excluded(g, mature_names=mature_names, catver_map=catver_map, include_names=include_names, exclude_names=exclude_names)
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

    # --- Phase 1b: build clone count map (how many clones reference each parent) ---
    clone_counts = defaultdict(int)
    for g in all_games:
        parent = g.get("cloneof", "").lower()
        if parent:
            clone_counts[parent] += 1

    # --- Phase 2: group by title ---
    groups = defaultdict(list)
    for g in kept:
        desc = g.findtext("description", "")
        title = normalize_title(desc)
        key = grouping_key(title)
        # Different drivers = different games even if titles normalize the same
        sourcefile = g.get("sourcefile", "")
        if sourcefile:
            key = f"{key}|{sourcefile.lower()}"
        groups[key].append(g)

    # --- Phase 3: pick best per group ---
    selected = []
    dupes = 0
    for key, games in groups.items():
        if len(games) == 1:
            selected.append(games[0])
            continue

        scored = sorted(games, key=lambda g: score_game(g, clone_counts))
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
    ap.add_argument("-c", "--catver-folder", default=None,
                    help="Path to pS_CatVer_* folder containing catver.ini and UI_files/. "
                         "Auto-detected if not specified.")
    ap.add_argument("-i", "--include-file", default="include.txt",
                    help="Path to a text file listing ROMs to always keep (one per line, "
                         "with or without .zip). Default: include.txt in the current directory.")
    ap.add_argument("-e", "--exclude-file", default="exclude.txt",
                    help="Path to a text file listing ROMs to always exclude (one per line, "
                         "with or without .zip). Default: exclude.txt in the current directory.")
    args = ap.parse_args()

    # Load include list (ROMs that bypass all exclusion filters)
    include_names = load_include_list(args.include_file)
    if include_names:
        print(f"Include list: {len(include_names)} ROMs will bypass exclusion filters")

    # Load exclude list (ROMs that are always excluded)
    exclude_names = load_exclude_list(args.exclude_file)
    if exclude_names:
        print(f"Exclude list: {len(exclude_names)} ROMs will be force-excluded")

    # Check for conflicts between include and exclude lists
    conflicts = check_include_exclude_conflicts(include_names, exclude_names)
    if conflicts:
        print(f"\nERROR: {len(conflicts)} ROM(s) found in both include and exclude lists:")
        for name in sorted(conflicts):
            print(f"  {name}")
        print("\nResolve the conflicts by removing duplicates from one of the lists.")
        sys.exit(1)

    # Load all INI-based exclusions (auto-detect pS_CatVer_* folder)
    ini_excluded_names, catver_map = load_all_ini_exclusions(args.catver_folder)

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
            sel, tot = process_dat(fp, args.output_dir, args.verbose,
                                   ini_excluded_names, catver_map, include_names, exclude_names)
            grand_selected += sel
            grand_total += tot
        except Exception as e:
            print(f"  ERROR: {e}")

    print(f"\n{'=' * 60}")
    print(f"All done!  {grand_selected} games kept from {grand_total} total entries "
          f"across {len(files)} file(s).")


if __name__ == "__main__":
    main()
