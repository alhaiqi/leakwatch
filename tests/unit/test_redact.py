import fakes
from leakwatch.scanner.redact import mask, scrub


def test_mask_shape():
    v = fakes.aws_key()
    m = mask(v)
    assert m == v[:4] + "…" + v[-2:]
    assert v not in m


def test_mask_short_values_reveal_less():
    assert mask("abcdefgh") == "ab…"
    assert mask("abc") == "…"
    assert mask("") == "…"


def test_scrub_masks_every_known_and_generic_secret():
    vals = [fakes.aws_key(), fakes.github_pat(), fakes.anthropic_key(), fakes.slack_token()]
    pw = fakes.db_password()
    text = " ".join(vals) + f" url={fakes.postgres_url(pw)} password=\"{fakes.generic_password()}\""
    out = scrub(text)
    for v in vals + [pw]:
        assert v not in out
    assert "…" in out


def test_scrub_masks_unknown_high_entropy_tokens():
    tok = fakes._rand(fakes.ALNUM, 32)
    assert tok not in scrub(f"header X-Weird: {tok}")


def test_scrub_leaves_normal_code_alone():
    s = 'def connect(host="localhost", port=5432):  # retry 3 times'
    assert scrub(s) == s
