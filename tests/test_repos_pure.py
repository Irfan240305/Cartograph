import pytest

from cartograph.repos import map_file, parse_github_url, repo_folder


def test_parse_github_url():
    assert parse_github_url("https://github.com/psf/requests") == "psf/requests"


def test_parse_github_url_strips_git_suffix():
    assert parse_github_url("https://github.com/psf/requests.git") == "psf/requests"


def test_parse_github_url_rejects_other_sites():
    with pytest.raises(ValueError):
        parse_github_url("https://gitlab.com/foo/bar")


def test_repo_folder_replaces_slash():
    assert repo_folder("psf/requests").name == "psf__requests"


def test_map_file_names_correctly():
    assert map_file("psf/requests").name == "psf__requests.json"