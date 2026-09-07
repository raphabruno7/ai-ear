"""Build the AWS Transcribe custom vocabulary from the golden set.

Seeds Transcribe with the hard owner/pet names it otherwise mis-hears. In
production you'd load the clinic's real patient roster the same way — here the
source is dataset/samples.jsonl.

    python build_vocab.py            # create/refresh, wait until READY
    python build_vocab.py --delete   # tear it down

Vocabulary name = $TRANSCRIBE_VOCAB (default "call-copilot-en-US").
Phrases-list format only (no S3 table): it fixes what Transcribe *hears*, not
how it capitalises — the LLM still does the orthography.
"""

from __future__ import annotations

import argparse
import json
import os
import time
import unicodedata
from pathlib import Path

import boto3
from dotenv import load_dotenv

HERE = Path(__file__).parent
load_dotenv(HERE.parent / ".env")

NAME = os.environ.get("TRANSCRIBE_VOCAB", "call-copilot-en-US")
REGION = os.environ.get("AWS_REGION", "us-east-1")
SAMPLES = HERE / "dataset" / "samples.jsonl"

# Domain tokens dictated in the email samples — free signal, not name-seeded, so
# they double as a control cohort in the eval report.
EMAIL_TOKENS = ["protonmail", "icloud", "outlook", "stanford", "yahoo", "company", "nhs"]


# latin letters NFKD doesn't decompose (ł, ø, ß, …) — the en-US Phrases charset
# rejects them outright.
_TRANSLIT = str.maketrans({"ł": "l", "Ł": "L", "ø": "o", "Ø": "O", "đ": "d", "Đ": "D",
                           "ß": "ss", "æ": "ae", "Æ": "Ae", "œ": "oe", "Œ": "Oe"})


def _ascii(s: str) -> str:
    """Fold to the unaccented en-US Phrases charset."""
    s = unicodedata.normalize("NFKD", s.translate(_TRANSLIT))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return s.encode("ascii", "ignore").decode()


def _phrases() -> list[str]:
    rows = [json.loads(l) for l in SAMPLES.read_text().splitlines() if l.strip()]
    out: set[str] = set()
    for r in rows:
        if r["kind"] != "name":
            continue
        name = _ascii(r["expected"])
        toks = [t.strip(".'") for t in name.replace("-", " ").split()]
        toks = [t for t in toks if t and all(c.isalpha() or c in "'" for c in t)]
        out.update(toks)                       # each word
        if len(toks) > 1:
            out.add("-".join(toks))            # the full name as one phrase
    out.update(EMAIL_TOKENS)
    return sorted(out)


def _wait_ready(client) -> str:
    while True:
        v = client.get_vocabulary(VocabularyName=NAME)
        state = v["VocabularyState"]
        if state != "PENDING":
            return state
        time.sleep(5)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--delete", action="store_true")
    ap.add_argument("--check", action="store_true", help="offline self-check, no AWS call")
    args = ap.parse_args()

    if args.check:
        assert _ascii("Michał Wojciechowski") == "Michal Wojciechowski"
        assert _ascii("Aoife Ní Bhraonáin") == "Aoife Ni Bhraonain"
        assert _ascii("Björn Andersson") == "Bjorn Andersson"
        ps = _phrases()
        assert "Kathleen" in ps and "O'Brien" in ps, ps
        assert "Kathleen-O'Brien" in ps                     # full name as one phrase
        assert "protonmail" in ps                           # email control token
        assert all(p.isascii() and " " not in p for p in ps), [p for p in ps if not p.isascii() or " " in p]
        print(f"ok — {len(ps)} phrases")
        return

    client = boto3.client("transcribe", region_name=REGION)

    if args.delete:
        client.delete_vocabulary(VocabularyName=NAME)
        print(f"deleted {NAME}")
        return

    phrases = _phrases()
    exists = any(v["VocabularyName"] == NAME
                 for v in client.list_vocabularies(NameContains=NAME).get("Vocabularies", []))
    op = client.update_vocabulary if exists else client.create_vocabulary
    op(VocabularyName=NAME, LanguageCode="en-US", Phrases=phrases)
    print(f"{'update' if exists else 'create'} {NAME}: {len(phrases)} phrases")

    state = _wait_ready(client)
    print(f"state: {state}")
    if state != "READY":
        raise SystemExit(f"vocabulary {NAME} is {state}, not READY")


if __name__ == "__main__":
    main()
