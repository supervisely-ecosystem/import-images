"""Offline test harness: runs src/main.py against a small in-memory fake of sly.Api.

No Supervisely server is contacted. Run from the repo root:
    python -m pytest tests
with the SDK version from dev_requirements.txt installed (plus pytest).
"""
import importlib
import os
import sys
from types import SimpleNamespace

import pytest

SRC_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")
APP_MODULES = ("globals", "functions", "main", "workflow")


class FakeFileApi:
    def __init__(self, files):
        # files: {remote_path: mime}
        self.files = dict(files)
        self.removed = []

    def list(self, team_id, path, *args, **kwargs):
        return [
            {
                "path": p,
                "name": os.path.basename(p),
                "hash": f"hash-{p}",
                "meta": {"ext": os.path.splitext(p)[1].lstrip(".")},
            }
            for p in self.files
            if p.startswith(path)
        ]

    def is_on_agent(self, remote_path):
        return remote_path.startswith("agent://")

    def get_info_by_path(self, team_id, remote_path):
        return SimpleNamespace(path=remote_path, mime=self.files[remote_path])

    def remove(self, team_id, path):
        self.removed.append(path)


class FakeImageApi:
    def __init__(self, reject_names=()):
        self.reject_names = set(reject_names)
        self.uploaded = []  # (dataset_id, name)

    def get_list(self, dataset_id):
        return []

    def upload_hashes(self, dataset_id, names, hashes, **kwargs):
        bad = [n for n in names if n in self.reject_names]
        if bad:
            # what the SDK raises when images.bulk.add answers HTTP 400 after retries
            raise RuntimeError(f"HTTP 400 from images.bulk.add for {bad}")
        infos = []
        for name in names:
            self.uploaded.append((dataset_id, name))
            infos.append(SimpleNamespace(id=len(self.uploaded), name=name))
        return infos

    upload_paths = None  # not used: tests run without NEED_DOWNLOAD


class FakeApi:
    def __init__(self, files, reject_names=()):
        self.file = FakeFileApi(files)
        self.image = FakeImageApi(reject_names)
        self._ds = 0
        self.project = SimpleNamespace(
            get_info_by_id=lambda id: None,
            create=lambda workspace_id, name, change_name_if_conflict=False: SimpleNamespace(
                id=100, name=name
            ),
        )
        self.dataset = SimpleNamespace(create=self._create_dataset, get_info_by_id=None)
        self.output_project = None
        self.task = SimpleNamespace(set_output_project=self._set_output_project)

    def _create_dataset(self, project_id, name, parent_id=None, change_name_if_conflict=False):
        self._ds += 1
        return SimpleNamespace(id=self._ds, name=name)

    def _set_output_project(self, task_id, project_id, project_name=None):
        self.output_project = project_id


@pytest.fixture
def run_app(tmp_path, monkeypatch):
    """Import the app with the given Team Files content and return (main, g, api)."""
    import supervisely as sly

    def _run(files, input_path="/images/", remove_source=True, reject_names=()):
        api = FakeApi(files, reject_names)
        monkeypatch.setenv("ENV", "production")
        monkeypatch.setenv("SLY_APP_DATA_DIR", str(tmp_path / "data"))
        monkeypatch.setenv("TASK_ID", "1")
        monkeypatch.setenv("context.teamId", "8")
        monkeypatch.setenv("context.workspaceId", "9")
        monkeypatch.setenv("modal.state.slyFolder", input_path)
        monkeypatch.setenv("modal.state.remove_source", "true" if remove_source else "false")
        for name in ("modal.state.files", "modal.state.slyFile", "context.projectId",
                     "context.datasetId", "modal.state.normalize_exif",
                     "modal.state.remove_alpha_channel"):
            monkeypatch.delenv(name, raising=False)
        monkeypatch.setattr(sly.Api, "from_env", classmethod(lambda cls, *a, **k: api))
        monkeypatch.syspath_prepend(SRC_DIR)
        for mod in APP_MODULES:
            sys.modules.pop(mod, None)
        main = importlib.import_module("main")
        g = importlib.import_module("globals")
        g.workflow = SimpleNamespace(add_output=lambda project_id: None)
        return main, g, api

    yield _run
    for mod in APP_MODULES:
        sys.modules.pop(mod, None)
