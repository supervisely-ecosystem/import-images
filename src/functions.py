import os
import pathlib

import supervisely as sly
from PIL import Image
from supervisely.io.fs import get_file_ext, get_file_name, get_file_name_with_ext
from supervisely.video.import_utils import get_dataset_name

import globals as g


def get_project_name_from_input_path(input_path: str) -> str:
    """Returns project name from target sly folder name."""
    full_path_dir = os.path.dirname(input_path)
    return os.path.basename(full_path_dir)


# def get_dataset_name(file_path: str) -> str:
#     """Returns dataset name from file path."""
#     full_path_dir = f"{os.path.dirname(file_path)}/"
#     relative_path = os.path.relpath(g.INPUT_PATH, full_path_dir)
#     path_parts = pathlib.Path(file_path).parts
#     if relative_path == ".":
#         return g.DEFAULT_DATASET_NAME
#     elif relative_path == "..":
#         return path_parts[-2]
#     else:
#         path_parts = pathlib.Path(file_path).parts
#         return f"{path_parts[-3]}_{path_parts[-2]}"


def convert_tiff_to_jpeg(path: str) -> tuple:
    """Convert .tiff image format to .jpeg."""
    name = f"{get_file_name(path)}.jpg"
    img = Image.open(path)
    path = f"{os.path.dirname(path)}/{name}"
    img = img.convert("RGB")
    img.save(path, "JPEG")
    return name, path


def process_tiff_images(
    api: sly.Api, batch_names: list, batch_paths: list, batch_hashes: list
) -> tuple:
    """Detect and convert .tiff images in dataset if NEED_DOWNLOAD is false."""
    tiff_names = []
    tiff_paths = []
    for image_name, image_path, images_hash in zip(
        batch_names, batch_paths, batch_hashes
    ):
        if image_path.endswith(".tiff"):
            local_save_path = f"{g.STORAGE_DIR}{image_path}"
            api.file.download(
                team_id=g.TEAM_ID,
                remote_path=image_path,
                local_save_path=local_save_path,
            )
            tiff_name, tiff_path = convert_tiff_to_jpeg(local_save_path)
            tiff_names.append(tiff_name)
            tiff_paths.append(tiff_path)
            batch_names.remove(image_name)
            batch_paths.remove(image_path)
            batch_hashes.remove(images_hash)
    return tiff_names, tiff_paths


def normalize_exif_and_remove_alpha_channel(
    api: sly.Api, names: list, paths: list, hashes: list
) -> tuple:
    """
    If flags normalize exif, remove alpha channel or convert .tiff to .jpeg set to True,
    download and process images with corresponding flags.
    """
    res_batch_names = []
    res_batch_paths = []
    app_batch_paths = [f"{g.STORAGE_DIR}{batch_path}" for batch_path in paths]
    remote_ds_dir = f"{os.path.dirname(paths[0])}/"
    local_save_dir = f"{g.STORAGE_DIR}{remote_ds_dir}/"
    api.file.download_directory(
        g.TEAM_ID, remote_path=remote_ds_dir, local_save_path=local_save_dir
    )
    for name, path in zip(names, app_batch_paths):
        try:
            file_ext = get_file_ext(path).lower()
            if file_ext == ".tiff" and g.CONVERT_TIFF:
                name, path = convert_tiff_to_jpeg(path)
            elif file_ext != ".mpo" and (g.REMOVE_ALPHA_CHANNEL or g.NORMALIZE_EXIF):
                img = sly.image.read(path, g.REMOVE_ALPHA_CHANNEL)
                sly.image.write(path, img, g.REMOVE_ALPHA_CHANNEL)
            res_batch_names.append(name)
            res_batch_paths.append(path)
        except Exception as e:
            sly.logger.warning(
                "Skip image {!r}: {}".format(name, str(e)), extra={"file_path": path}
            )
    return res_batch_names, res_batch_paths, local_save_dir


def get_datasets_images_map(dir_info: list) -> tuple:
    """Creates a dictionary map based on api response from the target sly folder data."""
    datasets_images_map = {}
    for file_info in dir_info:
        full_path_file = file_info["path"]
        try:
            file_ext = get_file_ext(full_path_file)
            if file_ext not in g.SUPPORTED_IMG_EXTS:
                sly.image.validate_ext(full_path_file)
        except Exception as e:
            sly.logger.warn(
                "File skipped {!r}: error occurred during processing {!r}".format(
                    full_path_file, str(e)
                )
            )
            continue

        file_name = get_file_name_with_ext(full_path_file)
        file_hash = file_info["hash"]
        ds_name = get_dataset_name(full_path_file.lstrip("/"))
        if ds_name not in datasets_images_map.keys():
            datasets_images_map[ds_name] = {
                "img_names": [],
                "img_paths": [],
                "img_hashes": [],
            }

        if file_name in datasets_images_map[ds_name]["img_names"]:
            temp_name = sly.fs.get_file_name(full_path_file)
            temp_ext = sly.fs.get_file_ext(full_path_file)
            new_file_name = f"{temp_name}_{sly.rand_str(5)}{temp_ext}"
            sly.logger.warning(
                "Name {!r} already exists in dataset {!r}: renamed to {!r}".format(
                    file_name, ds_name, new_file_name
                )
            )
            file_name = new_file_name

        datasets_images_map[ds_name]["img_names"].append(file_name)
        datasets_images_map[ds_name]["img_paths"].append(full_path_file)
        datasets_images_map[ds_name]["img_hashes"].append(file_hash)

    datasets_names = list(datasets_images_map.keys())
    return datasets_names, datasets_images_map
