#!/usr/bin/env python3
"""Turn spoken numbers into single caption tokens.

Whisper writes the same amount many ways: "five thousand dollars", "5000 dollars", "$5000", "25" + ",000",
"one lakh rupees". This module rewrites each of them as one token ("$5,000", "25,000", "₹1 lakh") that spans the
time of all the words it replaced, so a caption never splits an amount across lines or pages.

    from spoken_numbers import normalise_numbers     (scripts/ is on the path when group.py runs)
    python3 scripts/spoken_numbers.py "gold is at five thousand dollars, up 40 percent"     # prints the rewritten line

Standard library only.
"""
import re
import sys

ONES = {w: i for i, w in enumerate(
    "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen "
    "eighteen nineteen".split())}
TENS = {"twenty": 20, "thirty": 30, "forty": 40, "fourty": 40, "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90}
# multipliers written out in digits ("5 thousand" -> "5,000") ...
SMALL_MULT = {"hundred": 100, "thousand": 1000, "hazaar": 1000, "hazar": 1000, "sau": 100}
# ... and multipliers kept as a word, because "$5 million" and "₹5 lakh" read better than a row of zeros
BIG_MULT = {"million": "million", "billion": "billion", "trillion": "trillion", "lakh": "lakh", "lakhs": "lakh", "lac": "lakh",
            "lacs": "lakh", "crore": "crore", "crores": "crore", "karod": "crore", "cr": "crore"}
BIG_VALUE = {"million": 10 ** 6, "billion": 10 ** 9, "trillion": 10 ** 12, "lakh": 10 ** 5, "crore": 10 ** 7}
CURRENCY_WORD = {"dollar": "$", "dollars": "$", "bucks": "$", "usd": "$", "rupee": "₹", "rupees": "₹", "rupaye": "₹", "rupay": "₹",
                 "rupiya": "₹", "rupaiye": "₹", "inr": "₹", "rs": "₹", "euro": "€", "euros": "€", "pound": "£", "pounds": "£"}
CURRENCY_PREFIX = {"rs": "₹", "rs.": "₹", "inr": "₹", "usd": "$", "rupees": "₹"}
PERCENT_WORD = {"percent", "percentage", "pct"}
SIGNS = "$₹€£"
# Hindi number words, used only when the language is Hindi and a multiplier or currency word follows ("paanch lakh").
HINDI_ONES = {"ek": 1, "do": 2, "teen": 3, "char": 4, "chaar": 4, "paanch": 5, "panch": 5, "chhe": 6, "cheh": 6, "saat": 7,
              "aath": 8, "nau": 9, "das": 10, "bees": 20, "pachas": 50, "pachaas": 50}

LEAD = re.compile(r"^[^\w$₹€£]+", re.UNICODE)
TRAIL = re.compile(r"[^\w%]+$", re.UNICODE)
DIGITS = re.compile(r"^\d[\d,]*(\.\d+)?$")


def _core(text):
    """(leading punctuation, core, trailing punctuation). The core keeps $ ₹ % and inner commas."""
    lead = LEAD.match(text)
    lead = lead.group(0) if lead else ""
    rest = text[len(lead):]
    trail = TRAIL.search(rest)
    trail = trail.group(0) if trail else ""
    return lead, rest[:len(rest) - len(trail)] if trail else rest, trail


def group_digits(n, indian=False):
    """5000 -> "5,000"; with indian=True 500000 -> "5,00,000"."""
    s = str(int(n))
    if not indian or len(s) <= 3:
        return f"{int(n):,}"
    head, tail = s[:-3], s[-3:]
    parts = []
    while len(head) > 2:
        parts.insert(0, head[-2:])
        head = head[:-2]
    if head:
        parts.insert(0, head)
    return ",".join(parts + [tail])


def _fmt(value, indian=False, year_ok=False):
    """A number as caption text. Whole numbers get separators; 1900-2100 stays a bare year when year_ok."""
    if isinstance(value, float) and not value.is_integer():
        whole, frac = f"{value:.4f}".rstrip("0").split(".")
        return group_digits(int(whole), indian) + "." + frac
    v = int(value)
    if year_ok and 1900 <= v <= 2100:
        return str(v)
    return group_digits(v, indian)


def _parse_digits(core):
    """"5,000" / "5000" / "3.5" -> number, or None."""
    if not DIGITS.match(core):
        return None
    s = core.replace(",", "")
    return float(s) if "." in s else int(s)


def _read_number(cores, i, hindi=False):
    """Read a number that starts at cores[i]. Returns (value, big_word, count, spelled, words_used, is_year) or None.

    value is the number before the kept multiplier: "five million" -> (5, "million"), "five thousand" -> (5000, None).
    spelled is True when at least one number word (not digits) was used. words_used counts number words and digits.
    """
    n = len(cores)
    j = i
    total, cur, used, spelled, any_num = 0, None, 0, False, False
    big = None
    year_pair = None
    while j < n:
        c = cores[j].lower()
        d = _parse_digits(cores[j])
        if d is not None and cur is None and not any_num:
            cur, any_num = d, True
            used += 1
        elif c in ONES and not (c == "zero" and any_num):
            v = ONES[c]
            if cur is None:
                cur = v
            elif isinstance(cur, int) and cur >= 20 and cur % 10 == 0 and cur < 100 and 0 < v < 10:
                cur += v  # twenty + five
            elif isinstance(cur, int) and cur % 100 == 0 and cur >= 100:
                cur += v  # five hundred + six
            elif isinstance(cur, int) and 10 <= cur <= 99 and v >= 10 and year_pair is None and total == 0:
                year_pair, cur = cur, v  # "nineteen" "ninety" -> a year
            else:
                break
            any_num = spelled = True
            used += 1
        elif c in TENS:
            v = TENS[c]
            if cur is None:
                cur = v
            elif isinstance(cur, int) and cur % 100 == 0 and cur >= 100:
                cur += v
            elif isinstance(cur, int) and 10 <= cur <= 99 and year_pair is None and total == 0:
                year_pair, cur = cur, v  # "nineteen ninety one", "twenty twenty four"
            else:
                break
            any_num = spelled = True
            used += 1
        elif hindi and c in HINDI_ONES and cur is None and j + 1 < n and (
                cores[j + 1].lower() in SMALL_MULT or cores[j + 1].lower() in BIG_MULT or cores[j + 1].lower() in CURRENCY_WORD):
            cur, any_num, spelled = HINDI_ONES[c], True, True
            used += 1
        elif c in SMALL_MULT and cur is not None:
            m = SMALL_MULT[c]
            if m == 100:
                if year_pair is not None or (isinstance(cur, float)):
                    break
                cur = cur * 100
            else:
                total += cur * m
                cur = None
            any_num = spelled = True
            used += 1
        elif c in BIG_MULT and cur is not None and big is None:
            big = BIG_MULT[c]
            spelled = True
            used += 1
            j += 1
            break
        elif c == "and" and any_num and j + 1 < n and (cores[j + 1].lower() in ONES or cores[j + 1].lower() in TENS) \
                and ((cur is not None and isinstance(cur, int) and cur % 100 == 0) or (cur is None and total)):
            pass  # "five hundred and twenty", "two thousand and five hundred"
        elif c == "point" and cur is not None and j + 1 < n and (cores[j + 1].lower() in ONES or re.fullmatch(r"\d+", cores[j + 1])):
            k, frac = j + 1, ""
            while k < n and (cores[k].lower() in ONES and ONES[cores[k].lower()] < 10 or re.fullmatch(r"\d+", cores[k])):
                frac += str(ONES[cores[k].lower()]) if cores[k].lower() in ONES else cores[k]
                k += 1
            cur = float(f"{int(cur)}.{frac}")
            spelled = True
            used += k - j
            j = k
            continue
        else:
            break
        j += 1
    if not any_num:
        return None
    if year_pair is not None:
        if cur is None or total:
            return None
        value = year_pair * 100 + cur  # 19 | 91 -> 1991
        if not 1100 <= value <= 2099:
            return None
    else:
        value = total + (cur or 0)
    return value, big, j - i, spelled, used, year_pair is not None


def normalise_numbers(words, language=None, grouping="auto"):
    """Rewrite number phrases in a list of {text, startMs, endMs, ...} as single tokens. Returns a new list.

    grouping: "western" (5,000,000), "indian" (50,00,000) or "auto" (Indian with ₹ amounts or Hindi speech).
    """
    hindi = (language or "").lower().startswith("hi")
    parts = [_core(w["text"]) for w in words]
    cores = [p[1] for p in parts]
    out = []
    i, n = 0, len(words)

    def closed(a, b):
        """True when no sentence or clause punctuation sits between word a and word b (inside the phrase)."""
        return all(not re.search(r"[.,!?;:…]", parts[k][2]) and not parts[k + 1][0] for k in range(a, b))

    while i < n:
        lead, core, trail = parts[i]
        low = core.lower()
        sign = ""
        start = i
        j = i
        # "Rs 500", "Rs. 5 lakh", "rupees 500"
        if low.rstrip(".") in CURRENCY_PREFIX and i + 1 < n and not re.search(r"[!?;:…,]", parts[i][2]) and (
                _parse_digits(cores[i + 1]) is not None or cores[i + 1].lower() in ONES or cores[i + 1].lower() in TENS):
            sign = CURRENCY_PREFIX[low.rstrip(".")]
            j = i + 1
        # "$5000", "$5", "₹500"
        elif core[:1] in SIGNS and _parse_digits(core[1:]) is not None:
            sign = core[0]
            cores[i] = core[1:]
        # "a hundred", "a thousand", "a lakh"
        elif low in ("a", "ek") and i + 1 < n and closed(i, i + 1) and (cores[i + 1].lower() in SMALL_MULT or cores[i + 1].lower() in BIG_MULT) \
                and (low == "a" or hindi) and (cores[i + 1].lower() in SMALL_MULT or (
                    i + 2 < n and closed(i + 1, i + 2) and cores[i + 2].lower() in CURRENCY_WORD)):
            cores[i] = "one"
        got = _read_number(cores, j, hindi)
        # A percent sign glued on by the transcriber ("10%") is already one token: leave it, but still group the digits.
        if got is None:
            m = re.fullmatch(r"([$₹€£]?)(\d[\d,]*(?:\.\d+)?)(%|x|k|K|M|B)?", core)
            if m and m.group(2):
                v = _parse_digits(m.group(2))
                indian = grouping == "indian" or (grouping == "auto" and (m.group(1) == "₹" or hindi))
                txt = m.group(1) + _fmt(v, indian, year_ok=not m.group(1) and not m.group(3) and "," not in m.group(2)) + (m.group(3) or "")
                w = dict(words[i])
                w["text"] = lead + txt + trail
                out.append(w)
            else:
                out.append(dict(words[i]))
            i += 1
            continue
        value, big, count, spelled, used, is_year = got
        end = j + count  # exclusive
        # the phrase must not cross punctuation
        while end - 1 > j and not closed(j, end - 1):
            end -= 1
            got = None
        if got is None:
            sub = _read_number(cores[:end], j, hindi)
            if sub is None:
                out.append(dict(words[i]))
                i += 1
                continue
            value, big, count, spelled, used, is_year = sub
            end = j + count
        suffix = ""
        # what follows: a currency word, a percent word
        nxt = cores[end].lower() if end < n and closed(end - 1, end) else ""
        if nxt in CURRENCY_WORD and not sign:
            sign = CURRENCY_WORD[nxt]
            end += 1
        elif nxt in PERCENT_WORD or (nxt == "per" and end + 1 < n and cores[end + 1].lower() == "cent" and closed(end, end + 1)):
            suffix = "%"
            end += 2 if nxt == "per" else 1
        only_digit = count == 1 and not spelled
        # Leave small spelled numbers alone ("three times", "one of them"): rewrite only when there is a unit,
        # a multiplier, or more than one number word.
        if not (sign or suffix or big or used >= 2 or only_digit):
            out.append(dict(words[i]))
            i += 1
            continue
        indian = grouping == "indian" or (grouping == "auto" and (sign == "₹" or hindi or big in ("lakh", "crore")))
        bare_year = only_digit and not sign and not suffix and "," not in cores[j]
        txt = sign + _fmt(value, indian, year_ok=(bare_year or is_year) and not sign and not suffix and not big)
        if big:
            txt += " " + big
        txt += suffix
        w = dict(words[start])
        w["text"] = parts[start][0] + txt + parts[end - 1][2]
        w["endMs"] = max(x["endMs"] for x in words[start:end])
        if end - start > 1:
            w["prob"] = None
        out.append(w)
        i = end
    return out


if __name__ == "__main__":
    line = " ".join(sys.argv[1:]) or "gold is at five thousand dollars, up 40 percent since 1991"
    ws = [{"text": t, "startMs": k * 300, "endMs": k * 300 + 280} for k, t in enumerate(line.split())]
    print(" | ".join(w["text"] for w in normalise_numbers(ws)))
