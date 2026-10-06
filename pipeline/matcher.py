# pipeline/matcher.py
"""
Cross-store product matcher.
"""
import re
import hashlib
import logging
from dataclasses import dataclass
from rapidfuzz import fuzz

log = logging.getLogger(__name__)

WEIGHT_BRAND = 0.30
WEIGHT_QUANTITY = 0.20
WEIGHT_NAME = 0.50
MIN_MATCH_SCORE = 0.80

# Words we strip before fuzzy comparison — they vary between stores
# but don't distinguish products.
NOISE_PATTERNS = [
    r"\břeck[ýáé]\b",
]

# Keywords that are hard vetoes when present on ONE side only.
# These define the product — a "slané" butter is not the same as an
# unsalted one, no matter how similar the rest of the name is.

ONE_SIDED_KEYWORDS = [
    # existing ones...
    "bio", "high protein", "bez laktózy", "bezlaktóz", "slané", "neslané",
    "kefírové", "acidofilní", "zakysan", "farmářsk", "ovesné", "sojové",
    "mandlové", "kokosové", "rýžové", "plnotučn", "polotučn", "nízkotučn",
    # NEW — meat cuts
    "stehna", "stehno", "prsní", "řízky", "křídla", "křídlo", "čtvrtky",
    "kotleta", "kýta", "plec", "žebírka", "šunka", "slanina",
    # NEW — rice/variety
    "basmati", "jasmín", "parboiled", "dlouhozrnn", "loupan",
    # NEW — dairy types
    "smetan", "zakysan", "bílý", "ovocný",
]


def _normalize_name(name: str) -> str:
    if not name:
        return ""
    s = name.lower()
    s = re.sub(r"[(),]", " ", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def _normalize_brand(brand: str | None) -> str:
    if not brand:
        return ""
    return brand.lower().strip()


def _parse_quantity(unit_str: str | None) -> tuple[float, str] | None:
    if not unit_str:
        return None
    s = unit_str.lower().replace(",", ".").strip()
    m = re.match(r"([\d.]+)\s*(ml|l|g|kg|ks|kus|ks\.)", s)
    if not m:
        return None
    value = float(m.group(1))
    unit = m.group(2).rstrip(".")
    if unit == "l":
        return (value * 1000, "ml")
    if unit == "kg":
        return (value * 1000, "g")
    if unit in ("ks", "kus"):
        return (value, "ks")
    return (value, unit)


def _brand_similarity(b1: str, b2: str) -> float:
    if not b1 or not b2:
        return 0.0
    if b1 == b2:
        return 1.0
    score = fuzz.token_sort_ratio(b1, b2) / 100.0
    return score if score >= 0.70 else 0.0


def _quantity_similarity(q1, q2) -> float:
    if q1 is None or q2 is None:
        return 0.5
    v1, u1 = q1
    v2, u2 = q2
    if u1 != u2:
        return 0.0
    ratio = min(v1, v2) / max(v1, v2) if max(v1, v2) > 0 else 0.0
    if ratio >= 0.95:
        return 1.0
    return ratio


def _extract_fat_percent(name: str) -> float | None:
    m = re.search(r"(\d+[,.]?\d*)\s*%", name)
    if not m:
        return None
    return float(m.group(1).replace(",", "."))


def _shelflife_veto(n1: str, n2: str) -> bool:
    fresh_1 = "čerstv" in n1 or "cerstv" in n1
    fresh_2 = "čerstv" in n2 or "cerstv" in n2
    long_1 = "trvanliv" in n1
    long_2 = "trvanliv" in n2
    if fresh_1 and long_2:
        return True
    if long_1 and fresh_2:
        return True
    return False


def _name_similarity(n1: str, n2: str) -> float:
    if not n1 or not n2:
        return 0.0

    if _shelflife_veto(n1, n2):
        return 0.0

    # Fat %: veto only when BOTH sides declare a different value
    f1 = _extract_fat_percent(n1)
    f2 = _extract_fat_percent(n2)
    if f1 is not None and f2 is not None and abs(f1 - f2) > 0.1:
        return 0.0

    # One-sided keyword veto: if one name has a discriminating keyword and
    # the other doesn't, they are not the same product.
    for kw in ONE_SIDED_KEYWORDS:
        if (kw in n1) != (kw in n2):
            return 0.0

    s1 = n1
    s2 = n2
    for pat in NOISE_PATTERNS:
        s1 = re.sub(pat, " ", s1, flags=re.IGNORECASE)
        s2 = re.sub(pat, " ", s2, flags=re.IGNORECASE)
    s1 = re.sub(r"\s+", " ", s1).strip()
    s2 = re.sub(r"\s+", " ", s2).strip()

    return fuzz.token_set_ratio(s1, s2) / 100.0


@dataclass
class ProductRecord:
    store: str
    product_id: str
    name: str
    brand: str | None
    unit: str | None
    price: float


def score_pair(a: ProductRecord, b: ProductRecord) -> tuple[float, dict]:
    brand_sim = _brand_similarity(_normalize_brand(a.brand), _normalize_brand(b.brand))
    qty_sim = _quantity_similarity(_parse_quantity(a.unit), _parse_quantity(b.unit))
    name_sim = _name_similarity(_normalize_name(a.name), _normalize_name(b.name))

    if a.brand and b.brand and brand_sim == 0.0:
        return 0.0, {
            "brand": brand_sim, "quantity": qty_sim, "name": name_sim,
            "veto": "brand",
        }

    total = (
        WEIGHT_BRAND * brand_sim
        + WEIGHT_QUANTITY * qty_sim
        + WEIGHT_NAME * name_sim
    )
    return total, {"brand": brand_sim, "quantity": qty_sim, "name": name_sim}


def find_matches(target: ProductRecord, candidates: list[ProductRecord]) -> list[tuple[ProductRecord, float]]:
    scored = []
    for c in candidates:
        if c.store == target.store:
            continue
        score, _ = score_pair(target, c)
        if score >= MIN_MATCH_SCORE:
            scored.append((c, score))
    return sorted(scored, key=lambda x: x[1], reverse=True)


def canonical_key(product: ProductRecord) -> str:
    brand = _normalize_brand(product.brand) or "unknown"
    qty = _parse_quantity(product.unit)
    qty_str = f"{qty[0]}{qty[1]}" if qty else "unknown"

    name = _normalize_name(product.name)
    fat = _extract_fat_percent(name)
    fat_str = f"f{fat}" if fat is not None else "f?"

    shelf = "fresh" if "čerstv" in name else "long" if "trvanliv" in name else "any"

    raw = f"{brand}|{qty_str}|{shelf}|{fat_str}"
    return hashlib.sha1(raw.encode()).hexdigest()[:16]