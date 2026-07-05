"""Model-family matching rules — the domain knowledge of this project.

Each rule is (family, brand_pattern, text_pattern, product_type or None).
A listing joins the FIRST family whose brand pattern matches its make and
whose text pattern matches its model+title. Order matters: budget brands
(Squier, Epiphone, PRS SE) sit above their premium siblings so "Fender
Squier Strat" lands in the Squier family, and specific models sit above
general ones.

Guitars matching no rule stay unmatched on purpose: boutique and obscure
instruments don't have enough comparable listings to price honestly.
"""

import re


def both(a, b):
    """Pattern requiring BOTH a and b to appear somewhere in the text."""
    return rf"(?=.*(?:{a}))(?=.*(?:{b}))"


# Factory tiers of the same model are different products at different
# prices (a Mexican-made Strat is not comparable to an American one).
CUSTOM_SHOP = r"custom shop(?!\s*design)|masterbuilt|murphy|historic"
AMERICAN = r"american|\busa\b|\bu\.s\."
JAPAN = r"\bmij\b|\bcij\b|japan"
MEXICO = r"player\b|\bmim\b|mexic|\bstandard\b|road worn|vintera|classic series|blacktop|\bdeluxe\b"

R = [
    # ---- budget sub-brands first (their titles often name the parent brand)
    ("Squier Stratocaster",      r"squier|squire\b|squirer", r"strat", "electric-guitars"),
    ("Squier Telecaster",        r"squier|squire\b|squirer", r"\btele", "electric-guitars"),
    ("Squier Jazzmaster/Jaguar", r"squier|squire\b|squirer", r"jazzmaster|jaguar", "electric-guitars"),
    ("Squier Precision Bass",    r"squier|squire\b|squirer", r"precision|\bp[- ]?bass", "bass-guitars"),
    ("Squier Jazz Bass",         r"squier|squire\b|squirer", r"jazz\s?bass|\bj[- ]?bass", "bass-guitars"),
    ("Epiphone Les Paul",        r"epiphone", r"les\s?paul", None),
    ("Epiphone SG Special",      r"epiphone", both(r"\bsg\b", r"special"), None),
    ("Epiphone SG",              r"epiphone", r"\bsg\b", None),
    ("Epiphone Casino",          r"epiphone", r"casino", None),
    ("Epiphone ES/Dot",          r"epiphone", r"\bes[- ]?\d|dot", None),
    ("PRS SE",                   r"\bprs\b|paul reed", r"\bse\b", None),
    ("PRS S2",                   r"\bprs\b|paul reed", r"\bs2\b", None),

    # ---- Fender (tiered: specific factory lines before the catch-all)
    ("Fender Stratocaster (Japan)",       r"fender", both(r"strat", JAPAN), "electric-guitars"),
    ("Fender Stratocaster (Custom Shop)", r"fender", both(r"strat", CUSTOM_SHOP), "electric-guitars"),
    ("Fender Stratocaster (American)",    r"fender", both(r"strat", AMERICAN), "electric-guitars"),
    ("Fender Stratocaster (Mexico)",      r"fender", both(r"strat", MEXICO), "electric-guitars"),
    ("Fender Stratocaster (other)",       r"fender", r"strat", "electric-guitars"),
    ("Fender Telecaster (Japan)",         r"fender", both(r"\btele", JAPAN), "electric-guitars"),
    ("Fender Telecaster (Custom Shop)",   r"fender", both(r"\btele", CUSTOM_SHOP), "electric-guitars"),
    ("Fender Telecaster (American)",      r"fender", both(r"\btele", AMERICAN), "electric-guitars"),
    ("Fender Telecaster (Mexico)",        r"fender", both(r"\btele", MEXICO), "electric-guitars"),
    ("Fender Telecaster (other)",         r"fender", r"\btele", "electric-guitars"),
    ("Fender Jazzmaster (Japan)",       r"fender", both(r"jazzmaster", JAPAN), "electric-guitars"),
    ("Fender Jazzmaster (Custom Shop)", r"fender", both(r"jazzmaster", CUSTOM_SHOP), "electric-guitars"),
    ("Fender Jazzmaster (American)",    r"fender", both(r"jazzmaster", AMERICAN), "electric-guitars"),
    ("Fender Jazzmaster (Mexico)",      r"fender", both(r"jazzmaster", MEXICO), "electric-guitars"),
    ("Fender Jazzmaster (other)",       r"fender", r"jazzmaster", "electric-guitars"),
    ("Fender Jaguar (Japan)",     r"fender", both(r"jaguar", JAPAN), "electric-guitars"),
    ("Fender Jaguar (American)",  r"fender", both(r"jaguar", AMERICAN), "electric-guitars"),
    ("Fender Jaguar (Mexico)",    r"fender", both(r"jaguar", MEXICO), "electric-guitars"),
    ("Fender Jaguar (other)",     r"fender", r"jaguar", "electric-guitars"),
    ("Fender Mustang/Duo-Sonic", r"fender", r"mustang|duo[- ]?sonic", "electric-guitars"),
    ("Fender Precision Bass (American)", r"fender", both(r"precision|\bp[- ]?bass", AMERICAN), "bass-guitars"),
    ("Fender Precision Bass (Mexico)",   r"fender", both(r"precision|\bp[- ]?bass", MEXICO), "bass-guitars"),
    ("Fender Precision Bass (other)",    r"fender", r"precision|\bp[- ]?bass", "bass-guitars"),
    ("Fender Jazz Bass (American)", r"fender", both(r"jazz\s?bass|\bj[- ]?bass", AMERICAN), "bass-guitars"),
    ("Fender Jazz Bass (Mexico)",   r"fender", both(r"jazz\s?bass|\bj[- ]?bass", MEXICO), "bass-guitars"),
    ("Fender Jazz Bass (other)",    r"fender", r"jazz\s?bass|\bj[- ]?bass", "bass-guitars"),
    ("Fender Mustang Bass",      r"fender", r"mustang", "bass-guitars"),
    ("Fender CD/FA Acoustic",    r"fender", r"\bcd[- ]?\d|\bfa[- ]?\d", "acoustic-guitars"),

    # ---- Gibson (Les Paul tiered the same way; Sonex first — sellers
    # file this budget 80s model as a Les Paul)
    ("Gibson Sonex",             r"gibson", r"sonex", "electric-guitars"),
    ("Gibson Les Paul (Custom Shop)", r"gibson", both(r"les\s?paul|\blp\b", CUSTOM_SHOP), "electric-guitars"),
    ("Gibson Les Paul Custom",   r"gibson", both(r"les\s?paul|\blp\b", r"\bcustom\b"), "electric-guitars"),
    ("Gibson Les Paul Studio",   r"gibson", both(r"les\s?paul|\blp\b", r"studio"), "electric-guitars"),
    ("Gibson Les Paul Tribute",  r"gibson", both(r"les\s?paul|\blp\b", r"tribute"), "electric-guitars"),
    ("Gibson Les Paul Jr/Special", r"gibson", both(r"les\s?paul|\blp\b", r"junior|\bjr\b|special"), "electric-guitars"),
    ("Gibson Les Paul Classic",  r"gibson", both(r"les\s?paul|\blp\b", r"classic"), "electric-guitars"),
    ("Gibson Les Paul Standard", r"gibson", both(r"les\s?paul|\blp\b", r"standard"), "electric-guitars"),
    ("Gibson Les Paul (other)",  r"gibson", r"les\s?paul|\blp\b", "electric-guitars"),
    ("Gibson Melody Maker",      r"gibson", r"melody\s?maker", "electric-guitars"),
    ("Gibson SG",                r"gibson", r"\bsg\b", "electric-guitars"),
    ("Gibson ES-335 family",     r"gibson", r"\bes[- ]?3\d{2}\b|\b3[345]5\b|\b339\b", None),
    ("Gibson Flying V",          r"gibson", r"flying\s?v", None),
    ("Gibson Explorer",          r"gibson", r"explorer", None),
    ("Gibson Firebird",          r"gibson", r"firebird", None),
    ("Gibson J-45",              r"gibson", r"\bj[- ]?45\b", "acoustic-guitars"),
    ("Gibson Hummingbird",       r"gibson", r"hummingbird", "acoustic-guitars"),
    ("Gibson J-200/SJ-200",      r"gibson", r"\bs?j[- ]?200\b", "acoustic-guitars"),
    ("Gibson Dove",              r"gibson", r"\bdove\b", "acoustic-guitars"),

    # ---- PRS core
    ("PRS Silver Sky",           r"\bprs\b|paul reed", r"silver\s?sky", None),
    ("PRS Custom 24",            r"\bprs\b|paul reed", r"custom\s?24", None),
    ("PRS Custom 22",            r"\bprs\b|paul reed", r"custom\s?22", None),
    ("PRS McCarty",              r"\bprs\b|paul reed", r"mccarty", None),
    ("PRS CE",                   r"\bprs\b|paul reed", r"\bce\b", None),

    # ---- other electrics
    ("Ibanez RG",                r"ibanez", r"\brg", "electric-guitars"),
    ("Ibanez AZ",                r"ibanez", r"\baz\d", "electric-guitars"),
    ("Ibanez JEM",               r"ibanez", r"\bjem\b", "electric-guitars"),
    ("Ibanez Artcore",           r"ibanez", r"artcore|\bas\d|\baf\d|\bag\d", None),
    ("Ibanez SR Bass",           r"ibanez", r"\bsr\d|soundgear", "bass-guitars"),
    ("Jackson Soloist",          r"jackson", r"soloist|\bsl\d", "electric-guitars"),
    ("Jackson Dinky JS (budget)", r"jackson", both(r"dinky|\bdk\d?|\bjs\d", r"\bjs\d"), "electric-guitars"),
    ("Jackson Dinky",            r"jackson", r"dinky|\bdk\d?", "electric-guitars"),
    ("Jackson Rhoads",           r"jackson", r"rhoads|\brr\d?", "electric-guitars"),
    ("Charvel Pro-Mod/So-Cal",   r"charvel", r"pro[- ]?mod|so[- ]?cal|dk2", "electric-guitars"),
    ("ESP/LTD EC",               r"\besp\b|\bltd\b", r"\bec[- ]?\d{3,4}|eclipse", "electric-guitars"),
    ("Schecter C-1/Hellraiser",  r"schecter", r"\bc[- ]?1\b|hellraiser|omen", "electric-guitars"),
    ("Gretsch White Falcon",     r"gretsch", r"white\s?falcon", None),
    ("Gretsch 6120/Nashville",   r"gretsch", r"6120|nashville", None),
    ("Gretsch Electromatic",     r"gretsch", r"electromatic|\bg5\d{3}", None),
    ("Gretsch Streamliner",      r"gretsch", r"streamliner|\bg2\d{3}", None),
    ("Rickenbacker 330/360",     r"rickenbacker", r"\b3[36]0\b", "electric-guitars"),
    ("Rickenbacker 4001/4003",   r"rickenbacker", r"\b400[13]\b", "bass-guitars"),
    ("Music Man StingRay Bass",  r"music\s?man", r"sting\s?ray", "bass-guitars"),
    ("Hofner Violin Bass",       r"hofner|höfner", r"violin|500/1", "bass-guitars"),
    ("Yamaha Pacifica (budget 012-212)", r"yamaha", both(r"pacifica|\bpac\d", r"\bpac?\s?[0-2]\d\d"), "electric-guitars"),
    ("Yamaha Pacifica",          r"yamaha", r"pacifica", "electric-guitars"),

    # ---- acoustics
    ("Martin D-28",              r"martin", r"\bd[- ]?28\b|hd[- ]?28", "acoustic-guitars"),
    ("Martin D-18",              r"martin", r"\bd[- ]?18\b", "acoustic-guitars"),
    ("Martin D-35",              r"martin", r"\bd[- ]?35\b", "acoustic-guitars"),
    ("Martin D-15",              r"martin", r"\bd[- ]?15", "acoustic-guitars"),
    ("Martin D-41/45",           r"martin", r"\bd[- ]?4[15]\b", "acoustic-guitars"),
    ("Martin 000",               r"martin", r"\b000|triple[- ]?o", "acoustic-guitars"),
    ("Martin OM",                r"martin", r"\bomc?[- ]?\d", "acoustic-guitars"),
    ("Martin X Series",          r"martin", r"\b[dg0]?x\d|x series", "acoustic-guitars"),
    ("Taylor GS Mini",           r"taylor", r"gs\s?mini", "acoustic-guitars"),
    ("Taylor Baby/Big Baby",     r"taylor", r"\bbaby\b|bt\d", "acoustic-guitars"),
    ("Taylor 100/200 Series",    r"taylor", r"\b[12]1[0246](ce)?\b|\b[12]5[0-9](ce)?\b", "acoustic-guitars"),
    ("Taylor 300/400 Series",    r"taylor", r"\b[34][12][0-9](ce)?\b", "acoustic-guitars"),
    ("Taylor 500-900 Series",    r"taylor", r"\b[5-9][12][0-9](ce)?\b", "acoustic-guitars"),
    ("Yamaha FG/FS",             r"yamaha", r"\bfgx?[- ]?\d|\bfsx?[- ]?\d", "acoustic-guitars"),
]

RULES = [(fam, re.compile(b), re.compile(t), pt) for fam, b, t, pt in R]


SQUIER_IN_TEXT = re.compile(r"squier|squire\b|squirer")


def effective_brand(make, text):
    """The brand we trust for sorting.

    Usually the seller's make field. Two systematic misfilings are
    corrected from the text: Squiers listed under Fender (in several
    spellings) and Epiphones listed under Gibson. Text mentions never
    otherwise override the make field — plenty of listings name-drop
    brands they aren't ("Gibson-licensed", "compares to a Fender").
    """
    brand = (make or "").lower()
    if SQUIER_IN_TEXT.search(text):
        return "squier"
    if "orville" in brand:            # "Orville by Gibson" is not Gibson
        return "orville"
    if "sterling" in brand or "sterling by" in text:  # Music Man's import brand
        return "sterling"
    if "epiphone" in brand or ("epiphone" in text and "gibson" in brand):
        return "epiphone"
    return brand


def match_family(make, model, title, product_type):
    """Return the family for a listing, or None if it stays unmatched."""
    text = f"{model or ''} {title or ''}".lower()
    brand = effective_brand(make, text)
    for family, bpat, tpat, pt in RULES:
        if pt is not None and pt != product_type:
            continue
        if bpat.search(brand) and tpat.search(text):
            return family
    return None
