from cartograph.tools import split_identifiers


def test_camel_case_is_split():
    assert split_identifiers("CodeAnswer") == "CodeAnswer Code Answer"


def test_plain_words_unchanged():
    assert split_identifiers("hybrid search") == "hybrid search"