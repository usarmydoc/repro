"""Regression tests: --env snapshots only capture the named environment."""

import os
import site
import sys
import sysconfig

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from repro import snapshot
from repro.detectors import _util, conda, packages


def _plant_user_site_package(userbase):
    """Create a fake distribution in a user site-packages under userbase."""
    scheme = "{}_user".format(os.name)
    purelib = sysconfig.get_path("purelib", scheme, vars={"userbase": str(userbase)})
    dist = os.path.join(purelib, "reprofakeleak-9.9.9.dist-info")
    os.makedirs(dist)
    with open(os.path.join(dist, "METADATA"), "w") as f:
        f.write("Metadata-Version: 2.1\nName: reprofakeleak\nVersion: 9.9.9\n")


def test_run_cmd_passes_extra_env():
    out, rc = _util.run_cmd(
        [sys.executable, "-c", "import os; print(os.environ['REPRO_TEST_VAR'])"],
        env={"REPRO_TEST_VAR": "hello"},
    )
    assert rc == 0 and out == "hello"


@pytest.mark.skipif(not site.ENABLE_USER_SITE, reason="user site disabled for this interpreter")
def test_detect_pip_for_env_excludes_user_site(tmp_path, monkeypatch):
    """A package in ~/.local must not appear as part of the environment."""
    _plant_user_site_package(tmp_path)
    monkeypatch.setenv("PYTHONUSERBASE", str(tmp_path))
    monkeypatch.delenv("PYTHONNOUSERSITE", raising=False)

    # Sanity check: without exclusion pip does see the planted package
    out, _ = _util.run_cmd([sys.executable, "-m", "pip", "list"], timeout=60)
    assert "reprofakeleak" in out

    pkgs = packages.detect_pip(python=sys.executable)
    assert pkgs, "pip listing for the interpreter came back empty"
    assert "reprofakeleak" not in pkgs


def test_conda_listing_disables_user_site(monkeypatch):
    """mamba lists pip packages via the env's pip, so user site must be off."""
    calls = []

    def fake_run_cmd(cmd, timeout=10, combine_stderr=True, env=None):
        calls.append(env)
        return "[]", 0

    monkeypatch.setattr(conda, "run_cmd", fake_run_cmd)
    conda._list_packages("mamba", "someenv")
    assert calls == [{"PYTHONNOUSERSITE": "1"}]


def test_env_without_python_records_pip_unknown(tmp_path, monkeypatch):
    """An env with no interpreter must not fall back to the pip on PATH."""
    prefix = tmp_path / "envs" / "nopy"
    (prefix / "bin").mkdir(parents=True)
    monkeypatch.setattr(conda, "env_prefix", lambda name: str(prefix))
    monkeypatch.setattr(packages, "detect", lambda python=None: {"pip": {"leaked": "1.0"}})

    ctx = snapshot._resolve_env("nopy")
    result = snapshot._detect_packages(ctx)
    assert result["pip"] == {}
    assert result["pip_source"]["status"] == "unknown"
    assert "no Python interpreter" in result["pip_source"]["reason"]


def test_env_with_python_uses_that_interpreter(tmp_path, monkeypatch):
    prefix = tmp_path / "envs" / "withpy"
    (prefix / "bin").mkdir(parents=True)
    py = prefix / "bin" / "python"
    py.write_text("#!/bin/sh\n")
    py.chmod(0o755)
    monkeypatch.setattr(conda, "env_prefix", lambda name: str(prefix))
    seen = []
    monkeypatch.setattr(packages, "detect", lambda python=None: seen.append(python) or {"pip": {}})
    monkeypatch.setattr(packages, "detect_user_site", lambda python, env_pip: {"stub": True})
    monkeypatch.setattr(packages, "detect_user_site", lambda python, env_pip: {"stub": True})

    result = snapshot._detect_packages(snapshot._resolve_env("withpy"))
    assert seen == [str(py)]
    assert result["pip_source"] == {"python": str(py), "user_site": "excluded",
                                    "user_site_visible": {"stub": True}}


def test_unknown_env_is_reported(monkeypatch):
    monkeypatch.setattr(conda, "_find_conda_binary", lambda: "conda")
    monkeypatch.setattr(conda, "_list_envs", lambda binary: [{"name": "base", "path": "/x"}])
    monkeypatch.setattr(conda, "run_cmd", lambda *a, **k: ("conda 1.0", 0))
    monkeypatch.setattr(conda, "_list_packages", lambda binary, env_name=None: [])
    monkeypatch.setattr(packages, "detect", lambda python=None: {"pip": {"leaked": "1.0"}})

    result = conda.detect(env_name="does-not-exist")
    assert "not found" in result["error"]

    ctx = snapshot._resolve_env("does-not-exist")
    assert ctx["prefix"] is None
    assert "not found" in snapshot._detect_packages(ctx)["pip_source"]["reason"]


@pytest.mark.skipif(not site.ENABLE_USER_SITE, reason="user site disabled for this interpreter")
def test_user_site_shadowing_is_recorded(tmp_path, monkeypatch):
    """User-site packages are excluded from pip but still recorded as visible."""
    _plant_user_site_package(tmp_path)
    monkeypatch.setenv("PYTHONUSERBASE", str(tmp_path))
    monkeypatch.delenv("PYTHONNOUSERSITE", raising=False)

    env_pip = {"ReproFakeLeak": "1.0.0", "other": "2.0"}
    info = packages.detect_user_site(sys.executable, env_pip)
    assert info["enabled"] is True
    assert info["path"].startswith(str(tmp_path))
    assert info["packages"] == {"reprofakeleak": "9.9.9"}
    assert info["shadows"] == {
        "reprofakeleak": {"user_site": "9.9.9", "environment": "1.0.0"}
    }


def test_user_site_query_failure_is_unknown(monkeypatch):
    monkeypatch.setattr(packages, "run_cmd", lambda *a, **k: ("", 1))
    info = packages.detect_user_site("/nonexistent/python", {})
    assert info["status"] == "unknown" and info["reason"]


@pytest.mark.skipif(not site.ENABLE_USER_SITE, reason="user site disabled for this interpreter")
def test_user_site_shadowing_is_recorded(tmp_path, monkeypatch):
    """User-site packages are excluded from pip but still recorded as visible."""
    _plant_user_site_package(tmp_path)
    monkeypatch.setenv("PYTHONUSERBASE", str(tmp_path))
    monkeypatch.delenv("PYTHONNOUSERSITE", raising=False)

    env_pip = {"ReproFakeLeak": "1.0.0", "other": "2.0"}
    info = packages.detect_user_site(sys.executable, env_pip)
    assert info["enabled"] is True
    assert info["path"].startswith(str(tmp_path))
    assert info["packages"] == {"reprofakeleak": "9.9.9"}
    assert info["shadows"] == {
        "reprofakeleak": {"user_site": "9.9.9", "environment": "1.0.0"}
    }


def test_user_site_query_failure_is_unknown(monkeypatch):
    monkeypatch.setattr(packages, "run_cmd", lambda *a, **k: ("", 1))
    info = packages.detect_user_site("/nonexistent/python", {})
    assert info["status"] == "unknown" and info["reason"]
