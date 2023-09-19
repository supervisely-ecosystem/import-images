import os
import sys
from distutils.util import strtobool

import supervisely as sly
from fastapi import FastAPI
from supervisely.app.fastapi import create
from supervisely.imaging.image import SUPPORTED_IMG_EXTS

app_root_directory = os.path.dirname(os.getcwd())
sys.path.append(app_root_directory)
sys.path.append(os.path.join(app_root_directory, "src"))
print(f"App root directory: {app_root_directory}")
sly.logger.info(f'PYTHONPATH={os.environ.get("PYTHONPATH", "")}')

# order matters
# from dotenv import load_dotenv
# load_dotenv(os.path.join(app_root_directory, "secret_debug.env"))
# load_dotenv(os.path.join(app_root_directory, "debug.env"))

app = FastAPI()

sly_app = create()

api = sly.Api.from_env()

TASK_ID = int(os.environ["TASK_ID"])
TEAM_ID = int(os.environ["context.teamId"])
WORKSPACE_ID = int(os.environ["context.workspaceId"])

PROJECT_ID = None
DATASET_ID = None

if os.environ.get("modal.state.slyProjectId") is not None:
    PROJECT_ID = int(os.environ.get("modal.state.slyProjectId"))
if os.environ.get("modal.state.slyDatasetId") is not None:
    DATASET_ID = int(os.environ.get("modal.state.slyDatasetId"))

INPUT_FILES = os.environ.get("modal.state.files", None)
INPUT_FOLDER = os.environ.get("modal.state.slyFolder", None)
INPUT_FILE = sly.env.file(raise_not_found=False)
sly.logger.debug(
    f"App starting... INPUT_FILES: {INPUT_FILES}, INPUT_FOLDER: {INPUT_FOLDER}, INPUT_FILE: {INPUT_FILE}"
)

INPUT_PATH = INPUT_FILES or INPUT_FOLDER or INPUT_FILE
sly.logger.debug(f"App starting... INPUT_PATH: {INPUT_PATH}")

OUTPUT_PROJECT_NAME = os.environ.get("modal.state.project_name", "")

NORMALIZE_EXIF = bool(strtobool(os.getenv("modal.state.normalize_exif", "False")))
REMOVE_ALPHA_CHANNEL = bool(strtobool(os.getenv("modal.state.remove_alpha_channel", "False")))

IS_ON_AGENT = api.file.is_on_agent(INPUT_PATH)
sly.logger.debug(f"App starting... IS_ON_AGENT: {IS_ON_AGENT}.")

NEED_DOWNLOAD = NORMALIZE_EXIF or REMOVE_ALPHA_CHANNEL or IS_ON_AGENT
sly.logger.debug(f"App starting... NEED_DOWNLOAD: {NEED_DOWNLOAD}.")

REMOVE_SOURCE = bool(strtobool(os.getenv("modal.state.remove_source", "False")))

DEFAULT_DATASET_NAME = "ds0"
SUPPORTED_IMG_EXTS = SUPPORTED_IMG_EXTS
SUPPORTED_IMG_EXTS.append(".nrrd")

STORAGE_DIR = sly.app.get_data_dir()
