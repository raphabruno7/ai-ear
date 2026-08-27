"""Accuracy metrics for the phonetic name/email golden-set A/B.

Pure functions, no deps beyond stdlib + `jellyfish` (metaphone). Self-checked
against hand-computed values in demo().
"""

from __future__ import annotations

import re

try:
    from jellyfish import metaphone
except ImportError:  # keep the module importable for the self-check environment
    metaphone = None


def normalize(s: str) -> str:
    """Lowercase, strip punctuation except @/. (emails), collapse whitespace."""
    s = s.strip().lower()
    s = s.replace("'", "").replace("’", "")  # O'Brien -> obrien
    s = re.sub(r"[^\w@.\s]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def exact_match(expected: str, got: str) -> bool:
    return normalize(expected) == normalize(got)


def levenshtein(a: str, b: str) -> int:
    if len(a) < len(b):
        a, b = b, a
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def lev_norm(expected: str, got: str) -> float:
    e, g = normalize(expected), normalize(got)
    if not e and not g:
        return 0.0
    return levenshtein(e, g) / max(len(e), len(g))


def wer(expected: str, got: str) -> float:
    """Word error rate = Levenshtein over word sequences / expected word count."""
    e = normalize(expected).split()
    g = normalize(got).split()
    if not e:
        return 0.0 if not g else 1.0
    # token-level Levenshtein
    prev = list(range(len(g) + 1))
    for i, we in enumerate(e, 1):
        cur = [i]
        for j, wg in enumerate(g, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (we != wg)))
        prev = cur
    return prev[-1] / len(e)


def phonetic_ok(expected: str, got: str, kind: str) -> bool:
    """For names: metaphone codes must match. For emails: exact local+domain
    match after normalising 'at'/'dot' spellouts."""
    if kind == "email":
        return _email_key(expected) == _email_key(got)
    if metaphone is None:
        raise RuntimeError("jellyfish not installed; needed for phonetic name match")
    e = " ".join(metaphone(w) for w in normalize(expected).split())
    g = " ".join(metaphone(w) for w in normalize(got).split())
    return e == g


def _email_key(s: str) -> str:
    s = normalize(s)
    s = s.replace(" at ", "@").replace(" dot ", ".").replace(" ", "")
    return s


def score(expected: str, got: str, kind: str) -> dict:
    return {
        "exact": exact_match(expected, got),
        "wer": round(wer(expected, got), 4),
        "lev_norm": round(lev_norm(expected, got), 4),
        "phonetic_ok": phonetic_ok(expected, got, kind),
    }


def demo() -> None:
    assert exact_match("Kathleen O'Brien", "kathleen obrien") is True
    assert levenshtein("kathleen", "cathlyn") == 3
    assert abs(lev_norm("kathleen", "kathleen") - 0.0) < 1e-9
    assert abs(wer("the grey cat", "the gray cat") - 1 / 3) < 1e-9
    assert _email_key("jane dot doe at gmail dot com") == "jane.doe@gmail.com"
    assert phonetic_ok("jane.doe@gmail.com", "jane dot doe at gmail dot com", "email") is True
    if metaphone is not None:
        assert phonetic_ok("Kathleen", "Cathleen", "name") is True
        assert phonetic_ok("Kathleen", "Nathaniel", "name") is False
    print("eval metrics demo ok")


if __name__ == "__main__":
    demo()
