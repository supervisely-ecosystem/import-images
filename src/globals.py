import os

import supervisely as sly
from fastapi import FastAPI
from supervisely.app.fastapi import create

app = FastAPI()

sly_app = create()

api = sly.Api.from_env()

TEAM_ID = int(os.environ["context.teamId"])
WORKSPACE_ID = int(os.environ["context.workspaceId"])
INPUT_PATH = os.environ.get("modal.state.slyFolder", None)
DEFAULT_DATASET_NAME = "ds0"
