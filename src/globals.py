import os
import sys
from distutils.util import strtobool

import supervisely as sly
from dotenv import load_dotenv
from fastapi import FastAPI
from supervisely.app.fastapi import create
from supervisely.imaging.image import SUPPORTED_IMG_EXTS
from supervisely.io.fs import mkdir

app_root_directory = os.path.dirname(os.getcwd())
sys.path.append(app_root_directory)
sys.path.append(os.path.join(app_root_directory, "src"))
print(f"App root directory: {app_root_directory}")
sly.logger.info(f'PYTHONPATH={os.environ.get("PYTHONPATH", "")}')

# order matters
load_dotenv(os.path.join(app_root_directory, "secret_debug.env"))
load_dotenv(os.path.join(app_root_directory, "debug.env"))

app = FastAPI()

sly_app = create()

api = sly.Api.from_env()

TASK_ID = int(os.environ["TASK_ID"])
TEAM_ID = int(os.environ["context.teamId"])
WORKSPACE_ID = int(os.environ["context.workspaceId"])

PROJECT_ID = None
DATASET_ID = None

if os.environ.get('modal.state.slyProjectId') is not None:
    PROJECT_ID = int(os.environ.get('modal.state.slyProjectId'))
if os.environ.get('modal.state.slyDatasetId') is not None:
    DATASET_ID = int(os.environ.get('modal.state.slyDatasetId'))

INPUT_PATH = os.environ.get("modal.state.slyFolder", None)
OUTPUT_PROJECT_NAME = os.environ.get("modal.state.project_name", "")

NORMALIZE_EXIF = bool(strtobool(os.getenv("modal.state.normalize_exif")))
REMOVE_ALPHA_CHANNEL = bool(strtobool(os.getenv("modal.state.remove_alpha_channel")))
CONVERT_TIFF = bool(strtobool(os.getenv("modal.state.convert_tiff")))
NEED_DOWNLOAD = NORMALIZE_EXIF or REMOVE_ALPHA_CHANNEL
REMOVE_SOURCE = bool(strtobool(os.getenv("modal.state.remove_source")))

DEFAULT_DATASET_NAME = "ds0"
SUPPORTED_IMG_EXTS = SUPPORTED_IMG_EXTS
if CONVERT_TIFF:
    SUPPORTED_IMG_EXTS.append(".tiff")
STORAGE_DIR = os.path.join(app_root_directory, "debug", "data", "storage_dir")
mkdir(STORAGE_DIR, True)
