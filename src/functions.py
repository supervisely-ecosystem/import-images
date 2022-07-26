import mimetypes
import os
import pathlib

import magic
import supervisely as sly
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


def normalize_exif_and_remove_alpha_channel(names: list, paths: list) -> tuple:
    """
    If flags normalize exif, remove alpha channel set to True,
    download and process images with corresponding flags.
    """
    res_batch_names = []
    res_batch_paths = []
    for name, path in zip(names, paths):
        try:
            file_ext = get_file_ext(path).lower()
            if file_ext != ".mpo" and (g.REMOVE_ALPHA_CHANNEL or g.NORMALIZE_EXIF):
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
        if dataset_name is not None:
            ds_name = dataset_name
        else:
            try:
                ds_name = get_dataset_name(full_path_file.lstrip("/"))
            except:
                ds_name = g.DEFAULT_DATASET_NAME

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


# def get_dataset_name(file_path: str, default: str = "ds0") -> str:
#     """Dataset name from image path."""
#     dir_path = os.path.split(file_path)[0]
#     path_parts = pathlib.Path(dir_path).parts
#     return path_parts[3] if len(path_parts) != 1 else default


def get_dataset_name(file_path: str, default: str = "ds0") -> str:
    """Dataset name from image path."""
    dir_path = os.path.split(file_path)[0]
    ds_name = default
    path_parts = pathlib.Path(dir_path).parts
    if len(path_parts) != 1:
        if g.INPUT_PATH.startswith("/import/import-images/"):
            ds_name = path_parts[3]
        else:
            ds_name = path_parts[-1]
    return ds_name


def validate_mimetypes(images_names: list, images_paths: list) -> list:
    """Validate mimetypes for images."""
    mime = magic.Magic(mime=True)
    for idx, (image_name, image_path) in enumerate(zip(images_names, images_paths)):
        if g.NEED_DOWNLOAD:
            mimetype = mime.from_file(image_path)
            file_ext = get_file_ext(image_name).lower()
        else:
            file_info = g.api.file.get_info_by_path(
                team_id=g.TEAM_ID, remote_path=image_path
            )
            mimetype = file_info.mime
            file_ext = get_file_ext(image_name).lower()

        if file_ext in mimetypes.guess_all_extensions(mimetype):
            continue

        new_img_ext = mimetypes.guess_extension(mimetype)
        new_img_name = f"{get_file_name(image_name)}{new_img_ext}"
        images_names[idx] = new_img_name
        sly.logger.warn(
            f"Image {image_name} extension doesn't have correct mimetype {mimetype}. Image has been converted to {new_img_ext}"
        )

    return images_names
