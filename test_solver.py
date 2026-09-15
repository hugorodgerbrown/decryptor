"""pytest test_solver.py"""

import pytest

import vocab
from solver import (
    BAND_RANKED,
    BAND_UNATTESTED,
    BAND_UNRANKED,
    TIER_PHRASE,
    anagram_key,
    normalise,
    parse_enumeration,
    solve,
    split_entry,
)


@pytest.fixture(scope="session")
def index():
    return vocab.load()


# -- normalisation ----------------------------------------------------------

def test_normalise_strips_punctuation_and_case():
    assert normalise("On a train, up to its!") == "onatrainuptoits"


def test_normalise_folds_accents():
    assert normalise("café-crème") == "cafecreme"


def test_anagram_key_matches_across_spacing():
    assert anagram_key("on a train, up to its") == anagram_key("saturation point")


def test_split_entry_records_separators():
    assert split_entry("point of no return") == (
        ("point", "of", "no", "return"), (" ", " ", " "))
    assert split_entry("take-out") == (("take", "out"), ("-",))


# -- enumeration ------------------------------------------------------------

@pytest.mark.parametrize("text", ["10,5", "10 5", "(10,5)", " 10 , 5 "])
def test_parse_equivalent_forms(text):
    assert parse_enumeration(text).lengths == (10, 5)


def test_parse_preserves_hyphen():
    enum = parse_enumeration("4-3,2")
    assert enum.lengths == (4, 3, 2)
    assert enum.render(["hard", "top", "of"]) == "hard-top of"


def test_parse_rejects_garbage():
    with pytest.raises(ValueError):
        parse_enumeration("banana")


# -- solving ----------------------------------------------------------------

@pytest.mark.parametrize("fodder,enum,expected", [
    ("on a train, up to its", "10,5", "saturation point"),
    ("no more stars", "11", "astronomers"),
    ("dirty room", "9", "dormitory"),
    ("a rope ends it", "11", "desperation"),
    ("voices rant on", "12", "conversation"),
])
def test_known_answers_rank_first(fodder, enum, expected, index):
    answers = solve(fodder, enum, index)
    assert answers, f"no answer for {fodder!r}"
    assert answers[0].text == expected
    assert answers[0].band == BAND_RANKED


def test_letter_count_mismatch_is_rejected(index):
    with pytest.raises(ValueError, match="15 letters"):
        solve("on a train, up to its", "10,4", index)


# -- bands ------------------------------------------------------------------

def test_unrankable_entry_is_banded_not_scored(index):
    """UKACD attests 'esperantido' but gives us nothing to rank it with. It must
    appear below 'desperation' on evidence, never above it on a phantom score."""
    answers = solve("a rope ends it", "11", index)
    texts = [a.text for a in answers]
    assert texts[0] == "desperation"
    assert "esperantido" in texts
    unranked = next(a for a in answers if a.text == "esperantido")
    assert unranked.band == BAND_UNRANKED
    assert unranked.score < answers[0].score


def test_bands_are_never_traded_off_against_score(index):
    answers = solve("point of no return", "5,2,2,6", index, include_unattested=True)
    bands = [a.band for a in answers]
    assert bands == sorted(bands), "a lower band outranked a higher one"


def test_attested_phrase_outranks_unattested_split(index):
    answers = solve("on a train, up to its", "10,5", index, include_unattested=True)
    assert answers[0].text == "saturation point"
    assert answers[0].band == BAND_RANKED
    assert answers[0].tier == TIER_PHRASE
    assert any(a.band == BAND_UNATTESTED for a in answers[1:])


def test_unattested_phrase_hidden_by_default(index):
    assert solve("the eyes", "4,3", index) == []
    fallback = solve("the eyes", "4,3", index, include_unattested=True)
    assert fallback[0].text == "they see"
    assert fallback[0].band == BAND_UNATTESTED


# -- separators -------------------------------------------------------------

def test_hyphen_enumeration_renders_hyphen(index):
    assert solve("out take", "4-3", index)[0].text == "take-out"


def test_loose_enumeration_still_finds_hyphenated_entry(index):
    assert solve("out take", "4,3", index)[0].words == ("take", "out")


# -- hygiene ----------------------------------------------------------------

def test_results_are_deduplicated(index):
    answers = solve("point of no return", "5,2,2,6", index, include_unattested=True)
    assert len({a.words for a in answers}) == len(answers)


def test_limit_is_respected(index):
    assert len(solve("the eyes", "4,3", index, limit=3, include_unattested=True)) == 3


# -- word finder ------------------------------------------------------------
from solver import find_pattern, parse_pattern  # noqa: E402


def test_blank_is_space_underscore_or_question_mark():
    """A solver filling squares reaches for whichever key is nearest. All three
    mean the same thing, and none of them is a word break."""
    assert parse_pattern("r_c_n_l_") == parse_pattern("r c n l ")
    assert parse_pattern("r_c_n_l_") == parse_pattern("r?c?n?l?")


def test_pattern_derives_its_own_enumeration():
    """The separators carry the shape, so there is nothing to type twice."""
    assert str(parse_pattern("t_k_,o_t").enumeration) == "4,3"
    assert str(parse_pattern("t_k_-o_t").enumeration) == "4-3"
    assert str(parse_pattern("r_c_n_l_").enumeration) == "8"


def test_trailing_blank_counts():
    """'r_c_n_l_' is eight squares, not seven. The last one is the point."""
    assert parse_pattern("r_c_n_l_").total == 8
    assert parse_pattern("r c n l ").total == 8


def test_pattern_finds_the_word(index):
    answers = find_pattern("r_c_n_l_", index)
    assert "recently" in [a.text for a in answers]


def test_pattern_finds_a_phrase_by_its_derived_shape(index):
    answers = find_pattern("s_t_r_t_o_,p_i_t", index)
    assert answers[0].text == "saturation point"
    assert answers[0].tier == TIER_PHRASE


def test_pattern_honours_the_hyphen(index):
    """'take out' and 'take-out' are both attested and dedupe to one answer, so
    a pattern that states the hyphen has to get the hyphenated one — and a
    pattern that states a comma still finds it, the same trade solve() makes."""
    assert [a.text for a in find_pattern("t_k_-o_t", index)] == ["take-out"]
    assert [a.text for a in find_pattern("t_k_,o_t", index)] == ["take out"]


def test_pattern_rejects_a_letter_in_the_wrong_square(index):
    """The whole value of a pattern is positional. A word that merely has the
    right letters must not come back."""
    assert "recently" not in [a.text for a in find_pattern("_r_c_n_l", index)]


def test_pattern_respects_length(index):
    assert all(len(a.text.replace(" ", "").replace("-", "")) == 8
               for a in find_pattern("r_______", index, limit=50))


def test_pattern_bands_match_the_solver(index):
    """Same evidence rule as solve(): ranked before unranked, never blended."""
    answers = find_pattern("________", index, limit=50)
    assert answers == sorted(answers, key=lambda a: (a.band, -a.score, a.text))
    assert answers[0].band == BAND_RANKED


def test_open_pattern_is_flagged_not_special_cased():
    """All blanks is a legal pattern that matches the entire dictionary. The
    caller decides whether to run it; the parser just says so."""
    assert parse_pattern("____").is_open
    assert not parse_pattern("r___").is_open


def test_empty_pattern_finds_nothing(index):
    assert find_pattern("", index) == []


def test_pattern_limit_is_respected(index):
    assert len(find_pattern("________", index, limit=5)) == 5


# -- synonyms ---------------------------------------------------------------
from solver import find_synonyms  # noqa: E402


def test_synonyms_of_a_clue_word(index):
    """The plain lookup: the definition half of the clue, nothing else known."""
    texts = [a.text for a in find_synonyms("want", index)]
    assert "need" in texts
    assert "wish" in texts


def test_synonym_bands_match_the_solver(index):
    answers = find_synonyms("quiet", index)
    assert answers == sorted(answers, key=lambda a: (a.band, -a.score, a.text))
    assert answers[0].band == BAND_RANKED


def test_synonyms_are_all_attested(index):
    """WordNet offers lemmas our own dictionary has never heard of. We cannot
    band those honestly, and the browser payload drops them, so neither may we."""
    for word in ("quiet", "want", "sailor", "flower", "run"):
        for answer in find_synonyms(word, index):
            assert all(index.attests(w) for w in answer.words), answer.text


def test_a_word_is_not_its_own_synonym(index):
    assert "quiet" not in [a.text for a in find_synonyms("quiet", index)]


def test_synonyms_ignore_case_and_punctuation(index):
    assert find_synonyms("Quiet!", index) == find_synonyms("quiet", index)


def test_no_word_finds_no_synonyms(index):
    assert find_synonyms("", index) == []
    assert find_synonyms("   ", index) == []


def test_unknown_word_finds_nothing_rather_than_raising(index):
    """Below the frequency floor there is simply no synset. An empty list is
    the honest answer; the UI says so in words."""
    assert find_synonyms("zzzzqx", index) == []


def test_synonym_limit_is_respected(index):
    assert len(find_synonyms("run", index, limit=3)) == 3


# -- abbreviations ----------------------------------------------------------
from solver import (ABBREV_LABEL, TIER_ABBREV, find_abbreviations,  # noqa: E402
                    lookup_key, what_it_stands_for)


def test_lookup_key_folds_a_phrase_not_a_word():
    """normalise() would run 'able seaman' into one word. These meanings are
    often two, so words have to survive as words."""
    assert lookup_key("Able Seaman") == "able seaman"
    assert lookup_key("Anglo-Saxon") == lookup_key("anglo saxon") == "anglo saxon"


def test_the_gap_wordnet_could_not_fill(index):
    """The reason this mode exists. A thesaurus gives sailor -> bluejacket; a
    setter writes AB, and no synset says so."""
    assert [a.text for a in find_abbreviations("sailor", index)] == [
        "ab", "jack", "os", "tar"]


def test_shorthand_is_not_filtered_by_the_dictionary(index):
    """'cantuar' is not in our dictionary and is a perfectly good way to clue
    'archbishop'. The attestation here is the convention, not the wordlist,
    which is exactly why this is its own tier and not more synonyms —
    find_synonyms() drops what the dictionary cannot vouch for, and this
    must not."""
    assert not index.attests("cantuar")
    assert "cantuar" in [a.text
                         for a in find_abbreviations("archbishop", index)]


def test_source_markers_survive_as_bands(index):
    """The list marks what only advanced cryptics use and what some setters
    call unsound. Flattening those into one list would imply they are all
    equally safe."""
    notes = find_abbreviations("note", index)
    by_band = {a.text: a.band for a in notes}
    assert by_band["do"] == BAND_RANKED
    assert by_band["a"] == BAND_UNATTESTED      # '+' in the source
    assert ABBREV_LABEL[BAND_UNATTESTED] == "considered unsound by some"


def test_bands_are_never_traded_off_here_either(index):
    answers = find_abbreviations("note", index)
    assert [a.band for a in answers] == sorted(a.band for a in answers)
    assert answers == sorted(answers, key=lambda a: (a.band, a.text))


def test_shorthand_is_not_scored(index):
    """There is no frequency evidence that bears on whether AB is a fair way to
    clue 'sailor'. A number here would be invented."""
    for answer in find_abbreviations("sailor", index):
        assert answer.score == 0.0
        assert answer.tier == TIER_ABBREV


def test_multi_word_shorthand_is_carried_through(index):
    """A few entries are not abbreviations at all — 'uncle' is 'pawnbroker',
    'spy' is 'old man'. The pattern matcher handles them like any phrase."""
    assert "pawnbroker" in [a.text for a in find_abbreviations("uncle", index)]


def test_lookup_ignores_case_and_punctuation(index):
    assert (find_abbreviations("Sailor!", index)
            == find_abbreviations("sailor", index))


def test_a_short_form_says_what_it_stands_for(index):
    """Typing 'ab' is typing a short form, not a clue word. An empty list would
    be a lie about a word the table knows perfectly well."""
    assert find_abbreviations("ab", index) == []
    assert "sailor" in what_it_stands_for("ab", index)


def test_unknown_word_has_no_shorthand(index):
    assert find_abbreviations("zzzzqx", index) == []
    assert what_it_stands_for("zzzzqx", index) == []


def test_no_word_finds_no_shorthand(index):
    assert find_abbreviations("", index) == []
    assert find_abbreviations("  ", index) == []


def test_shorthand_limit_is_respected(index):
    assert len(find_abbreviations("note", index, limit=3)) == 3


def test_the_list_loads_without_a_cache_rebuild():
    """It is 42 KB of plain text, deliberately outside the pickle: correcting
    one line must not cost a 30-second vocabulary rebuild."""
    forward, reverse = vocab.load_abbreviations()
    assert len(forward) > 2000
    assert ("ab", BAND_RANKED) in forward["sailor"]
    assert "sailor" in reverse["ab"]


# -- diagnostics ------------------------------------------------------------
from solver import alternative_shapes, diagnose, letter_near_misses, word_swaps  # noqa: E402


def test_misread_clue_word_is_found_and_marked_confident(index):
    """The real failure: 'want top line' for 'need top line'. Three letter
    substitutions, so no letter-distance check can see it."""
    suggestions = word_swaps("want top line", "11", index)
    assert suggestions, "no swap found"
    top = suggestions[0]
    assert top.answers[0].text == "needlepoint"
    assert top.detail == "want \u2192 need"
    assert top.confident, "a synonym swap must outrank coincidental fits"
    assert top.fodder is not None


def test_only_synonym_swaps_are_confident(index):
    """Precision check: of everything that merely fits, only the synonym is
    marked confident. If this starts failing the signal has gone noisy."""
    suggestions = word_swaps("want top line", "11", index, limit=25)
    confident = [s for s in suggestions if s.confident]
    assert len(confident) == 1
    assert confident[0].answers[0].text == "needlepoint"


def test_letter_distance_cannot_find_a_misread_word(index):
    """Documents the limit that makes word_swaps necessary."""
    misses = letter_near_misses("want top line", "11", index, max_distance=2)
    assert all(s.answers[0].text != "needlepoint" for s in misses)


def test_near_misses_find_a_typo(index):
    """One letter dropped from real fodder is exactly what this is for."""
    misses = letter_near_misses("no more star", "11", index, max_distance=2)
    assert any(s.answers[0].text == "astronomers" for s in misses)


def test_alternative_shapes_finds_the_right_enumeration(index):
    shapes = alternative_shapes("on a train, up to its", index)
    assert any(s.enumeration == "10,5" for s in shapes)


def test_no_diagnostics_offered_for_letters_that_go_nowhere(index):
    assert alternative_shapes("want top line", index) == []


def test_diagnose_leads_with_the_likeliest_cause(index):
    suggestions = diagnose("want top line", "11", index)
    assert suggestions[0].confident
    assert suggestions[0].answers[0].text == "needlepoint"


def test_suggested_fodder_actually_solves(index):
    """Every suggestion must be actionable — applying it has to work."""
    for s in diagnose("want top line", "11", index):
        if s.fodder:
            assert solve(s.fodder, "11", index)[0].text == s.answers[0].text
