import os
import pathlib

import supervisely as sly
from fastapi import FastAPI
from supervisely.app.fastapi import create

app_root_directory = str(pathlib.Path(__file__).parent.absolute().parents[0])
sly.logger.info(f"App root directory: {app_root_directory}")
sly.logger.info(f'PYTHONPATH={os.environ.get("PYTHONPATH", "")}')

app = FastAPI()

sly_app = create()

api = sly.Api.from_env()

TEAM_ID = int(os.environ["context.teamId"])
WORKSPACE_ID = int(os.environ["context.workspaceId"])
INPUT_PATH = os.environ.get("modal.state.slyFolder", None)

NORMALIZE_EXIF = os.getenv("modal.state.normalize_exif", 'False').lower() in ('true', '1', 't')
REMOVE_ALPHA_CHANNEL = os.getenv("modal.state.remove_alpha_channel", 'False').lower() in ('true', '1', 't')
CONVERT_TIFF = os.getenv("modal.state.convert_tiff", 'False').lower() in ('true', '1', 't')
NEED_DOWNLOAD = NORMALIZE_EXIF or REMOVE_ALPHA_CHANNEL or CONVERT_TIFF
REMOVE_SOURCE = os.getenv("modal.state.remove_source", 'False').lower() in ('true', '1', 't')

DEFAULT_DATASET_NAME = "ds0"
SUPPORTED_IMG_EXTS = [".jpg", ".jpeg", ".mpo", ".bmp", ".png", ".webp"]
if CONVERT_TIFF:
    SUPPORTED_IMG_EXTS.append(".tiff")
STORAGE_DIR = os.path.join(app_root_directory, "debug", "data", "storage_dir")
