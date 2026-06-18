import pytest
from pathlib import Path
import tempfile
import shutil
import json
from datetime import datetime, timedelta, timezone

from workspace_os.workspace_discovery import (
    discover_workspaces_in_root,
    filter_workspaces_by_type,
    cache_workspace_discovery,
    load_workspace_cache,
    _is_workspace_directory,
    _detect_workspace_type,
)


@pytest.fixture
def temp_workspace_root():
    temp_dir = Path(tempfile.mkdtemp())
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


def test_discover_git_workspace(temp_workspace_root):
    # Create a mock git repo
    git_repo = temp_workspace_root / "test-repo"
    git_repo.mkdir()
    git_dir = git_repo / ".git"
    git_dir.mkdir()
    (git_dir / "HEAD").write_text("ref: refs/heads/main\n")
    (git_dir / "config").write_text('[remote "origin"]\n\turl = https://github.com/test/repo.git\n')

    workspaces = list(discover_workspaces_in_root(temp_workspace_root, max_depth=1))

    assert len(workspaces) == 1
    assert workspaces[0].name == "test-repo"
    assert workspaces[0].workspace_type == "git"
    assert workspaces[0].branch == "main"
    assert "github.com/test/repo.git" in (workspaces[0].remote_url or "")


def test_discover_python_workspace(temp_workspace_root):
    # Create a Python project
    py_project = temp_workspace_root / "python-app"
    py_project.mkdir()
    (py_project / "pyproject.toml").write_text("[project]\nname = 'test'\n")

    workspaces = list(discover_workspaces_in_root(temp_workspace_root, max_depth=1))

    assert len(workspaces) == 1
    assert workspaces[0].name == "python-app"
    assert workspaces[0].workspace_type == "python"


def test_discover_node_workspace(temp_workspace_root):
    # Create a Node.js project
    node_project = temp_workspace_root / "node-app"
    node_project.mkdir()
    (node_project / "package.json").write_text('{"name": "test"}\n')

    workspaces = list(discover_workspaces_in_root(temp_workspace_root, max_depth=1))

    assert len(workspaces) == 1
    assert workspaces[0].name == "node-app"
    assert workspaces[0].workspace_type == "node"


def test_discover_multiple_workspaces(temp_workspace_root):
    # Create multiple workspaces
    (temp_workspace_root / "repo1" / ".git").mkdir(parents=True)
    (temp_workspace_root / "repo1" / ".git" / "HEAD").write_text("ref: refs/heads/main\n")

    (temp_workspace_root / "repo2").mkdir(parents=True)
    (temp_workspace_root / "repo2" / "package.json").write_text('{"name": "test"}\n')

    (temp_workspace_root / "repo3").mkdir(parents=True)
    (temp_workspace_root / "repo3" / "pyproject.toml").write_text("[project]\nname = 'test'\n")

    workspaces = list(discover_workspaces_in_root(temp_workspace_root, max_depth=2))

    assert len(workspaces) == 3
    workspace_names = {ws.name for ws in workspaces}
    assert workspace_names == {"repo1", "repo2", "repo3"}


def test_filter_workspaces_by_type(temp_workspace_root):
    (temp_workspace_root / "git-repo" / ".git").mkdir(parents=True)
    (temp_workspace_root / "git-repo" / ".git" / "HEAD").write_text("ref: refs/heads/main\n")
    (temp_workspace_root / "node-app").mkdir(parents=True)
    (temp_workspace_root / "node-app" / "package.json").write_text('{"name": "test"}\n')

    all_workspaces = discover_workspaces_in_root(temp_workspace_root, max_depth=1)
    git_only = list(filter_workspaces_by_type(all_workspaces, "git"))

    assert len(git_only) == 1
    assert git_only[0].workspace_type == "git"


def test_is_workspace_directory(temp_workspace_root):
    node_dir = temp_workspace_root / "node-app"
    node_dir.mkdir()
    (node_dir / "package.json").write_text('{"name": "test"}\n')

    assert _is_workspace_directory(node_dir) is True
    assert _is_workspace_directory(temp_workspace_root) is False


def test_detect_workspace_type(temp_workspace_root):
    node_dir = temp_workspace_root / "node-app"
    node_dir.mkdir()
    (node_dir / "package.json").write_text('{"name": "test"}\n')

    assert _detect_workspace_type(node_dir) == "node"

    py_dir = temp_workspace_root / "py-app"
    py_dir.mkdir()
    (py_dir / "pyproject.toml").write_text("[project]\n")

    assert _detect_workspace_type(py_dir) == "python"


def test_cache_workspace_discovery(temp_workspace_root):
    # Create test workspaces
    (temp_workspace_root / "repo1" / ".git").mkdir(parents=True)
    (temp_workspace_root / "repo1" / ".git" / "HEAD").write_text("ref: refs/heads/main\n")
    (temp_workspace_root / "repo2").mkdir(parents=True)
    (temp_workspace_root / "repo2" / "package.json").write_text('{"name": "test"}\n')

    cache_path = temp_workspace_root / "cache.json"
    count = cache_workspace_discovery(temp_workspace_root, cache_path, max_depth=2)

    assert count == 2
    assert cache_path.exists()

    # Verify cache structure
    with open(cache_path, "r") as f:
        cache_data = json.load(f)

    assert cache_data["root"] == str(temp_workspace_root)
    assert "scanned_at" in cache_data
    assert len(cache_data["workspaces"]) == 2


def test_load_workspace_cache_fresh(temp_workspace_root):
    # Create and cache workspaces
    (temp_workspace_root / "repo1" / ".git").mkdir(parents=True)
    (temp_workspace_root / "repo1" / ".git" / "HEAD").write_text("ref: refs/heads/main\n")

    cache_path = temp_workspace_root / "cache.json"
    cache_workspace_discovery(temp_workspace_root, cache_path, max_depth=1)

    # Load fresh cache
    workspaces = load_workspace_cache(cache_path, max_age_hours=24)

    assert workspaces is not None
    assert len(workspaces) == 1
    assert workspaces[0].name == "repo1"
    assert workspaces[0].workspace_type == "git"


def test_load_workspace_cache_stale(temp_workspace_root):
    # Create cache with old timestamp
    cache_path = temp_workspace_root / "cache.json"
    old_timestamp = (datetime.now(timezone.utc) - timedelta(hours=48)).isoformat()

    cache_data = {
        "root": str(temp_workspace_root),
        "scanned_at": old_timestamp,
        "workspaces": [],
    }

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    with open(cache_path, "w") as f:
        json.dump(cache_data, f)

    # Load stale cache
    workspaces = load_workspace_cache(cache_path, max_age_hours=24)

    assert workspaces is None


def test_load_workspace_cache_missing(temp_workspace_root):
    cache_path = temp_workspace_root / "nonexistent.json"
    workspaces = load_workspace_cache(cache_path)

    assert workspaces is None
