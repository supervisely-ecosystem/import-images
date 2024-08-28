import mimetypes
import os
import pathlib
import re
from typing import List

import magic

# * do not remove folllowing imports, it is used to register avif/heic formats
import pillow_avif  # noqa
import supervisely as sly
from PIL import Image
from pillow_heif import register_heif_opener
from supervisely.io.fs import get_file_ext, get_file_name, get_file_name_with_ext

import globals as g

register_heif_opener()


def get_project_name_from_input_path(input_path: str) -> str:
    """Returns project name from target sly folder name."""
    full_path_dir = os.path.dirname(input_path)
    return os.path.basename(full_path_dir) or sly.fs.get_file_name(input_path)


def download_project(api: sly.Api, input_path):
    """Download target directory from Team Files if NEED_DOWNLOAD is True."""
    remote_path = input_path.lstrip("/")
    if api.file.is_on_agent(input_path):
        agent_id, remote_path = api.file.parse_agent_id_and_path(input_path)

    if api.file.exists(g.TEAM_ID, input_path):
        local_save_path = os.path.join(g.STORAGE_DIR, remote_path)
        api.file.download(g.TEAM_ID, input_path, local_save_path)
    else:
        local_save_path = os.path.join(g.STORAGE_DIR, remote_path)
        if not local_save_path.endswith("/"):
            local_save_path += "/"
        api.file.download_directory(g.TEAM_ID, input_path, local_save_path)
    return local_save_path


def validate_file_without_ext(file_path: str) -> bool:
    try:
        pil_img = Image.open(file_path)
        pil_img.load()  # Validate image data. Because 'open' is lazy method.
        return True
    except Exception as e:
        return False


def unpack_archive_on_team_files(api: sly.Api, archive_path) -> List[sly.api.file_api.FileInfo]:
    sly.logger.debug(f"Unpacking archive {archive_path} on Team Files")
    archives_dir = os.path.join(g.STORAGE_DIR, "archives")
    unpacked_dir = os.path.join(g.STORAGE_DIR, "images_project")
    sly.fs.mkdir(archives_dir)
    sly.logger.debug(f"Path to the archives: {archives_dir}, to unpacked files: {unpacked_dir}")

    download_path = os.path.join(archives_dir, sly.fs.get_file_name_with_ext(archive_path))
    api.file.download(g.TEAM_ID, archive_path, download_path)
    sly.logger.debug(f"Archive {archive_path} downloaded to {download_path}")

    unpacked_path = os.path.join(unpacked_dir, sly.fs.get_file_name(archive_path))
    sly.fs.mkdir(unpacked_path)
    filename = sly.fs.get_file_name_with_ext(download_path)
    ext = sly.fs.get_file_ext(filename).lower()
    if sly.fs.is_archive(download_path):
        try:
            sly.fs.unpack_archive(download_path, unpacked_path)
        except Exception as e:
            raise RuntimeError(f"Failed to unpack archive {filename}: {repr(e)}")
    elif validate_file_without_ext(download_path):
        try:
            file_name = get_file_name(download_path)
            sly.logger.debug(f"File {file_name} has no extension, but it is an image.")
            file_name = validate_mimetypes([file_name], [download_path], is_local=True)[0]
            sly.fs.copy_file(download_path, os.path.join(unpacked_path, file_name))
        except Exception as e:
            raise RuntimeError(f"Failed to process file {filename}: {repr(e)}") from e
    elif ext == ".pdf":
        raise RuntimeError(f"Use 'Import PDF as Images' app to import PDF files")
    elif ext == ".mp4":
        raise RuntimeError(
            f"Use 'Import Videos' app to import video and "
            "'Videos project to images project' app to get frames from it"
        )
    elif ext == ".csv":
        raise RuntimeError(f"Use 'Import Images from CSV' app to import CSV files")
    else:
        raise RuntimeError(f"Provided file is not an archive: {filename}")
    filter_fn = lambda x: sly.fs.get_file_ext(x).lower() in g.EXT_TO_CONVERT
    files_to_convert = sly.fs.list_files_recursively(unpacked_path, filter_fn=filter_fn)
    if len(files_to_convert) > 0:
        g.NEED_DOWNLOAD = True
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
            if file_ext in g.EXT_TO_CONVERT:
                path, name = convert_to_jpg(path)
                if path is None:
                    continue
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
            if file_ext.lower() not in g.SUPPORTED_EXTS:
                sly.image.validate_ext(full_path_file)
        except Exception as e:
            sly.logger.warn(
                "File skipped {!r}: error occurred during processing {!r}".format(
                    full_path_file, str(e)
                )
            )
            continue

        file_name = get_file_name_with_ext(full_path_file)
        file_ext = get_file_ext(full_path_file)
        if file_ext.lower() in g.EXT_TO_CONVERT:
            g.NEED_DOWNLOAD = True
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

    if re.match(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3}", ds_name):
        ds_name = f"dataset {ds_name[:-4]}" # remove milliseconds
    return ds_name


def validate_mimetypes(images_names: list, images_paths: list, is_local: bool = False) -> list:
    """Validate mimetypes for images."""

    mimetypes.add_type("image/webp", ".webp")  # to extend types_map
    mimetypes.add_type("image/jpeg", ".jfif")  # to extend types_map

    mime = magic.Magic(mime=True)
    for idx, (image_name, image_path) in enumerate(zip(images_names, images_paths)):
        if g.NEED_DOWNLOAD or is_local:
            mimetype = mime.from_file(image_path)
        else:
            file_info = g.api.file.get_info_by_path(team_id=g.TEAM_ID, remote_path=image_path)
            mimetype = file_info.mime
        file_ext = get_file_ext(image_name).lower()
        if file_ext in mimetypes.guess_all_extensions(mimetype):
            continue

        new_img_ext = mimetypes.guess_extension(mimetype)
        if new_img_ext == ".pdf":
            raise RuntimeError(f"Use 'Import PDF as Images' app to import PDF files")
        elif new_img_ext == ".mp4":
            raise RuntimeError(
                f"Use 'Import Videos' and 'Videos project to images project' "
                "apps to import video and get frames from it"
            )
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


def convert_to_jpg(path) -> tuple:
    """Convert image to jpg."""
    name = get_file_name(path)
    new_name = f"{name}.jpeg"
    dirname = os.path.dirname(path)
    new_path = os.path.join(dirname, new_name)
    try:
        with Image.open(path) as image:
            image.convert("RGB").save(new_path)
        sly.fs.silent_remove(path)
        return new_path, new_name
    except Exception as e:
        sly.logger.warn(f"Skip image {name}: {repr(e)}", extra={"file_path": path})
