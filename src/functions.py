import os
import pathlib

import supervisely as sly
from supervisely.io.fs import get_file_name_with_ext

import globals as g


def get_project_name_from_input_path(input_path: str) -> str:
    """Returns project name from target sly folder name."""
    full_path_dir = os.path.dirname(input_path)
    return os.path.basename(full_path_dir)


def get_dataset_name(file_path: str) -> str:
    """Returns dataset name from file path."""
    full_path_dir = f"{os.path.dirname(file_path)}/"
    relative_path = os.path.relpath(g.INPUT_PATH, full_path_dir)
    path_parts = pathlib.Path(file_path).parts
    if relative_path == ".":
        return g.DEFAULT_DATASET_NAME
    elif relative_path == "..":
        return path_parts[-2]
    else:
        path_parts = pathlib.Path(file_path).parts
        return f"{path_parts[-3]}_{path_parts[-2]}"


def get_datasets_images_map(dir_info: list) -> tuple:
    """Creates a dictionary map based on api response from the target sly folder data."""
    datasets_images_map = {}
    for file_info in dir_info:
        if file_info["meta"]["mime"].startswith("image"):
            full_path_file = file_info["path"]

            try:
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
            ds_name = get_dataset_name(full_path_file)

            if ds_name not in datasets_images_map.keys():
                datasets_images_map[ds_name] = {"img_names": [], "img_hashes": []}

            datasets_images_map[ds_name]["img_names"].append(file_name)
            datasets_images_map[ds_name]["img_hashes"].append(file_hash)

    datasets_names = list(datasets_images_map.keys())
    return datasets_names, datasets_images_map
