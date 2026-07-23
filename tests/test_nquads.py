from aife.nquads import group_by_subject, normalize_domain, parse_line


def test_parses_uri_object():
    quad = parse_line('<http://a.com/j1> <http://schema.org/hiringOrganization> _:b0 .')
    assert quad is not None
    assert quad.subject == "<http://a.com/j1>"
    assert quad.obj == "_:b0"


def test_parses_literal_and_unescapes():
    quad = parse_line('<http://a.com/j1> <http://schema.org/description> "line\\none" .')
    assert quad is not None
    assert quad.obj == "line\none"


def test_literal_containing_quotes_keeps_inner_content():
    quad = parse_line('<http://a.com/j1> <http://schema.org/title> "the \\"best\\" job" .')
    assert quad is not None
    assert quad.obj == 'the "best" job'


def test_rejects_malformed_line():
    assert parse_line("garbage") is None


def test_normalize_domain_strips_scheme_www_and_path():
    assert normalize_domain("https://www.Example.com/jobs/1") == "example.com"
    assert normalize_domain("example.com") == "example.com"
    assert normalize_domain(None) is None
    assert normalize_domain("") is None


def test_group_by_subject_attaches_blank_nodes_to_preceding_uri():
    lines = [
        '<http://a.com/1> <http://schema.org/title> "A" .',
        '_:b0 <http://schema.org/name> "Firm A" .',
        '<http://b.com/1> <http://schema.org/title> "B" .',
        '_:b1 <http://schema.org/name> "Firm B" .',
    ]
    groups = list(group_by_subject(iter(lines)))
    assert [subject for subject, _ in groups] == ["<http://a.com/1>", "<http://b.com/1>"]
    assert all(len(quads) == 2 for _, quads in groups)
