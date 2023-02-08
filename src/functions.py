import mimetypes
from os import listdir, walk
from os.path import basename, isdir, isfile, join

import magic

import supervisely as sly
from supervisely.imaging.image import SUPPORTED_IMG_EXTS
from supervisely.io.fs import get_file_ext, get_file_name

SUPPORTED_IMG_EXTS = SUPPORTED_IMG_EXTS
SUPPORTED_IMG_EXTS.append(".nrrd")


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
            if file_ext != ".mpo":
                img = sly.image.read(path, remove_alpha_channel=True)
                sly.image.write(path, img, remove_alpha_channel=True)
            res_batch_names.append(name)
            res_batch_paths.append(path)
        except Exception as e:
            sly.logger.warning(
                "Skip image {!r}: {}".format(name, str(e)), extra={"file_path": path}
            )
    return res_batch_names, res_batch_paths


def get_files(directory) -> list:
    dir_files = []
    for root, _, files in walk(directory):
        validated_files = []
        for file in files:
            path = join(root, file)
            try:
                sly.image.validate_ext(path)
                validated_files.append(path)
            except Exception as e:
                sly.logger.warn(
                    "File skipped {!r}: error occurred during processing {!r}".format(path, str(e))
                )
                continue
        dir_files.extend(validated_files)
    return dir_files


def get_ds_files_map(directory, default_ds_name="ds0") -> dict:
    ds_image_map = {}
    files_list = []
    dirs_list = []
    if not isdir(directory):
        sly.logger.warn(f"Error occurred during processing {directory}. {str(e)}")
        return ds_image_map
    for f in listdir(directory):
        path = join(directory, f)
        if isfile(path):
            try:
                sly.image.validate_ext(path)
                files_list.append(path)
            except Exception as e:
                sly.logger.warn(
                    "File skipped {!r}: error occurred during processing {!r}".format(path, str(e))
                )
                continue
        elif isdir(path):
            dirs_list.append(path)

    ds_image_map[default_ds_name] = files_list
    for path in dirs_list:
        ds_name = basename(path)
        ds_files = get_files(path)
        ds_image_map[ds_name] = ds_files

    return ds_image_map


def validate_mimetypes(images_names: list, images_paths: list) -> list:
    """Validate mimetypes for images."""
    mime = magic.Magic(mime=True)
    for idx, (image_name, image_path) in enumerate(zip(images_names, images_paths)):
        mimetype = mime.from_file(image_path)
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
