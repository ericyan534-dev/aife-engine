import gzip

from aife.extract import build_posting, extract
from aife.nquads import group_by_subject

RECORD = """<http://acme.com/j1> <http://schema.org/title> "Data Analyst" .
<http://acme.com/j1> <http://schema.org/description> "Build dashboards." .
<http://acme.com/j1> <http://schema.org/hiringOrganization> _:org .
<http://acme.com/j1> <http://schema.org/jobLocation> _:place .
_:org <http://schema.org/name> "Acme Corporation" .
_:place <http://schema.org/address> _:addr .
_:addr <http://schema.org/addressLocality> "Berlin" .
_:addr <http://schema.org/addressCountry> "DE" .
"""


def _single_posting(text):
    subject, quads = next(group_by_subject(iter(text.splitlines())))
    return build_posting(subject, quads)


def test_resolves_firm_name_and_chained_location():
    posting = _single_posting(RECORD)
    assert posting.domain == "acme.com"
    assert posting.title == "Data Analyst"
    assert posting.firm_name == "Acme Corporation"
    assert posting.location is not None
    assert "Berlin" in posting.location and "DE" in posting.location


def test_location_resolves_when_address_props_sit_on_the_place_node():
    text = (
        '<http://acme.com/j1> <http://schema.org/jobLocation> _:place .\n'
        '_:place <http://schema.org/addressLocality> "Oslo" .\n'
    )
    assert _single_posting(text).location == "Oslo"


def test_missing_optional_fields_do_not_raise():
    posting = _single_posting('<http://acme.com/j1> <http://schema.org/title> "Cook" .\n')
    assert posting.description == ""
    assert posting.firm_name is None
    assert posting.location is None


def test_extract_keeps_longest_description_per_domain(tmp_path):
    corpus = tmp_path / "part.gz"
    text = (
        '<http://acme.com/short> <http://schema.org/description> "short" .\n'
        '<http://acme.com/long> <http://schema.org/description> "much longer text" .\n'
        '<http://other.com/x> <http://schema.org/description> "ignored" .\n'
    )
    corpus.write_bytes(gzip.compress(text.encode()))

    result = extract([corpus], {"acme.com"})
    assert set(result) == {"acme.com"}
    assert result["acme.com"].description == "much longer text"
