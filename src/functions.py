import os

from supervisely.io.fs import get_file_name_with_ext

import globals as g


def get_project_name_from_input_path(input_path: str) -> str:
    """Returns project name from target sly folder name."""
    full_path_dir = os.path.dirname(input_path)
    return os.path.basename(full_path_dir)


def get_datasets_images_map(dir_info: list, project_name: str) -> tuple:
    """Creates a dictionary map based on api response from the target sly folder data."""
    datasets_images_map = {}
    for file_info in dir_info:
        if file_info["meta"]["mime"].startswith("image"):
            full_path_file = file_info["path"]
            full_path_dir = os.path.dirname(full_path_file)

            file_name = get_file_name_with_ext(full_path_file)
            file_hash = file_info["hash"]

            ds_name = os.path.basename(full_path_dir)
            if ds_name == project_name:
                ds_name = g.DEFAULT_DATASET_NAME
            if ds_name not in datasets_images_map.keys():
                datasets_images_map[ds_name] = {"img_names": [], "img_hashes": []}

            datasets_images_map[ds_name]["img_names"].append(file_name)
            datasets_images_map[ds_name]["img_hashes"].append(file_hash)

    datasets_names = list(datasets_images_map.keys())
    return datasets_names, datasets_images_map
