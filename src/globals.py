import os
import sys
from distutils.util import strtobool

import supervisely as sly
from dotenv import load_dotenv
from fastapi import FastAPI
from supervisely.app.fastapi import create

from workflow import Workflow

app_root_directory = os.path.dirname(os.getcwd())
sys.path.append(app_root_directory)
sys.path.append(os.path.join(app_root_directory, "src"))
print(f"App root directory: {app_root_directory}")
sly.logger.info(f'PYTHONPATH={os.environ.get("PYTHONPATH", "")}')

if sly.is_development():
    load_dotenv(os.path.join(app_root_directory, "local.env"))
    load_dotenv(os.path.expanduser("~/supervisely.env"))

app = FastAPI()

sly_app = create()

api = sly.Api.from_env()

workflow = Workflow(api)

TASK_ID = sly.env.task_id()
TEAM_ID = sly.env.team_id()
WORKSPACE_ID = sly.env.workspace_id()

PROJECT_ID = sly.env.project_id(raise_not_found=False)
DATASET_ID = sly.env.dataset_id(raise_not_found=False)

INPUT_FILES = os.environ.get("modal.state.files", None)
INPUT_FOLDER = sly.env.folder(raise_not_found=False)
INPUT_FILE = sly.env.file(raise_not_found=False)
sly.logger.info(
    f"App starting... INPUT_FILES: {INPUT_FILES}, INPUT_FOLDER: {INPUT_FOLDER}, INPUT_FILE: {INPUT_FILE}"
)

INPUT_PATH = INPUT_FILES or INPUT_FOLDER or INPUT_FILE
sly.logger.info(f"App starting... INPUT_PATH: {INPUT_PATH}")
CHECKED_INPUT_PATH = INPUT_PATH
if INPUT_PATH is None:
    raise RuntimeError("No input data. Please specify input files or folder.")

OUTPUT_PROJECT_NAME = os.environ.get("modal.state.project_name", "")
DEFAULT_DATASET_NAME = "ds0"

NORMALIZE_EXIF = bool(strtobool(os.getenv("modal.state.normalize_exif", "False")))
REMOVE_ALPHA_CHANNEL = bool(strtobool(os.getenv("modal.state.remove_alpha_channel", "False")))

IS_ON_AGENT = api.file.is_on_agent(INPUT_PATH)
sly.logger.info(f"App starting... IS_ON_AGENT: {IS_ON_AGENT}.")

NEED_DOWNLOAD = NORMALIZE_EXIF or REMOVE_ALPHA_CHANNEL or IS_ON_AGENT
sly.logger.info(f"App starting... NEED_DOWNLOAD: {NEED_DOWNLOAD}.")

REMOVE_SOURCE = bool(strtobool(os.getenv("modal.state.remove_source", "False")))

STORAGE_DIR = sly.app.get_data_dir()

EXT_TO_CONVERT = [".heic", ".avif"]
SUPPORTED_EXTS = [*sly.image.SUPPORTED_IMG_EXTS, *EXT_TO_CONVERT]
