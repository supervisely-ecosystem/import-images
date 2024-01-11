import mimetypes
import os
import pathlib
from typing import List

import magic
import supervisely as sly
from supervisely.io.fs import get_file_ext, get_file_name, get_file_name_with_ext

import globals as g


def get_project_name_from_input_path(input_path: str) -> str:
    """Returns project name from target sly folder name."""
    full_path_dir = os.path.dirname(input_path)
    return os.path.basename(full_path_dir) or sly.fs.get_file_name(input_path)


def download_project(api: sly.Api, input_path):
    """Download target directory from Team Files if NEED_DOWNLOAD is True."""
    remote_proj_dir = input_path
    if api.file.is_on_agent(input_path):
        agent_id, path_on_agent = api.file.parse_agent_id_and_path(input_path)
        local_save_dir = f"{g.STORAGE_DIR}{path_on_agent}/"
    else:
        local_save_dir = f"{g.STORAGE_DIR}{remote_proj_dir}/"
    local_save_dir = local_save_dir.replace("//", "/")
    api.file.download_directory(
        g.TEAM_ID, remote_path=remote_proj_dir, local_save_path=local_save_dir
    )
    return local_save_dir


def unpack_archive_on_team_files(api: sly.Api, archive_path) -> List[sly.api.file_api.FileInfo]:
    sly.logger.debug(f"Unpacking archive {archive_path} on Team Files")
    archives_dir = os.path.join(g.STORAGE_DIR, "archives")
    unpacked_dir = os.path.join(g.STORAGE_DIR, "unpacked")
    sly.fs.mkdir(archives_dir)
    sly.logger.debug(f"Path to the archives: {archives_dir}, to unpacked files: {unpacked_dir}")

    download_path = os.path.join(archives_dir, sly.fs.get_file_name_with_ext(archive_path))
    api.file.download(g.TEAM_ID, archive_path, download_path)
    sly.logger.debug(f"Archive {archive_path} downloaded to {download_path}")

    unpacked_path = os.path.join(unpacked_dir, sly.fs.get_file_name(archive_path))
    sly.fs.mkdir(unpacked_path)
    try:
        sly.fs.unpack_archive(download_path, unpacked_path)
    except Exception as e:
        filename = sly.fs.get_file_name_with_ext(download_path)
        raise RuntimeError(
            f"Provided file is not an archive: {filename} or it is corrupted: {str(e)}"
        )
    sly.logger.debug(f"Archive {download_path} unpacked to {unpacked_path}")

    upload_path = f"/import-images/temp/{sly.fs.get_file_name(archive_path)}"
    upload_path = api.file.get_free_dir_name(g.TEAM_ID, upload_path)

    sly.logger.debug(f"Uploading unpacked files to {upload_path}")

    api.file.upload_directory(g.TEAM_ID, unpacked_path, upload_path)
    sly.logger.debug(f"Unpacked files uploaded to {upload_path}")

    dir_info = api.file.list(g.TEAM_ID, upload_path)
    g.CHECKED_INPUT_PATH = upload_path

    return dir_info


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
            if file_ext not in sly.image.SUPPORTED_IMG_EXTS:
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
            except Exception:
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
        if g.api.file.is_on_agent(full_path_file):
            agent_id, full_path_file = g.api.file.parse_agent_id_and_path(full_path_file)
        datasets_images_map[ds_name]["img_paths"].append(full_path_file)
        datasets_images_map[ds_name]["img_hashes"].append(file_hash)

    datasets_names = list(datasets_images_map.keys())
    return datasets_names, datasets_images_map


def get_dataset_name(file_path: str, default: str = "ds0") -> str:
    """Dataset name from image path."""
    sly.logger.debug(f"get_dataset_name() started parsing  file_path: {file_path}")
    dir_path = os.path.split(file_path)[0]
    ds_name = default
    path_parts = pathlib.Path(dir_path).parts
    if len(path_parts) != 1:
        sly.logger.debug(f"get_dataset_name() found following path_parts: {path_parts}")

        # ? This code uses root directory after drag-n-drop, ignoring structure.
        # ? Why is it here?
        # if g.INPUT_PATH.startswith("/import/import-images/"):
        #     ds_name = path_parts[3]
        # else:
        ds_name = path_parts[-1]

    sly.logger.debug(f"get_dataset_name() will return ds_name: {ds_name}")

    return ds_name


def validate_mimetypes(images_names: list, images_paths: list) -> list:
    """Validate mimetypes for images."""

    mimetypes.add_type("image/webp", ".webp")  # to extend types_map
    mimetypes.add_type("image/jpeg", ".jfif")  # to extend types_map

    mime = magic.Magic(mime=True)
    for idx, (image_name, image_path) in enumerate(zip(images_names, images_paths)):
        if g.NEED_DOWNLOAD:
            mimetype = mime.from_file(image_path)
        else:
            file_info = g.api.file.get_info_by_path(team_id=g.TEAM_ID, remote_path=image_path)
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


def check_names_uniqueness(api: sly.Api, dataset_id, batch_names) -> list:
    """Check names uniqueness."""
    existing_images = api.image.get_list(dataset_id)
    existing_names = [image_info.name for image_info in existing_images]

    for idx, name in enumerate(batch_names):
        if name in existing_names:
            new_name = api.image.get_free_name(dataset_id, name)
            batch_names[idx] = new_name
            sly.logger.warn(
                f"Name {name} already exists in dataset {dataset_id}: renamed to {new_name}"
            )
    return batch_names
