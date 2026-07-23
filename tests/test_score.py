import pytest

from aife.canonicalize import _coerce as coerce_firm
from aife.score import Score, aife_index, task_shares
from aife.score import _coerce as coerce_score
from aife.vertex import RateLimiter, parse_json_array


def test_parse_json_array_accepts_plain_and_fenced():
    assert parse_json_array('[{"a": 1}]') == [{"a": 1}]
    assert parse_json_array('```json\n[{"a": 1}]\n```') == [{"a": 1}]
    assert parse_json_array('Here you go:\n[{"a": 1}]') == [{"a": 1}]


def test_parse_json_array_rejects_non_arrays():
    assert parse_json_array('{"a": 1}') is None
    assert parse_json_array("not json") is None


def test_rate_limiter_rejects_non_positive_rate():
    with pytest.raises(ValueError):
        RateLimiter(0)


@pytest.mark.parametrize(
    "record",
    [
        {"id": "a.com", "aife_score": 11.0, "category": "Routine"},
        {"id": "a.com", "aife_score": -1.0, "category": "Routine"},
        {"id": "a.com", "aife_score": 4.0, "category": "Nonsense"},
        {"id": "a.com", "aife_score": "abc", "category": "Routine"},
        {"aife_score": 4.0, "category": "Routine"},
    ],
)
def test_invalid_score_records_are_rejected(record):
    assert coerce_score(record) is None


def test_valid_score_record_is_accepted():
    score = coerce_score(
        {"id": "a.com", "short_summary": "Admin", "aife_score": 3.5, "category": "Routine"}
    )
    assert score == Score("a.com", "Admin", 3.5, "Routine")


def test_aife_index_normalizes_to_unit_interval():
    scores = [Score("a", "", 2.0, "Routine"), Score("a", "", 8.0, "Complex")]
    assert aife_index(scores) == pytest.approx(0.5)
    assert aife_index([]) is None


def test_task_shares_sum_to_one():
    scores = [
        Score("a", "", 1.0, "Routine"),
        Score("b", "", 5.0, "Complex"),
        Score("c", "", 9.0, "Creative"),
        Score("d", "", 2.0, "Routine"),
    ]
    shares = task_shares(scores)
    assert shares["Routine"] == pytest.approx(0.5)
    assert sum(shares.values()) == pytest.approx(1.0)


def test_task_shares_of_empty_input_are_zero():
    assert task_shares([]) == {"Routine": 0.0, "Complex": 0.0, "Creative": 0.0}


def test_unknown_firms_are_dropped():
    record = {
        "canonical_name": "UNKNOWN",
        "firm_age": 0,
        "firm_size": 0,
        "country": "N/A",
        "developed": 0,
    }
    assert coerce_firm(record) is None


def test_firm_record_requires_every_field():
    assert coerce_firm({"canonical_name": "Acme"}) is None
