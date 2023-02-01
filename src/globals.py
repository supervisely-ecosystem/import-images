import os
import sys
from distutils.util import strtobool
import supervisely as sly
from supervisely.imaging.image import SUPPORTED_IMG_EXTS

app_root_directory = os.path.dirname(os.getcwd())
sys.path.append(app_root_directory)
sys.path.append(os.path.join(app_root_directory, "src"))
print(f"App root directory: {app_root_directory}")
sly.logger.info(f'PYTHONPATH={os.environ.get("PYTHONPATH", "")}')

api = sly.Api.from_env()

INPUT_PATH = os.environ.get("modal.state.files", None)
if INPUT_PATH is None or INPUT_PATH == "":
    INPUT_PATH = os.environ.get("modal.state.slyFolder")

OUTPUT_PROJECT_NAME = os.environ.get("modal.state.project_name", "")

NORMALIZE_EXIF = bool(strtobool(os.getenv("modal.state.normalize_exif", "False")))
REMOVE_ALPHA_CHANNEL = bool(strtobool(os.getenv("modal.state.remove_alpha_channel", "False")))
IS_ON_AGENT = api.file.is_on_agent(INPUT_PATH)
NEED_DOWNLOAD = NORMALIZE_EXIF or REMOVE_ALPHA_CHANNEL or IS_ON_AGENT
REMOVE_SOURCE = bool(strtobool(os.getenv("modal.state.remove_source", "False")))

DEFAULT_DATASET_NAME = "ds0"
SUPPORTED_IMG_EXTS = SUPPORTED_IMG_EXTS
SUPPORTED_IMG_EXTS.append(".nrrd")

STORAGE_DIR = sly.app.get_data_dir()
