import supervisely as sly
from supervisely.imaging.image import SUPPORTED_IMG_EXTS


api = sly.Api.from_env()


INPUT_PATH = "/import_images"

NORMALIZE_EXIF = None
REMOVE_ALPHA_CHANNEL = None
IS_ON_AGENT = None
NEED_DOWNLOAD = None
REMOVE_SOURCE = None

DEFAULT_DATASET_NAME = "ds0"
SUPPORTED_IMG_EXTS = SUPPORTED_IMG_EXTS
SUPPORTED_IMG_EXTS.append(".nrrd")

STORAGE_DIR = sly.app.get_data_dir()
