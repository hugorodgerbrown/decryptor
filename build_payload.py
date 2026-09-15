"""Compress the vocabulary into the payload the browser build embeds.

Layout (\x1e between sections, \x1d between groups):

  1  words     groups of one length:  "LEN\\nword\\nword..."
  2  freqs     one char per word, parallel to group 1
  3  phrases   groups of one total letter count: "TOTAL\\nphrase\\nphrase..."
  4  synonyms  "word syn syn ..."
  5  abbrevs   "meaning<TAB>short<TAB>short*"  (tab: both sides hold spaces)

The grouping is what makes the browser build usable on a phone. Sorting 238k
words into anagram keys costs 714 ms of a 2.6 s startup, and a query touches
one word length and one phrase total — so grouped, that work happens on demand
in ~65 ms instead of up front on the main thread.
"""
import base64
import gzip
from collections import defaultdict

import vocab
from solver import normalise

idx = vocab.load()
SWAP_MIN_ZIPF = 3.0
ALPHA = "0123456789abcdefghijklmnopqrstuvwxyz"

words = sorted({w for d in idx.words_by_key.values() for b in d.values() for w in b})
phrases = sorted({p[0][0] + "".join(s + w for s, w in zip(p[1], p[0][1:]))
                  for v in idx.phrases_by_key.values() for p in v})

by_length: dict[int, list[str]] = defaultdict(list)
for word in words:
    by_length[len(word)].append(word)

by_total: dict[int, list[str]] = defaultdict(list)
for phrase in phrases:
    by_total[len(normalise(phrase))].append(phrase)

word_groups, freq_groups = [], []
for length in sorted(by_length):
    group = by_length[length]
    word_groups.append(f"{length}\n" + "\n".join(group))
    # Zipf 0..7.5 -> one base36 char at 0.25 resolution. Lossy, imperceptible.
    freq_groups.append("".join(ALPHA[min(30, round(idx.zipf(w) * 4))] for w in group))

phrase_groups = [f"{total}\n" + "\n".join(by_total[total]) for total in sorted(by_total)]

# The whole synonym set per word, not just the same-length slice the
# diagnostics need: 0.32 MB gzipped against 0.05 MB, and it buys the synonyms
# mode, which is the one thing here a solver would otherwise reach for a
# thesaurus to do. word_swaps still filters to same-length candidates itself,
# so a superset costs it nothing.
#
# Targets are restricted to words the dictionary attests. A lemma we would
# never score or rank is one we cannot band honestly, and WordNet supplies a
# good few of them.
attested = set(words)
syn_lines = []
for word in words:
    if idx.zipf(word) < SWAP_MIN_ZIPF:
        continue
    related = sorted(s for s in idx.synonyms(word) if s in attested)
    if related:
        syn_lines.append(word + " " + " ".join(related))

# The setters' substitution vocabulary. Not filtered against the dictionary:
# 'cr' and 'er' are not words and are perfectly good ways to clue 'king'. The
# attestation here is the convention, which is the whole reason it is a tier of
# its own rather than more synonyms.
#
# The two source markers ride along as a suffix, so a band survives the trip
# without a second table. Only the forward direction is shipped — the browser
# inverts it on load, which is cheaper than sending it twice.
MARK = {0: "", 1: "*", 2: "+"}
abbrev_lines = [
    key + "\t" + "\t".join(short + MARK[band] for short, band in shorts)
    for key, shorts in sorted(vocab.load_abbreviations()[0].items())
]

blob = "\x1e".join(["\x1d".join(word_groups), "\x1d".join(freq_groups),
                    "\x1d".join(phrase_groups), "\n".join(syn_lines),
                    "\n".join(abbrev_lines)])
raw = gzip.compress(blob.encode(), 9)
b64 = base64.b64encode(raw).decode()
open("payload.b64", "w").write(b64)

print(f"{len(words):,} words in {len(word_groups)} length groups")
print(f"{len(phrases):,} phrases in {len(phrase_groups)} total groups")
print(f"{len(syn_lines):,} synonym sets")
print(f"{len(abbrev_lines):,} clue words with a setter's shorthand")
print(f"gzip {len(raw)/1e6:.2f} MB -> base64 {len(b64)/1e6:.2f} MB")
