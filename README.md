# Decryptor

Crossword anagram solver. Give it the fodder and the enumeration, get real answers.

```
$ ./solve.py "on a train, up to its" "10,5"

  RANKED
    ● saturation point   11.2

  1 shown in 0 ms
```

## Putting it on your home screen

`dist/` is an installable web app: manifest, icons, and a service worker that
precaches everything. It is 2.6 MB of static files with no backend.

**Testing it locally.** `devserver.py` serves `dist/` on
<http://localhost:8137>, which is a secure origin, so the service worker
registers exactly as it does in production. `.claude/launch.json` runs it.

```bash
python3 devserver.py
```

Load it once, then stop the server and reload: the app should still solve.
That is the whole claim, and it is the only way to check it — a service worker
never registers over `file://`.

It is a dozen lines longer than `python3 -m http.server` because that one is
quietly wrong here. It sends no `Cache-Control`, so Chromium heuristically
caches `index.html`, and the worker's `addAll()` then fills a **freshly named**
cache with the **previous** build: the page is stale, the cache name says it is
current, and nothing in the browser admits it. That cost an hour of chasing a
feature that was already shipped and looked missing. `render.yaml` sends
`no-cache` for exactly this reason, and now so does the dev server.

**Deploying to Render.** `dist/` is committed and `render.yaml` publishes it with
an empty build command, so the deploy has nothing to break: no Python on the
build image, no pip install, no 30-second vocabulary build. New → Static Site →
point at the repo. If you skip the blueprint, set publish directory to `dist`
and leave the build command blank.

**Workflow.** `dist/` is committed, so it is both the source of truth for the
deploy and the thing you edit toward.

| You changed | Run | Then |
|---|---|---|
| nothing — first deploy | *(nothing)* | commit `dist/`, push |
| `ui.template.html` | `python3 build_dist.py` | commit `dist/`, push |
| `build_payload.py` | `uv run python build_payload.py && python3 build_dist.py` | commit `dist/`, push |
| the dictionary or `vocab.py` | `./build.sh` | commit `dist/`, push |

`build_dist.py` needs only the standard library and works from a fresh clone:
if `payload.b64` is absent it recovers the dictionary from the committed
`dist/index.html`, which already contains it. Only a dictionary change needs
`./build.sh`, which installs wordfreq and nltk and takes about a minute.

Then, on the phone:

- **iOS** — open the URL in Safari, Share → Add to Home Screen.
- **Android** — open in Chrome, menu → Install app.

It opens without browser chrome, follows the system light/dark setting, and
**works with no signal at all** once installed. That last part is not incidental:
a crossword solver is used on trains. `sw.js` precaches every file it serves —
the page, the manifest and all four icons — on first visit, so nothing the page
asks for on load can reach for a network that is not there. A navigation to a
URL that was never cached falls back to the app itself rather than the browser's
offline error, since every URL here is the same single page. The offline reload
is asserted in the browser tests.

`verify_pwa.py` is the check with teeth here. It shuts the origin's server down
rather than asking the browser to pretend, because the first version of it used
offline emulation, the emulation silently failed to apply, and every assertion
passed against a live server — including one for an asset that was never
cached. Its first assertion is now a control: a fetch that must be unreachable.
If the control ever passes, nothing below it means anything.

That is how `icon-180.png` was caught. The page requests it on every load as
its apple-touch-icon, it was the only asset the worker did not precache, and
`precached >= 6` was true the whole time. It needs `uv sync --group verify &&
uv run playwright install chromium`.

The worker is cache-first, which means a stale cache would serve the old app
forever. Its cache name carries a hash of the built page, so a deploy that
changes anything invalidates it automatically — and `render.yaml` sends
`Cache-Control: no-cache` for `sw.js` itself, since a cached worker could never
learn about its own replacement.

iOS ignores manifest icons for Add to Home Screen and needs a real
`apple-touch-icon` file, which is why this ships as a folder and not as the
single HTML.

## Four ways in

A solver arrives at a crossword from one of four directions, so the app has
four modes, chosen by the tabs at the top.

**Anagrind** is the one above: fodder in, real answers out.

**Word finder** is the other one — a half-filled grid entry rather than letters
to rearrange. The input *is* the grid: fifteen squares, and you type from square
one.

```
r_c_n_l_        ->  recently
s_t_r_t_o_,p_i_t ->  saturation point
t_k_-o_t        ->  take-out
```

A blank is a **space, an underscore or a question mark**, whichever your hands
reach for; all three mean one unknown letter. A **comma or hyphen is a word
break**, and that is the whole reason there is no enumeration field in this
mode: `t_k_,o_t` already says (4,3) and `t_k_-o_t` already says 4-3. An
enumeration typed next to a pattern could only ever agree with it or be wrong.

A blank square draws a question mark — one of the characters you can type for
one — so the row reads back as what you entered and cannot be mistaken for a
square you never reached. Not the open box `␣`, which is the right symbol
and missing from several phone monospace fonts; tofu inside a crossword square
reads as a filled-in letter.

Word breaks sit *between* squares rather than taking one, so a fifteen-square
row still holds `10,5`. The entry is as long as you have typed, not fifteen:
squares past the caret are unclaimed, which is what keeps `r_c_n_l_` eight long
and not eight-plus-seven-unknowns. Clicking an answer fills the blanks in the
squares you typed into, without disturbing the pattern or the list.

Under the squares is a real `<input>`, invisible and covering them, so the
phone keyboard, paste and IME all still work and the grid stays a rendering of
its value. Clicking a square moves the caret there.

The highlighted square is what the keyboard acts on, in both directions: a
letter **fills that square** and moves to the next rather than pushing the row
along, and backspace **clears that square** and steps back. Past the last
square there is nothing to overwrite, so typing appends and the row grows —
which is how you enter one in the first place. Word breaks are the exception
and still insert, because a comma sits between two squares rather than in one.

Space is a blank rather than a word break because in this mode you are filling
in squares, and the break between words is what the comma is for.

The match is positional, which is the entire point: `_r_c_n_l` finds `cracknel`
and not `recently`. Bands and ordering are the same as the anagram side —
evidence first, never traded off against score — but there is no unattested
tier, because a pattern with no match has no legal split to fall back on, only
a wrong grid. Results are capped at 200, and the app says so when the cap
bites rather than passing a truncated list off as the whole answer.

**Synonyms** is the third — for the clue where you have neither the fodder nor
enough squares to look the entry up, only the definition half and a shape.

```
quiet   + h__h    ->  hush
want              ->  need, wish, lack, require, desire, ...
sailor  + ______  ->  panama, boater
```

The pattern is the same control the word finder uses, and here it is
**optional**: without one you get the whole synset, ranked. With one you get
the intersection, which is usually a single answer — `quiet` has twenty-four
synonyms and exactly one of them fits `h__h`. Clicking an answer fills the
squares, exactly as in word finder.

It is deliberately not a second anagram field. A thesaurus lookup narrowed by
a grid is the one thing here a solver would otherwise put the app down and
reach for a different book to do.

**Shorthand** is the fourth, and the only one that is not a dictionary lookup
at all. A setter writing `sailor` may simply mean the letters **AB** — that is
a convention of the form, not a synonym, and no thesaurus will ever say so.

```
sailor              ->  ab, jack, os, tar
sailor  + __        ->  ab, os
doctor              ->  bm, dd, dr, gp, mb, md, mo, who
king                ->  cr, er, gr, hm, k, lear, r
```

Same two controls as synonyms, and the same optional pattern. Three things are
deliberately different:

**It is not scored.** Nothing about word frequency bears on whether AB is a
fair way to clue `sailor`, so there is no number beside an answer — only the
band, and alphabetical order inside it. A score here would be invented, which
is the one thing the bands exist to prevent.

**It is not filtered by the dictionary.** `cantuar` is not a word we attest and
is a perfectly good way to clue `archbishop`. The attestation here is the
convention itself, which is exactly why this is a tier of its own instead of
more synonyms — `find_synonyms()` drops what the dictionary cannot vouch for,
and this must not.

**The bands mean something else.** The source marks entries that only turn up
in advanced cryptics, and entries some setters regard as unsound. Those survive
as the three bands rather than being flattened into one list that implies they
are all equally safe — so `note` gives you `do`, `fa`, `la` as standard, and
`a` through `g` under *Considered unsound*.

A word with no shorthand may be shorthand itself, so typing `ab` says what it
stands for rather than nothing at all.

Each mode has **separate inputs** — seven controls, not two wearing four sets
of labels. Fodder, a pattern, a definition and a clue word are different
notations — a space is punctuation in one and a square in another — so
switching tabs cannot bleed one into the next.

## Two ways to run it

**Standalone** — `decryptor.html`, one file, 2.6 MB. Open it on a phone or a
laptop; the dictionary is gzipped and embedded, so it needs no install and no
server. The combinatorial tier is capped at 400 results here.

| | before | now |
|---|---|---|
| startup, main thread | 3,035 ms | **380 ms** |
| heap at ready | 90 MB | **20 MB** |
| unsupported browser | hung on "Loading dictionary…" forever | named error |

Startup used to anagram-key all 238k words up front — 714 ms of it in one
synchronous loop, long enough for iOS to kill the tab. The payload is now
grouped by word length and by phrase total, so a query keys only the length it
touches (6 ms) and indexes only the phrases of its own total (7,156 of 112,672).
Frequencies stay eager because scoring any answer needs them, but they cost
104 ms without the keying.

**Test it in a browser, not in Node.** A `fetch("data:...")` loader once shipped
here and broke the page while every Node check stayed green — Node's `fetch`
loads data: URLs, and so does Chromium over `file://`. Only a page with a
Content-Security-Policy refuses them, which is exactly what a sandboxed viewer
applies. `verify_browser.js` now loads the built file in headless Chromium twice,
bare and under CSP, and the CSP pass fails on that loader and passes on the
current one. The payload is decoded in-page with `atob` and a manual byte loop
(224 ms); nothing in the load path touches the network.

The page makes **no external requests at all** — system fonts, no CDN, nothing
in the load path that touches the network. It follows the OS light/dark setting.
`verify_browser.js` asserts the request count is zero.

One caveat: `DecompressionStream` needs Safari 16.4+, Chrome 80+ or Firefox
113+. Older browsers get a named explanation instead of a spinner.

**Django service** — `uv run python web.py` → http://127.0.0.1:8000. Same UI
template, served with no payload embedded, so the page calls `/api/solve` and
answers come from `solver.py` itself.

```
GET /api/solve?fodder=on+a+train,+up+to+its&enum=10,5&all=

{"answers":[{"text":"saturation point","parts":["saturation","point"],
             "band":0,"band_label":"ranked","tier":"phrase","score":11.195}]}
```

The synonyms mode is served the same way:

```
GET /api/synonyms?word=quiet&pattern=h__h

{"answers":[{"text":"hush","parts":["hush"],"seps":[],"band":0,
             "band_label":"ranked","tier":"word","score":10.41}]}
```

And the shorthand:

```
GET /api/abbreviations?word=sailor&pattern=__

{"answers":[{"text":"ab","parts":["ab"],"seps":[],"band":0,
             "band_label":"standard","tier":"abbrev"}, ...],
 "meanings":[]}
```

`pattern` is optional throughout and, as in `/api/find`, carries its own
enumeration — so there is no shape parameter to disagree with it. Note that
`/api/abbreviations` returns no `score` at all rather than a zero, and that
`meanings` is populated only when there are no answers: it is what the word is
shorthand *for*, which is the useful reply to someone who typed `ab`.

There is one fork per mode between the two builds — `getAnswers()`,
`getMatches()`, `getSynonyms()` and `getAbbreviations()` in the template.
Everything else, including the banding and the tile animation, is shared.
`verify_ui.js` runs the browser solver in Node against the real payload and
checks all 37 Python expectations still hold, so the two cannot drift silently.
That matters most for synonyms, where the browser and Python read the same map
through different filters: the payload drops WordNet lemmas our own dictionary
does not attest, so `find_synonyms()` drops them too and the two agree by
construction rather than by luck.

## Setup

Dependencies are managed with [uv](https://docs.astral.sh/uv/); `uv.lock` pins
the exact set. There is no package to install — the modules sit at the repo
root — so `uv sync` only populates `.venv`.

```bash
uv sync --all-groups      # runtime + build + test + verify deps, from uv.lock
uv run python -c "import nltk; nltk.download('wordnet')"
uv run python vocab.py    # builds .vocab-cache.pkl, ~32s, 9.0 MB
uv run python build_dist.py  # assembles dist/ for hosting
```

Tests and linting go through tox, which builds its environments from the same
lockfile:

```bash
uv run tox                # lint + tests on 3.12, 3.13 and 3.14
uv run tox -e lint        # ruff only
uv run tox -e py314       # tests only, one interpreter
uv run tox -e py314 -- -k pattern   # arguments after -- reach pytest
```

CI runs exactly these two tox commands on every push and pull request — lint
once, tests on all three interpreters — so a green badge means the same
commands you run locally passed. There is no second definition of the suite in
the workflow file to drift out of step.

The rest of the checks are run directly. The `node` ones need no Python
environment; the `uv run` ones use `.venv`.

```bash
node verify_ui.js         # 37 browser/Python parity checks
node verify_load.js       # the real loadDictionary(), end to end
node verify_browser.js    # headless Chromium, bare and under CSP
node verify_deploy.js     # serves dist/: offline install, and redeploy reaching a user
uv run python verify_pwa.py  # the same two claims, against a server that is actually dead
uv run python devserver.py   # serve dist/ locally with production headers

uv run python build_payload.py  # regenerate payload.b64 after changing vocab.py
uv run python -c "open('decryptor.html','w').write(open('ui.template.html').read().replace('__PAYLOAD__', open('payload.b64').read().strip()))"
```

## Design

Three files, one responsibility each.

| File | Responsibility |
|---|---|
| `solver.py` | Search, banding, scoring. Pure, no I/O, no framework. |
| `vocab.py` | Where words, phrases and the setters' shorthand come from. The only file you change to improve answer quality. |
| `solve.py` | CLI. |
| `web.py` | Django service: `/`, `/api/solve`, `/api/find`, `/api/synonyms`, `/api/abbreviations`, `/api/diagnose`. |
| `ui.template.html` | The interface, shared by both builds. |

### The search is not combinatorial

For a multi-word answer we don't generate word splits and filter them — we
index 112k attested phrases by `(anagram_key, length_pattern)` and look the
answer up in O(1). "10,5" over 15 letters resolves in 0.3 ms and returns
exactly one thing. Combinatorial search exists as an opt-in fallback (`--all`)
and is labelled unattested in the output.

Hyphens are carried through: `4-3` renders `take-out`, while a loose `4,3`
still finds it, because solvers type the comma out of habit.

### The enumeration follows the fodder until you disagree with it

Typing fodder fills the enumeration with its letter count — `on` → `2`,
`on a tra` → `6`, `on a train, up to its` → `15`, counting `a-z` only. That is
the shape of a one-word answer, which is a guess, so the moment you type a
shape of your own it is yours: later fodder edits leave it alone and the
mismatch is shown as an error on the field rather than silently corrected. A
clue's enumeration is evidence and our letter count is arithmetic; the same
rule as the answer bands, which never trade a band off against a score.

Emptying the field hands it back, but it does not refill until the fodder
changes next — refilling under a cursor that is mid-edit is how someone
retyping `15` ends up with `155`.

### Three bands, because our sources disagree about what they know

| Band | Meaning | Marker |
|---|---|---|
| `RANKED` | Attested, and we have frequency evidence for every word | ● |
| `ATTESTED, UNRANKED` | In the dictionary, but at least one word has no frequency signal | ◐ |
| `UNATTESTED SPLIT` | A legal split of the letters, nothing more (opt-in) | ○ |

UKACD attests 250k crossword-legal entries but ships no frequency data —
50% of its single words have no Zipf signal at all. wordfreq ranks, but
attests nothing crossword-specific. Collapsing both into one number
fabricates confidence we don't have:

```
'a rope ends it' (11)          before             after
   desperation                  30.65             ● 10.7   RANKED
   esperantido                  20.00             ◐   —    ATTESTED, UNRANKED
```

That earlier 20.00 was pure membership bonus, not evidence. Scoring is now
`2·min(zipf) + mean(zipf)` — rarest word dominates, since a phrase is only as
plausible as its least plausible component — and **bands are never traded off
against score**. Obscurity is what advanced cryptics trade in, so a frequency
floor would delete exactly the entries UKACD exists to supply; the fix is
presentation, not exclusion.

## When there is no answer

**The web UI does not show this.** `DIAGNOSTICS` in `ui.template.html` is
`false`, which hides the section and, just as importantly, keeps it off the
automatic path: `letter_near_misses` costs ~420 ms on its first call and the
section ran on every empty result, so leaving it merely invisible would keep
paying for a thing nobody sees. Nothing is deleted — `diagnose()`,
`renderSuggestions()` and their styles are intact and still covered by
`test_solver.py`. Set the flag to `true`, run `python3 build_dist.py`, and the
section is back; that is the entire procedure. The CLI and `/api/diagnose` are
unaffected and still return suggestions.

An empty result looks the same whether the dictionary lacks the answer or the
solver was handed the wrong letters. In practice the second is far more common,
so `diagnose()` says what would have worked, most likely cause first.

```
$ ./solve.py "want top line" "11"
No attested answer fits those letters.

  DID YOU MEAN
    → want → need   needlepoint

  OTHER WORDS THAT WOULD ALSO FIT
      want → rays   personality
      ...
```

| Diagnostic | Catches | Cost |
|---|---|---|
| `word_swaps` | a misread clue word | 78 ms |
| `alternative_shapes` | a wrong enumeration | 2 ms |
| `letter_near_misses` | a typo | 420 ms first call, then ~20 ms |

**Why word swaps need a synonym signal.** `want` → `need` is three letter
substitutions — a letter distance of 6 out of 11, far past any threshold that
wouldn't return noise. So letter distance cannot find a misread word, and
`test_letter_distance_cannot_find_a_misread_word` pins that down.

Swapping same-length words does find it, but 25 different swaps produce a valid
11-letter answer and `needlepoint` ranks 10th by score. The one thing that
separates it: a solver who writes `want` for `need` has substituted a
**synonym**, and exactly 1 of those 25 is a WordNet synonym of the word typed.
So synonym swaps are marked confident and sorted first — the same rule as the
answer bands, grouping by kind of evidence instead of blending into one number.

Synonyms are precomputed into `.vocab-cache.pkl`. Querying WordNet live cost
8.6 s on first call, which was the entire runtime of the diagnostics; building
the map at cache time also keeps nltk off the runtime path.

### The synonym map pays for itself twice

The same map answers the diagnostics above and the synonyms mode, which is why
the mode was worth building: the data was already there, already offline, and
already the thing that separates a useful suggestion from a coincidence.

The two callers want different slices of it, so the map stores the whole synset
and each filters at query time — `word_swaps()` to same-length candidates,
`find_synonyms()` to whatever the grid pattern says. The browser payload used
to ship only the diagnostics' slice, at 0.05 MB gzipped. Shipping all of it
costs 0.32 MB, which is the app going from 2.2 MB to 2.6 MB, and it is the
whole feature — a thesaurus that stops working on a train is not one.

`SYNONYM_MIN_ZIPF` is a floor on the word you *look up*, not on what comes
back: 20,152 words have a synset, and they are the common ones, which is what
a clue's definition half is made of. `bluejacket` is reachable from `sailor`
and not the other way round.

## Sources

| Source | Contributes | Cannot tell us |
|---|---|---|
| [UKACD](data/LICENSE-UKACD.txt) 250k | 53k crossword-legal phrases, hyphenation, proper nouns | frequency |
| WordNet 64k lemmas | 64k phrases — overlaps UKACD by only 13k; the synonyms behind both the diagnostics and the synonyms mode | crossword conventions |
| wordfreq | Zipf frequencies | attestation |
| [Setters' shorthand](data/abbreviations.txt) 3,077 pairs | what a clue word is conventionally written as — `sailor` → AB | anything about ordinary meaning |

Union: **112,672 phrases, 237,658 words** (123k rankable), plus **2,061 clue
words** with a setter's shorthand.

The shorthand list is deliberately **not in `.vocab-cache.pkl`**. It is 42 KB
of plain text that parses in a millisecond, so pickling it would buy nothing
and would mean a 30-second vocabulary rebuild every time someone corrects a
single line. `vocab.load_abbreviations()` reads it on every load.

### ⚠️ The shorthand list has no licence yet

`data/abbreviations.txt` is **not cleared for release.** It was compiled by
Ross Beresford and posted to rec.puzzles.crosswords in 1992, and reaches us via
[mhl/cryptic-crossword-indicators-and-abbreviations](https://github.com/mhl/cryptic-crossword-indicators-and-abbreviations),
which publishes no licence at all.

That Beresford also wrote UKACD does **not** help: UKACD carries an explicit
BSD-3-Clause grant and this list carries nothing, and a Usenet post is not a
licence. Permission is being sought. Until it is granted in writing, treat this
file — and the built `dist/` that embeds it — as development only. The file
header says the same thing, so nobody has to read this far to find out.

UKACD is redistributed here under BSD-3-Clause, Copyright (c) 2009
J Ross Beresford. The notice is reproduced verbatim in
`data/LICENSE-UKACD.txt` and at the head of `data/UKACD.txt`, as its terms
require.

## Known limits

1. **Recall is still the open number.** `they see` (4,3) is a legitimate
   published answer and no gazetteer attests it. Measure recall against a
   corpus of real published answers before building UI.
2. **Capitalisation is lost.** UKACD marks proper nouns with a capital; we
   normalise it away, so `celtic cross` renders lowercase.
3. **Combo tier emits slot permutations** — `point on of return` and
   `point of on return` are separate rows. Noisy, opt-in only.
4. **4-word `--all` takes ~450 ms.** Queue it rather than serving inline.
5. **`web.py` is a dev server.** `DEBUG=True`, no CORS, no rate limiting, and
   `runserver` is single-process. Fine for testing, not for anything else.
6. **WordNet is not a crossword thesaurus.** It is a lexical database, so it
   gives `sailor` → `bluejacket` and not `ab`. That is what the shorthand mode
   is for, and the two stay in separate tabs precisely because they are
   different kinds of claim. Measure both against published clues before
   trusting them the way you trust the anagram side.
7. **Synonyms are single words only.** `_synonym_map()` drops WordNet lemmas
   containing `_`, so `abandon` → `give up` is missing even though the pattern
   matcher handles multi-word entries natively. Lifting it is a `vocab.py`
   change and a cache rebuild, not a solver change.
8. **The shorthand list is unlicensed** and is the one thing here that blocks a
   release. See the warning under Sources.
9. **The shorthand covers 2,061 clue words**, against 20,152 with synonyms. It
   is a 1992 list: it knows `lner` for `old railway` and will not know anything
   coined since.

## Django integration

`solver.py` has no framework dependencies and `Index` is immutable, so load it
once per process and share it:

```python
# apps/solver/apps.py
class SolverConfig(AppConfig):
    def ready(self):
        from . import vocab
        self.index = vocab.load()   # ~9.0 MB resident, thread-safe to read
```

Then a thin DRF view over `solve()`. At sub-millisecond per query for the
attested bands you can serve this synchronously; only `include_unattested`
needs a queue.
