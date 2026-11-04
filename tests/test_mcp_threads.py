from cartograph.mcp_server import thread_for


def test_same_repo_keeps_same_thread():
    assert thread_for("psf/requests") == thread_for("psf/requests")


def test_different_repos_get_different_threads():
    assert thread_for("psf/requests") != thread_for("Irfan240305/Cartograph")