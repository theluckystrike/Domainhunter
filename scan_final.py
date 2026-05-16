#!/usr/bin/env python3
"""
Premium Domain Scanner v3 (FINAL) — practical value assessment.
Focuses on what's ACTUALLY valuable from the dropping list.
"""

import csv
import re

CSV_PATH = "/Users/mike/Downloads/Dropping_Domains_All_2026-05-14.csv"

# ---------------------------------------------------------------------------
# Dictionaries & helpers
# ---------------------------------------------------------------------------
def load_full_dictionary():
    words = set()
    with open("/usr/share/dict/words") as f:
        for line in f:
            w = line.strip().lower()
            if w and w.isalpha():
                words.add(w)
    return words

VOWELS = set("aeiouy")

def is_pronounceable(name):
    name = name.lower()
    if not name.isalpha():
        return False
    n = len(name)
    if n <= 2:
        return True
    vowel_count = sum(1 for c in name if c in VOWELS)
    if vowel_count == 0:
        return False
    if n >= 4 and vowel_count < n / 4:
        return False
    consec = 0
    for c in name:
        if c not in VOWELS:
            consec += 1
            if consec > 3:
                return False
        else:
            consec = 0
    awkward = {
        "qz","qx","qk","qj","qv","qw","qp","qf","qg","qm","qn",
        "zx","zq","zj","xj","xq","xz","jx","jz","jq","bx","cx","dx",
        "fx","gx","hx","jj","kx","mx","px","vx","wx","xx","zz","bk",
        "fk","gq","kq","pq","vq","wq","bq","cj","dq","fq","gj","hq",
        "jb","jc","jd","jf","jg","jh","jk","jl","jm","jn","jp","jq",
        "jr","js","jt","jv","jw","kb","kd","kf","kg","kj","kp","kq",
        "kt","kv","kw","kz","lq","mq","nq","pj","pz","qb","qc","qd",
        "qe","qh","qi","qo","qq","qr","qs","qt","qy","rq","sq","tq",
        "vb","vc","vd","vf","vg","vh","vj","vk","vm","vn","vp","vt",
        "vw","vz","wj","wv","wz","xb","xc","xd","xf","xg","xh","xk",
        "xl","xm","xn","xr","xs","xv","xw","yq","yj","yz","zb","zd",
        "zf","zg","zk","zl","zm","zn","zp","zr","zs","zt","zv","zw",
    }
    for i in range(len(name)-1):
        if name[i:i+2] in awkward:
            return False
    return True

def has_cv_pattern(name):
    """Check if name has good consonant-vowel alternation (very brandable)."""
    name = name.lower()
    transitions = 0
    for i in range(len(name)-1):
        a_vowel = name[i] in VOWELS
        b_vowel = name[i+1] in VOWELS
        if a_vowel != b_vowel:
            transitions += 1
    return transitions >= len(name) * 0.5


# ---------------------------------------------------------------------------
# Recognizable / commercially interesting word lists
# ---------------------------------------------------------------------------
# Words that a typical English speaker would recognize and that have brand potential
RECOGNIZABLE_WORDS = set()
# Load full dict
full_dict = load_full_dictionary()

# Manually curated: words from the full dictionary that are actually recognizable
# We'll check the found domains against this by doing a manual human-eye filter in the output

# For scoring, we use a "recognizability" check: is the word in a common usage tier?
# We'll load a frequency list or use heuristics

# Heuristic: words that appear in BOTH the macOS dict AND look like normal English
# (not archaic, not scientific, not foreign)
def looks_recognizable(word):
    """Heuristic: does this word look like a normal, recognizable English word?"""
    w = word.lower()
    # Too many consecutive same letters
    for i in range(len(w)-2):
        if w[i] == w[i+1] == w[i+2]:
            return False
    # Common recognizable suffixes
    good_suffixes = ("ing", "tion", "ment", "ness", "able", "ible", "ful", "less",
                     "ous", "ive", "ary", "ery", "ory", "ize", "ise", "ate", "ure",
                     "ent", "ant", "ial", "ual", "ous", "ism", "ist", "ity")
    good_prefixes = ("un", "re", "pre", "over", "out", "under", "mis", "dis",
                     "up", "down", "fore", "back", "mid", "non", "sub", "super")
    # Very short words in dict are usually recognizable
    if len(w) <= 5 and w in full_dict:
        return True
    # 6+ letter words: check for common patterns
    has_good_suffix = any(w.endswith(s) for s in good_suffixes)
    has_good_prefix = any(w.startswith(p) for p in good_prefixes)
    if has_good_suffix or has_good_prefix:
        return True
    return False


# ---------------------------------------------------------------------------
# Main scan
# ---------------------------------------------------------------------------
def main():
    print(f"Dictionary: {len(full_dict):,} words")
    print(f"Scanning {CSV_PATH}...\n")

    # Collect ALL interesting domains
    all_finds = []  # (score, domain_full, name, tld, drop_date, category, tags)

    total = 0
    with open(CSV_PATH, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for row in reader:
            total += 1
            full_domain = row["Domain"].strip()
            tld = row["TLD"].strip().lower()
            drop_date = row.get("Drop Date", "").strip()

            if "." in full_domain:
                name = full_domain.rsplit(".", 1)[0]
                if "." in name:
                    continue
            else:
                name = full_domain

            nl = name.lower()
            n = len(nl)
            is_alpha = nl.isalpha()
            is_alnum = nl.isalnum()
            in_dict = nl in full_dict
            pron = is_alpha and is_pronounceable(nl)
            brandable = pron and has_cv_pattern(nl)

            # ---- Category: Single character ----
            if n == 1:
                tags = []
                if nl.isalpha():
                    tags.append("LETTER")
                else:
                    tags.append("DIGIT")
                score = 50000 if nl.isalpha() else 20000
                # TLD bonus
                premium_tlds = {"com": 5, "io": 3, "ai": 3, "co": 2.5, "net": 2, "org": 2}
                score *= premium_tlds.get(tld, 1.0)
                all_finds.append((score, f"{name}.{tld}", name, tld, drop_date, "1-char", tags))

            # ---- Category: 3-letter .com ----
            if n == 3 and tld == "com" and is_alpha:
                tags = []
                score = 15000
                if in_dict:
                    tags.append("WORD")
                    score *= 2.5
                if pron:
                    tags.append("PRON")
                    score *= 1.5
                elif not in_dict:
                    score *= 0.7  # unpronounceable non-word
                all_finds.append((score, f"{name}.{tld}", name, tld, drop_date, "3L .com", tags))

            # ---- Category: 4-letter .com ----
            if n == 4 and tld == "com" and is_alpha:
                tags = []
                score = 5000
                if in_dict:
                    tags.append("WORD")
                    score *= 3
                if pron:
                    tags.append("PRON")
                    if not in_dict:
                        score *= 1.5
                if brandable:
                    tags.append("BRANDABLE")
                    score *= 1.3
                if not pron and not in_dict:
                    continue  # skip garbage 4L
                all_finds.append((score, f"{name}.{tld}", name, tld, drop_date, "4L .com", tags))

            # ---- Category: Word .com 5-8 chars ----
            if 5 <= n <= 8 and tld == "com" and is_alpha and in_dict:
                tags = []
                base = {5: 3000, 6: 1500, 7: 800, 8: 500}
                score = base.get(n, 300)
                recog = looks_recognizable(nl)
                if recog:
                    tags.append("RECOGNIZABLE")
                    score *= 3
                else:
                    tags.append("OBSCURE")
                    score *= 1
                all_finds.append((score, f"{name}.{tld}", name, tld, drop_date, "word .com", tags))

            # ---- Category: 3-4 letter .io ----
            if 3 <= n <= 4 and tld == "io" and is_alpha:
                tags = []
                base = 8000 if n == 3 else 3000
                score = base
                if in_dict:
                    tags.append("WORD")
                    score *= 2
                if pron:
                    tags.append("PRON")
                    score *= 1.3
                if brandable:
                    tags.append("BRANDABLE")
                    score *= 1.2
                if not pron and not in_dict and n == 4:
                    score *= 0.5  # ugly 4L
                all_finds.append((score, f"{name}.{tld}", name, tld, drop_date, "short .io", tags))

            # ---- Category: 3-4 letter .net/.org ----
            if 3 <= n <= 4 and tld in ("net", "org") and is_alpha:
                tags = []
                base = 4000 if n == 3 else 1500
                score = base
                if in_dict:
                    tags.append("WORD")
                    score *= 2
                if pron:
                    tags.append("PRON")
                    score *= 1.3
                if brandable:
                    tags.append("BRANDABLE")
                    score *= 1.2
                if not pron and not in_dict and n == 4:
                    score *= 0.5
                all_finds.append((score, f"{name}.{tld}", name, tld, drop_date, f"short .{tld}", tags))

    print(f"Scanned {total:,} domains total")
    print(f"Found {len(all_finds):,} interesting domains\n")

    # Sort by score
    all_finds.sort(key=lambda x: -x[0])

    # Deduplicate
    seen = set()
    unique = []
    for item in all_finds:
        key = item[1].lower()
        if key not in seen:
            seen.add(key)
            unique.append(item)

    # =====================================================================
    # Print by category
    # =====================================================================
    categories = [
        ("1-char", "SINGLE-CHARACTER DOMAINS", 10),
        ("3L .com", "3-LETTER .COM DOMAINS", 10),
        ("4L .com", "4-LETTER .COM DOMAINS (words/pronounceable)", 30),
        ("word .com", "ENGLISH WORD .COM DOMAINS (5-8 chars)", 40),
        ("short .io", "3-4 LETTER .IO DOMAINS", 30),
        ("short .net", "3-4 LETTER .NET DOMAINS", 20),
        ("short .org", "3-4 LETTER .ORG DOMAINS", 20),
    ]

    for cat_key, cat_label, limit in categories:
        cat_items = [x for x in unique if x[5] == cat_key]
        print(f"{'='*80}")
        print(f"  {cat_label}  ({len(cat_items)} found)")
        print(f"{'='*80}")
        if not cat_items:
            print("  (none)\n")
            continue
        for i, (score, domain, name, tld, drop, cat, tags) in enumerate(cat_items[:limit], 1):
            tag_str = ", ".join(tags) if tags else ""
            print(f"  {i:>3}. {domain:<24} Score:{score:>9.0f}  [{tag_str:<25}]  Drop: {drop}")
        if len(cat_items) > limit:
            print(f"       ... and {len(cat_items) - limit} more")
        print()

    # =====================================================================
    # GRAND TOP 50
    # =====================================================================
    print(f"\n{'#'*80}")
    print(f"  TOP 50 MOST VALUABLE DROPPING DOMAINS — 2026-05-14")
    print(f"{'#'*80}")
    print(f"  {'#':<4} {'Domain':<26} {'Score':>9}  {'Category':<16} {'Tags':<28} {'Drop'}")
    print(f"  {'─'*4} {'─'*26} {'─'*9}  {'─'*16} {'─'*28} {'─'*10}")

    for i, (score, domain, name, tld, drop, cat, tags) in enumerate(unique[:50], 1):
        tag_str = ", ".join(tags)
        print(f"  {i:>3}. {domain:<26} {score:>9.0f}  {cat:<16} {tag_str:<28} {drop}")

    # =====================================================================
    # Actionable picks — human-curated style assessment
    # =====================================================================
    print(f"\n\n{'*'*80}")
    print(f"  ACTIONABLE PICKS — DOMAINS WORTH REGISTERING")
    print(f"{'*'*80}")

    # Filter for genuinely interesting ones
    picks = []
    for score, domain, name, tld, drop, cat, tags in unique:
        nl = name.lower()
        n = len(nl)

        # 1-char domains: always valuable
        if cat == "1-char" and nl.isalpha():
            picks.append((score * 2, domain, drop, cat, "Single letter domain — extremely rare", tags))
            continue

        # 3L .com: always interesting
        if cat == "3L .com":
            note = "3-letter .com — "
            if "WORD" in tags:
                note += "real word, very high value"
            elif "PRON" in tags:
                note += "pronounceable, strong brandable"
            else:
                note += "abbreviation potential"
            picks.append((score * 1.5, domain, drop, cat, note, tags))
            continue

        # 4L .com words
        if cat == "4L .com" and "WORD" in tags:
            picks.append((score, domain, drop, cat, "4-letter word .com — solid value", tags))
            continue

        # 4L .com brandable
        if cat == "4L .com" and "BRANDABLE" in tags:
            picks.append((score, domain, drop, cat, "4-letter brandable .com", tags))
            continue

        # Word .com recognizable
        if cat == "word .com" and "RECOGNIZABLE" in tags:
            picks.append((score, domain, drop, cat, f"Real English word .com ({n} chars)", tags))
            continue

        # 3L .io
        if cat == "short .io" and n == 3:
            note = "3-letter .io — "
            if "WORD" in tags:
                note += "word, premium"
            elif "PRON" in tags:
                note += "pronounceable"
            else:
                note += "short code"
            picks.append((score * 0.8, domain, drop, cat, note, tags))
            continue

        # 4L .io words
        if cat == "short .io" and n == 4 and ("WORD" in tags or "BRANDABLE" in tags):
            picks.append((score * 0.6, domain, drop, cat, "4-letter .io — brandable/word", tags))
            continue

    picks.sort(key=lambda x: -x[0])

    for i, (score, domain, drop, cat, note, tags) in enumerate(picks[:30], 1):
        print(f"\n  {i:>2}. {domain}")
        print(f"      Category: {cat}  |  Score: {score:.0f}  |  Drop: {drop}")
        print(f"      {note}")

    # Summary stats
    print(f"\n\n{'='*80}")
    print(f"  SCAN SUMMARY")
    print(f"{'='*80}")
    cat_counts = {}
    for item in unique:
        c = item[5]
        cat_counts[c] = cat_counts.get(c, 0) + 1
    for c in sorted(cat_counts.keys()):
        print(f"  {c:<20} {cat_counts[c]:>6} domains")
    print(f"  {'TOTAL':<20} {len(unique):>6} domains")
    print(f"  Actionable picks:  {min(len(picks), 30)}")
    print()


if __name__ == "__main__":
    main()
