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

    into_existing_dataset = g.DATASET_ID is not None
    existing_dataset_info = None
    nodes = f.get_datasets_hierarchy(dir_info, g.CHECKED_INPUT_PATH, into_existing_dataset)

    sly.logger.debug(f"Datasets hierarchy: {[node['chain'] for node in nodes]}")

    # Count what we plan to import vs what is actually uploaded, so the source is only
    # removed from Team Files when every image made it into the project.
    planned_cnt = sum(len(node["img_names"]) for node in nodes)
    uploaded_cnt = 0

    if planned_cnt == 0:
        # Nothing importable: fail before creating a project, so no empty project is left
        # behind. The source is kept as is.
        remove_temp_copy(api)
        supported = ", ".join(dict.fromkeys(ext.lower() for ext in g.SUPPORTED_EXTS))
        raise RuntimeError(
            f"No supported images found in '{g.INPUT_PATH}' "
            f"({len(g.SKIPPED_FILES)} files skipped as unsupported). "
            f"Supported extensions: {supported}. "
            "Nothing was imported, no project was created and the source in Team Files was kept."
        )

    project = api.project.get_info_by_id(g.PROJECT_ID) if g.PROJECT_ID else None
    project_created = False
    if project is None:
        project_name = f.get_project_name()
        project = api.project.create(
            workspace_id=g.WORKSPACE_ID, name=project_name, change_name_if_conflict=True
        )
        project_created = True

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
                    uploaded = api.image.upload_paths(
                        dataset_id=dataset_info.id,
                        names=res_batch_names,
                        paths=res_batch_paths,
                    )
                    uploaded_cnt += len(uploaded)
                except Exception as e:
                    sly.logger.warn(msg=e)
            else:
                try:
                    batch_names = f.validate_mimetypes(batch_names, batch_paths)
                    batch_names = f.check_names_uniqueness(
                        existing_names, dataset_info.id, batch_names
                    )
                    uploaded = api.image.upload_hashes(
                        dataset_id=dataset_info.id,
                        names=batch_names,
                        hashes=batch_hashes,
                    )
                    uploaded_cnt += len(uploaded)
                except Exception as e:
                    sly.logger.warn(msg=e)

            progress.iters_done_report(len(batch_names))

    if g.NEED_DOWNLOAD:
        sly.fs.remove_dir(dir_=g.STORAGE_DIR)

    failed_cnt = planned_cnt - uploaded_cnt
    skipped_cnt = len(g.SKIPPED_FILES)
    sly.logger.info(
        f"Import summary: {uploaded_cnt} of {planned_cnt} images imported, "
        f"{failed_cnt} failed, {skipped_cnt} files skipped as unsupported."
    )
    import_complete = planned_cnt > 0 and failed_cnt == 0 and skipped_cnt == 0

    source_kept = False
    if g.REMOVE_SOURCE and not g.IS_ON_AGENT:
        source_dir_name = g.INPUT_PATH.lstrip("/").rstrip("/")
        if import_complete:
            api.file.remove(team_id=g.TEAM_ID, path=g.INPUT_PATH)
            sly.logger.info(msg=f"Source directory: '{source_dir_name}' was successfully removed.")
        else:
            source_kept = True
            reasons = []
            if failed_cnt > 0:
                reasons.append(f"{failed_cnt} of {planned_cnt} images failed to import")
            if skipped_cnt > 0:
                reasons.append(f"{skipped_cnt} files were skipped as unsupported")
            if planned_cnt == 0:
                reasons.append("no images were found to import")
            sly.logger.warning(
                f"Source directory: '{source_dir_name}' was NOT removed from Team Files "
                f"because the import was not complete ({'; '.join(reasons)}). "
                "Check the warnings above; the source is kept so no data is lost.",
                extra={"skipped_files": g.SKIPPED_FILES[:100]},
            )
    remove_temp_copy(api)

    # Nothing made it into a project this run created: remove it rather than leave an
    # empty project behind (only if the server confirms it is still empty).
    project_removed = (
        uploaded_cnt == 0 and project_created and f.remove_project_if_empty(api, project)
    )

    if not project_removed:
        api.task.set_output_project(
            task_id=task_id, project_id=project.id, project_name=project.name
        )
        # ------------------------------------ Add Workflow Output ----------------------------------- #
        g.workflow.add_output(project.id)
        # --------------------------------------------- - -------------------------------------------- #

    if failed_cnt > 0:
        # Do not report success when images were lost on the way; what was imported stays
        # in the project.
        msg = f"{failed_cnt} of {planned_cnt} images failed to import (see warnings above)."
        if project_removed:
            msg += (
                f" Nothing was imported, so the empty project '{project.name}' "
                "created by this run was removed."
            )
        else:
            msg += (
                f" {uploaded_cnt} images were imported into project '{project.name}' "
                f"(id: {project.id})."
            )
        if source_kept:
            msg += " The source in Team Files was kept."
        raise RuntimeError(msg)


def remove_temp_copy(api: sly.Api):
    """Remove the app-created /import-images/temp/ copy of an unpacked archive.

    It is a copy made by this app, so it is safe to remove even when the original source
    is kept. Done only when remove_source is on, as before.
    """
    if not g.REMOVE_SOURCE or g.IS_ON_AGENT or g.CHECKED_INPUT_PATH == g.INPUT_PATH:
        return
    api.file.remove(team_id=g.TEAM_ID, path=g.CHECKED_INPUT_PATH)
    temp_dir_name = g.CHECKED_INPUT_PATH.lstrip("/").rstrip("/")
    sly.logger.info(msg=f"Temp directory: '{temp_dir_name}' was successfully removed.")


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
