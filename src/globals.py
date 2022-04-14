import os

import supervisely as sly
from supervisely.app.v1.app_service import AppService

my_app = AppService()

api: sly.Api = my_app.public_api
task_id = my_app.task_id

TEAM_ID = int(os.environ["context.teamId"])
WORKSPACE_ID = int(os.environ["context.workspaceId"])
INPUT_PATH = os.environ.get("modal.state.slyFolder", None)
DEFAULT_DATASET_NAME = "ds0"
