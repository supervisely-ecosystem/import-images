import os
import pathlib
import supervisely as sly
from PIL import Image
from supervisely.io.fs import (get_file_ext, get_file_name,
                               get_file_name_with_ext)
import globals as g


def get_project_name_from_input_path(input_path: str) -> str:
    """Returns project name from target sly folder name."""
    full_path_dir = os.path.dirname(input_path)
    return os.path.basename(full_path_dir)


def download_project(api, input_path):
    """Download target directory from Team Files if NEED_DOWNLOAD is True."""
    remote_proj_dir = input_path
    local_save_dir = f"{g.STORAGE_DIR}{remote_proj_dir}/"
    api.file.download_directory(
        g.TEAM_ID, remote_path=remote_proj_dir, local_save_path=local_save_dir
    )
    return local_save_dir


def convert_tiff_to_jpeg(name, path: str) -> tuple:
    """Convert .tiff image format to .jpeg."""
    name = f"{get_file_name(name)}.tiff.jpg"
    img = Image.open(path)
    path = f"{os.path.dirname(path)}/{name}"
    img = img.convert("RGB")
    img.save(path, "JPEG")
    return name, path


def process_tiff_images(
        api: sly.Api, batch_names: list, batch_paths: list, batch_hashes: list
) -> tuple:
    """Detect and convert .tiff images in dataset if NEED_DOWNLOAD is False."""
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
            tiff_name, tiff_path = convert_tiff_to_jpeg(image_name, local_save_path)
            tiff_names.append(tiff_name)
            tiff_paths.append(tiff_path)
            batch_names.remove(image_name)
            batch_paths.remove(image_path)
            batch_hashes.remove(images_hash)
    return tiff_names, tiff_paths, batch_names, batch_hashes


def normalize_exif_and_remove_alpha_channel(names: list, paths: list) -> tuple:
    """
    If flags normalize exif, remove alpha channel or convert .tiff to .jpeg set to True,
    download and process images with corresponding flags.
    """
    res_batch_names = []
    res_batch_paths = []
    for name, path in zip(names, paths):
        try:
            file_ext = get_file_ext(path).lower()
            if file_ext == ".tiff" and g.CONVERT_TIFF:
                name, path = convert_tiff_to_jpeg(name, path)
            elif file_ext != ".mpo" and (g.REMOVE_ALPHA_CHANNEL or g.NORMALIZE_EXIF):
                img = sly.image.read(path, g.REMOVE_ALPHA_CHANNEL)
                sly.image.write(path, img, g.REMOVE_ALPHA_CHANNEL)
            res_batch_names.append(name)
            res_batch_paths.append(path)
        except Exception as e:
            sly.logger.warning(
                "Skip image {!r}: {}".format(name, str(e)), extra={"file_path": path}
            )
    return res_batch_names, res_batch_paths


def get_datasets_images_map(dir_info: list, dataset_name=None) -> tuple:
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
        if dataset_name is not None:
            ds_name = dataset_name
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


def get_dataset_name(file_path, default="ds0"):
    dir_path = os.path.split(file_path)[0]
    ds_name = default
    path_parts = pathlib.Path(dir_path).parts
    if len(path_parts) != 1:
        ds_name = path_parts[3]
    return ds_name
