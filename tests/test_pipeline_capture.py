"""Regression tests: --pipeline and --container-images capture."""

import hashlib
import os
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from typer.testing import CliRunner

from repro import cli, snapshot
from repro.detectors import containers, pipeline

CONFIG = """
params { outdir = null }
manifest {
    name            = 'nf-core/fakepipe'
    contributors    = [[name: 'Someone Else', github: '@x']]
    version         = '1.0.0'
}
"""
MAIN = "workflow { println 'hi' }\n"


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _git(repo, *args):
    subprocess.run(["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t",
                    "-c", "commit.gpgsign=false"] + list(args),
                   check=True, capture_output=True)


def _fake_pipeline(tmp_path):
    repo = tmp_path / "fakepipe"
    repo.mkdir()
    (repo / "nextflow.config").write_text(CONFIG)
    (repo / "main.nf").write_text(MAIN)
    _git(repo, "init", "-q")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "init")
    commit = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"],
                            capture_output=True, text=True).stdout.strip()
    return repo, commit


def test_pipeline_source_clean(tmp_path):
    repo, commit = _fake_pipeline(tmp_path)
    result = pipeline.detect(str(repo), explicit=True)
    assert result["primary_type"] == "nextflow"
    assert result["checksum_algorithm"] == "sha256"
    assert result["config_checksums"] == {
        "nextflow.config": _sha(CONFIG.encode()),
        "main.nf": _sha(MAIN.encode()),
    }
    src = result["source"]
    assert src["name"] == "nf-core/fakepipe"
    assert src["path"] == str(repo)
    assert src["git_commit"] == commit
    assert src["git_clean"] is True and src["git_changed_paths"] == 0


def test_pipeline_source_dirty(tmp_path):
    repo, _ = _fake_pipeline(tmp_path)
    (repo / "main.nf").write_text(MAIN + "// edited\n")
    (repo / "untracked.txt").write_text("x")
    src = pipeline.detect_source(str(repo))
    assert src["git_clean"] is False and src["git_changed_paths"] == 2


def test_pipeline_source_unknowns_have_reasons(tmp_path):
    plain = tmp_path / "plain"
    plain.mkdir()
    (plain / "main.nf").write_text(MAIN)
    src = pipeline.detect_source(str(plain))
    assert src["name"] is None and src["name_reason"]
    assert src["git_commit"] is None and src["git_clean"] is None and src["git_reason"]
    assert "error" in pipeline.detect_source(str(tmp_path / "missing"))


def test_cwd_scan_has_no_source(tmp_path):
    repo, _ = _fake_pipeline(tmp_path)
    assert "source" not in pipeline.detect(str(repo))


def test_container_images(tmp_path):
    images = tmp_path / "apptainer"
    images.mkdir()
    blobs = {"a-data.img": b"alpha" * 1000, "b.img": os.urandom(3 << 20)}
    for name, data in blobs.items():
        (images / name).write_bytes(data)

    result = containers.detect_images(str(images))
    assert result["directory"] == str(images)
    assert result["file_count"] == 2
    assert result["total_bytes"] == sum(len(d) for d in blobs.values())
    assert result["files"] == [
        {"name": n, "size_bytes": len(d), "sha256": _sha(d)} for n, d in sorted(blobs.items())
    ]


def test_container_images_missing_dir(tmp_path):
    result = containers.detect_images(str(tmp_path / "nope"))
    assert result["error"] and result["files"] == []


def test_images_merge_under_containers():
    data = {"containers": {"runtimes": {}}}
    snapshot._merge_result(data, "Container images", {"file_count": 0, "files": []})
    assert data["containers"] == {"runtimes": {}, "images": {"file_count": 0, "files": []}}


def test_cli_passes_pipeline_and_images(monkeypatch):
    seen = {}
    monkeypatch.setattr(snapshot, "run_snapshot", lambda **kw: seen.update(kw))
    result = CliRunner().invoke(cli.app, ["snapshot", "--pipeline", "/p", "--container-images", "/i"])
    assert result.exit_code == 0, result.output
    assert seen["pipeline_dir"] == "/p" and seen["image_dir"] == "/i"
