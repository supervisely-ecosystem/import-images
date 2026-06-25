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

mimetypes.add_type("image/webp", ".webp")  # to extend types_map
mimetypes.add_type("image/jpeg", ".jfif")  # to extend types_map
mimetypes.add_type("image/nrrd", ".nrrd")  # to extend types_map

register_heif_opener()

def get_project_name() -> str:
    project_name = g.OUTPUT_PROJECT_NAME
    if any(char in project_name for char in ['/', '|', '\\']):
        sly.logger.warning('Project name you have provided is invalid. '
                      'Project and dataset names cannot contain following characters: "\\", "/", "|". '
                      'Thus, destination project will not contain them.', extra={'input name': project_name})
        project_name = project_name.replace('/', '').replace('|', '').replace('\\', '')
    if len(project_name) == 0:
        project_name = get_project_name_from_input_path(g.INPUT_PATH)
    sly.logger.info(f"Project name: {project_name}")
    return project_name


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
        raise RuntimeError(f"Use 'Import PDF as Images' or 'Auto Import' app to import PDF pages as images")
    elif ext == ".mp4":
        raise RuntimeError(
            f"Use 'Import Videos' app to import video and "
            "'Videos project to images project' app to get frames from it."
            "Alternatively, you can use 'Auto Import' for any data type supported in Supervisely."
        )
    elif ext == ".csv":
        raise RuntimeError(f"Use 'Import Images from CSV' or 'Auto Import' app to import images from CSV files")
    else:
        raise RuntimeError(f"Provided file is not an archive: {filename}. Try using 'Auto Import' application")
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


def normalize_ds_name(name: str) -> str:
    """Normalize a single dataset name component (drops timestamp milliseconds)."""
    if re.match(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3}", name):
        name = f"dataset {name[:-4]}"  # remove milliseconds
    return name


def get_dataset_chain(full_path_file: str, base: str) -> list:
    """Returns the list of dataset name components for an image file relative to `base`.

    Empty list means the image lies directly in the root `base` directory.
    Each component is normalized via `normalize_ds_name`.
    """
    base = (base or "").rstrip("/")
    dir_path = os.path.dirname(full_path_file).rstrip("/")
    rel = os.path.relpath(dir_path, base) if base else dir_path.lstrip("/")
    if rel in (".", "", os.sep):
        return []
    parts = [p for p in pathlib.Path(rel).parts if p not in ("", ".")]
    return [normalize_ds_name(p) for p in parts]


def collapse_top_levels(chains: list) -> int:
    """Number of leading single-folder levels to drop from the top of the tree.

    Stops when: an image lies directly at the current root, the current top level has
    more than one folder, or the single top folder has its own direct images.
    """
    chains = [list(c) for c in chains]
    k = 0
    while True:
        cur = [c[k:] for c in chains]
        if not cur or any(len(c) == 0 for c in cur):
            break
        tops = set(c[0] for c in cur)
        if len(tops) != 1:
            break
        top = next(iter(tops))
        if any(c == [top] for c in cur):  # single top folder has direct images
            break
        k += 1
    return k


def get_datasets_hierarchy(dir_info: list, base: str, into_existing_dataset: bool = False) -> list:
    """Builds an ordered (top-down) list of dataset nodes from the target folder data.

    Each node: {"chain": tuple, "name": str|None, "parent_chain": tuple,
                "img_names": [...], "img_paths": [...], "img_hashes": [...]}.
    Ancestor nodes that only contain subfolders carry empty image lists. A node with an
    empty `chain` represents the root level itself.
    When `into_existing_dataset` is True (import into an existing `DATASET_ID`), that
    dataset is treated as the root: loose root images go directly into it and subfolders
    become datasets nested inside it (no `ds0` wrapper is created).
    """
    records = []  # (chain_list, file_name, file_path, file_hash)
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

        try:
            chain = get_dataset_chain(full_path_file, base)
        except Exception:
            chain = []

        file_path = full_path_file
        if g.api.file.is_on_agent(full_path_file):
            agent_id, file_path = g.api.file.parse_agent_id_and_path(full_path_file)

        records.append([chain, file_name, file_path, file_hash])

    # Collapse the leading single-folder chain (top level only).
    k = collapse_top_levels([r[0] for r in records])
    for r in records:
        r[0] = r[0][k:]
    # If any image lies directly in root after collapse:
    #  - new project: the root level becomes the default dataset (ds0) and sibling
    #    folders nest inside it;
    #  - existing dataset: those images stay at the root (empty chain) so they are
    #    uploaded directly into the existing dataset.
    if not into_existing_dataset and any(len(r[0]) == 0 for r in records):
        for r in records:
            r[0] = [g.DEFAULT_DATASET_NAME] + r[0]

    # Group images by their final chain, deduping names within each node.
    nodes = {}  # chain_tuple -> node dict

    def ensure_node(chain_tuple):
        if chain_tuple not in nodes:
            nodes[chain_tuple] = {
                "chain": chain_tuple,
                "name": chain_tuple[-1] if chain_tuple else None,
                "parent_chain": chain_tuple[:-1] if len(chain_tuple) >= 1 else None,
                "img_names": [],
                "img_paths": [],
                "img_hashes": [],
            }
        return nodes[chain_tuple]

    for chain, file_name, file_path, file_hash in records:
        chain_tuple = tuple(chain)
        # Register all ancestor nodes so structural folders are created as parents.
        for depth in range(1, len(chain_tuple)):
            ensure_node(chain_tuple[:depth])
        node = ensure_node(chain_tuple)

        if file_name in node["img_names"]:
            temp_name = sly.fs.get_file_name(file_name)
            temp_ext = sly.fs.get_file_ext(file_name)
            new_file_name = f"{temp_name}_{sly.rand_str(5)}{temp_ext}"
            sly.logger.warning(
                "Name {!r} already exists in dataset {!r}: renamed to {!r}".format(
                    file_name, "/".join(chain_tuple), new_file_name
                )
            )
            file_name = new_file_name

        node["img_names"].append(file_name)
        node["img_paths"].append(file_path)
        node["img_hashes"].append(file_hash)

    # Order top-down so parents are created before children.
    return [nodes[c] for c in sorted(nodes.keys(), key=len)]


def validate_mimetypes(images_names: list, images_paths: list, is_local: bool = False) -> list:
    """Validate mimetypes for images."""

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


def get_existing_names(api: sly.Api, dataset_id) -> set:
    """Fetch the set of image names already present in a dataset (single API call)."""
    return {image_info.name for image_info in api.image.get_list(dataset_id)}


def check_names_uniqueness(existing_names: set, dataset_id, batch_names) -> list:
    """Resolve name collisions against `existing_names` and register the chosen names.

    `existing_names` is mutated in place so uniqueness holds across batches without
    re-querying the API on every batch.
    """
    for idx, name in enumerate(batch_names):
        new_name = name
        while new_name in existing_names:
            stem = get_file_name(name)
            ext = get_file_ext(name)
            new_name = f"{stem}_{sly.rand_str(5)}{ext}"
        if new_name != name:
            sly.logger.warn(
                f"Name {name} already exists in dataset {dataset_id}: renamed to {new_name}"
            )
        batch_names[idx] = new_name
        existing_names.add(new_name)
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
        return None, None
