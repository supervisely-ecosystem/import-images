import os

import supervisely as sly
from supervisely.app.widgets import SlyTqdm

import functions as f
import globals as g

progress_bar = SlyTqdm()


@sly.timeit
def import_images(api: sly.Api, task_id: int):
    dir_info = api.file.list(g.TEAM_ID, g.INPUT_PATH)
    if len(dir_info) == 0:
        raise Exception(f"There are no files in selected directory: '{g.INPUT_PATH}'")

    project_name = f.get_project_name_from_input_path(g.INPUT_PATH) if len(g.OUTPUT_PROJECT_NAME) == 0 else g.OUTPUT_PROJECT_NAME

    if g.NEED_DOWNLOAD:
        f.download_project(api, g.INPUT_PATH)

    datasets_names, datasets_images_map = f.get_datasets_images_map(dir_info)

    project = api.project.create(
        workspace_id=g.WORKSPACE_ID, name=project_name, change_name_if_conflict=True
    )
    for dataset_name in datasets_names:
        dataset_info = api.dataset.create(
            project_id=project.id, name=dataset_name, change_name_if_conflict=True
        )

        images_names = datasets_images_map[dataset_name]["img_names"]
        images_hashes = datasets_images_map[dataset_name]["img_hashes"]
        images_paths = datasets_images_map[dataset_name]["img_paths"]
        if g.NEED_DOWNLOAD:
            images_paths = [
                os.path.join(g.STORAGE_DIR, image_path.lstrip("/"))
                for image_path in images_paths
            ]
        for batch_names, batch_paths, batch_hashes in progress_bar(
            zip(
                sly.batched(seq=images_names, batch_size=10),
                sly.batched(seq=images_paths, batch_size=10),
                sly.batched(seq=images_hashes, batch_size=10),
            ),
            total=len(images_hashes) // 10,
            message="Dataset: {!r}".format(dataset_name),
        ):
            if g.NEED_DOWNLOAD:
                res_batch_names, res_batch_paths = f.normalize_exif_and_remove_alpha_channel(
                    names=batch_names, paths=batch_paths
                )
                api.image.upload_paths(
                    dataset_id=dataset_info.id,
                    names=res_batch_names,
                    paths=res_batch_paths,
                )
            else:
                if g.CONVERT_TIFF:
                    tiff_names, tiff_paths, batch_names, batch_hashes = f.process_tiff_images(
                        api=api,
                        batch_names=batch_names,
                        batch_paths=batch_paths,
                        batch_hashes=batch_hashes,
                    )
                    if len(tiff_names) > 0:
                        api.image.upload_paths(
                            dataset_id=dataset_info.id,
                            names=tiff_names,
                            paths=tiff_paths,
                        )
                try:
                    api.image.upload_hashes(
                        dataset_id=dataset_info.id,
                        names=batch_names,
                        hashes=batch_hashes,
                    )
                except Exception as e:
                    sly.logger.warn(msg=e)

    if g.NEED_DOWNLOAD or g.CONVERT_TIFF:
        sly.fs.remove_dir(dir_=g.STORAGE_DIR)
    if g.REMOVE_SOURCE:
        api.file.remove(team_id=g.TEAM_ID, path=g.INPUT_PATH)
        source_dir_name = g.INPUT_PATH.lstrip("/").rstrip("/")
        sly.logger.info(
            msg=f"Source directory: '{source_dir_name}' was successfully removed."
        )

    api.task.set_output_project(
        task_id=task_id, project_id=project.id, project_name=project.name
    )


if __name__ == "__main__":
    sly.logger.info(
        "Script arguments",
        extra={
            "context.teamId": g.TEAM_ID,
            "context.workspaceId": g.WORKSPACE_ID,
            "modal.state.slyFolder": g.INPUT_PATH,
        },
    )

    import_images(g.api, g.TASK_ID)
    try:
        sly.app.fastapi.shutdown()
    except KeyboardInterrupt:
        sly.logger.info("Application shutdown successfully")
