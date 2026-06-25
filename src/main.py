import os

import supervisely as sly
from dotenv import load_dotenv

if sly.is_development():
    load_dotenv("local.env")
    load_dotenv(os.path.expanduser("~/supervisely.env"))
    sly.fs.clean_dir(sly.app.get_data_dir())

import functions as f
import globals as g


@sly.timeit
def import_images(api: sly.Api, task_id: int):
    dir_info = api.file.list(g.TEAM_ID, g.INPUT_PATH)
    if len(dir_info) == 0:
        raise Exception(f"There are no files in selected directory: '{g.INPUT_PATH}'")

    sly.logger.debug(f"Number of files in selected directory: {len(dir_info)}")

    if len(dir_info) == 1:
        sly.logger.debug(
            f"There is only one file in directory {g.INPUT_PATH}. "
            "Will check if it is an archive or an image."
        )
        file_name = dir_info[0].get("name")
        file_ext = sly.fs.get_file_ext(file_name)
        if file_ext.lower() in sly.image.SUPPORTED_IMG_EXTS:
            sly.logger.debug(f"File {file_name} is an image.")
        elif file_ext.lower() in g.EXT_TO_CONVERT:
            sly.logger.debug(
                f"File {file_name} is an image, but it is not supported. "
                "Will try to convert it to jpeg."
            )
            g.NEED_DOWNLOAD = True
        else:
            sly.logger.debug(
                f"File {file_name} is not an image, will try to handle it as an archive."
            )
            dir_info = f.unpack_archive_on_team_files(api, dir_info[0].get("path"))
    elif len(dir_info) > 1:
        for file_info in dir_info:
            meta = file_info.get("meta")
            if meta is None or meta.get("ext") is None:
                continue
            ext = "." + meta.get("ext")
            if ext and ext in g.EXT_TO_CONVERT:
                sly.logger.debug(
                    f"Found file with unsupported extension. " "Will try to convert it to jpeg."
                )
                g.NEED_DOWNLOAD = True
                break

    project = api.project.get_info_by_id(g.PROJECT_ID) if g.PROJECT_ID else None
    if project is None:
        project_name = f.get_project_name()
        project = api.project.create(
            workspace_id=g.WORKSPACE_ID, name=project_name, change_name_if_conflict=True
        )

    into_existing_dataset = g.DATASET_ID is not None
    existing_dataset_info = None
    nodes = f.get_datasets_hierarchy(dir_info, g.CHECKED_INPUT_PATH, into_existing_dataset)

    sly.logger.debug(f"Datasets hierarchy: {[node['chain'] for node in nodes]}")

    if g.NEED_DOWNLOAD:
        sly.logger.info(f"Data will be downloaded: {g.CHECKED_INPUT_PATH}")
        f.download_project(api, g.CHECKED_INPUT_PATH)

    # The root level (empty chain) maps to the target: a newly created dataset is nested
    # under the project, while an existing DATASET_ID becomes the root for nested datasets.
    created_ids = {}  # chain_tuple -> dataset_id
    if into_existing_dataset:
        existing_dataset_info = api.dataset.get_info_by_id(g.DATASET_ID)
        created_ids[()] = existing_dataset_info.id

    for node in nodes:
        dataset_name = node["name"]
        if not node["chain"] and into_existing_dataset:
            # Loose root images are uploaded directly into the existing dataset.
            dataset_info = existing_dataset_info
        else:
            parent_chain = node["parent_chain"]
            parent_id = created_ids.get(parent_chain) if parent_chain is not None else None
            dataset_info = api.dataset.create(
                project_id=project.id,
                name=dataset_name,
                parent_id=parent_id,
                change_name_if_conflict=True,
            )
            created_ids[node["chain"]] = dataset_info.id

        images_names = node["img_names"]
        images_hashes = node["img_hashes"]
        images_paths = node["img_paths"]

        if g.NEED_DOWNLOAD:
            images_paths = [
                os.path.join(g.STORAGE_DIR, image_path.lstrip("/")) for image_path in images_paths
            ]

        existing_names = f.get_existing_names(api, dataset_info.id)
        progress = sly.Progress(
            f"Uploading images to dataset {dataset_name}", total_cnt=len(images_names)
        )
        for batch_names, batch_paths, batch_hashes in zip(
            sly.batched(seq=images_names, batch_size=10),
            sly.batched(seq=images_paths, batch_size=10),
            sly.batched(seq=images_hashes, batch_size=10),
        ):
            if g.NEED_DOWNLOAD:
                try:
                    res_batch_names, res_batch_paths = f.normalize_exif_and_remove_alpha_channel(
                        names=batch_names, paths=batch_paths
                    )
                    res_batch_names = f.validate_mimetypes(res_batch_names, res_batch_paths)
                    res_batch_names = f.check_names_uniqueness(
                        existing_names, dataset_info.id, res_batch_names
                    )
                    api.image.upload_paths(
                        dataset_id=dataset_info.id,
                        names=res_batch_names,
                        paths=res_batch_paths,
                    )
                except Exception as e:
                    sly.logger.warn(msg=e)
            else:
                try:
                    batch_names = f.validate_mimetypes(batch_names, batch_paths)
                    batch_names = f.check_names_uniqueness(
                        existing_names, dataset_info.id, batch_names
                    )
                    api.image.upload_hashes(
                        dataset_id=dataset_info.id,
                        names=batch_names,
                        hashes=batch_hashes,
                    )
                except Exception as e:
                    sly.logger.warn(msg=e)

            progress.iters_done_report(len(batch_names))

    if g.NEED_DOWNLOAD:
        sly.fs.remove_dir(dir_=g.STORAGE_DIR)
    if g.REMOVE_SOURCE and not g.IS_ON_AGENT:
        api.file.remove(team_id=g.TEAM_ID, path=g.INPUT_PATH)
        source_dir_name = g.INPUT_PATH.lstrip("/").rstrip("/")
        sly.logger.info(msg=f"Source directory: '{source_dir_name}' was successfully removed.")
        if g.CHECKED_INPUT_PATH != g.INPUT_PATH:
            api.file.remove(team_id=g.TEAM_ID, path=g.CHECKED_INPUT_PATH)
            temp_dir_name = g.CHECKED_INPUT_PATH.lstrip("/").rstrip("/")
            sly.logger.info(msg=f"Temp directory: '{temp_dir_name}' was successfully removed.")

    api.task.set_output_project(task_id=task_id, project_id=project.id, project_name=project.name)
    # -------------------------------------- Add Workflow Output ------------------------------------- #
    g.workflow.add_output(project.id)
    # ----------------------------------------------- - ---------------------------------------------- #


@sly.handle_exceptions(has_ui=False)
def main():
    sly.logger.info(
        "Script arguments",
        extra={
            "context.teamId": g.TEAM_ID,
            "context.workspaceId": g.WORKSPACE_ID,
            "modal.state.slyFolder": g.INPUT_PATH,
        },
    )

    try:
        import_images(g.api, g.TASK_ID)
        sly.app.fastapi.shutdown()
    finally:
        if not sly.is_development():
            sly.logger.info(f"Remove data directory: {g.STORAGE_DIR}")
            sly.fs.remove_dir(g.STORAGE_DIR)


if __name__ == "__main__":
    sly.main_wrapper("main", main)
