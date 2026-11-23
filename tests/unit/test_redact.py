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
    for _ in range(500):  # deterministic enough: covers letters-only draws (~0.4% of ALNUM draws)
        tok = fakes._rand(fakes.ALNUM, 32)
        assert tok not in scrub(f"header X-Weird: {tok}")
    letters = fakes._rand(fakes.string.ascii_letters, 32)
    assert letters not in scrub(f"x: {letters}")
    dashed = fakes._rand(fakes.ALNUM, 12) + "-" + fakes._rand(fakes.ALNUM, 14)
    assert dashed not in scrub(f"x: {dashed}")


def test_scrub_keeps_wordy_identifiers():
    for s in ["retries = MAX_CONNECTION_RETRIES_BEFORE_FAILURE",
              'AUTH_BACKEND = "django.contrib.auth.backends.ModelBackend"']:
        assert scrub(s) == s


def test_scrub_leaves_normal_code_alone():
    s = 'def connect(host="localhost", port=5432):  # retry 3 times'
    assert scrub(s) == s


def test_scrub_keeps_delivery_guids_and_refs_but_not_secrets_inside_refs():
    s = "queued from refs/heads/leakwatch-e2e-aws-1795463535 (delivery 630d1e2a-c8b1-11f0-9a3f-1e2b3c4d5e6f)"
    assert scrub(s) == s
    k = fakes.aws_key()
    assert k not in scrub(f"refs/heads/{k}")
