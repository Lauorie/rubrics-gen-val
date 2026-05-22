from rubrics.source_parser import parse_source, DOC_ALIASES


def test_parse_benson_with_page_range():
    parts = parse_source("Benson教材, 第4章, 第166-189页")
    assert len(parts) == 1
    assert parts[0].doc_alias == "Benson"
    assert parts[0].pages == (166, 189)


def test_parse_phd_with_single_page():
    parts = parse_source("贾宪振博士论文 第17页")
    assert parts[0].doc_alias == "贾宪振博士论文"
    assert parts[0].pages == (17, 17)


def test_parse_thyssenkrupp_short_form():
    parts = parse_source("ThyssenKrupp论文 第5页")
    assert parts[0].doc_alias == "ThyssenKrupp"


def test_parse_semicolon_multidoc():
    parts = parse_source("贾宪振博士论文 第17页; ThyssenKrupp论文 第5页")
    assert len(parts) == 2
    assert parts[0].doc_alias == "贾宪振博士论文"
    assert parts[1].doc_alias == "ThyssenKrupp"


def test_parse_no_page_info():
    parts = parse_source("Benson教材")
    assert len(parts) == 1
    assert parts[0].pages is None


def test_parse_comma_multidoc():
    parts = parse_source("贾宪振博士论文 第17页，重力坝论文 第502页")
    assert len(parts) == 2


def test_doc_aliases_map_to_actual_filenames():
    """Each alias must correspond to a real file in CAE-MDs/."""
    from pathlib import Path
    mds = list(Path("/home/juli/RLM/CAE-MDs").glob("*.md"))
    if not mds:
        return
    names = {m.name for m in mds}
    for alias, filename in DOC_ALIASES.items():
        assert filename in names, f"alias '{alias}' → '{filename}' not in CAE-MDs/"
