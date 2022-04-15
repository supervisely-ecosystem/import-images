import os

import supervisely as sly
from supervisely.app.widgets import SlyTqdm

import functions as f
import globals as g

progress_bar = SlyTqdm()


@sly.timeit
def import_images(api: sly.Api):
    dir_info = api.file.list(g.TEAM_ID, g.INPUT_PATH)
    project_name = f.get_project_name_from_input_path(g.INPUT_PATH)
    datasets_names, datasets_images_map = f.get_datasets_images_map(dir_info)

    project = api.project.create(
        workspace_id=g.WORKSPACE_ID, name=project_name, change_name_if_conflict=True
    )
    for dataset_name in datasets_names:
        dataset_info = api.dataset.create(
            project_id=project.id, name=dataset_name, change_name_if_conflict=True
        )
        images_names = datasets_images_map[dataset_name]["img_names"]
        images_paths = datasets_images_map[dataset_name]["img_paths"]
        images_hashes = datasets_images_map[dataset_name]["img_hashes"]

        for batch_names, batch_paths, batch_hashes in progress_bar(
                zip(sly.batched(images_names, 10), sly.batched(images_paths, 10), sly.batched(images_hashes, 10)),
                total=len(images_hashes) // 10,
                message="Dataset: {!r}".format(dataset_name),
        ):
            if g.NEED_DOWNLOAD:
                res_batch_names, res_batch_paths = f.normalize_exif_and_remove_alpha_channel(api, batch_names, batch_paths, batch_hashes)
                api.image.upload_paths(dataset_info.id, res_batch_names, res_batch_paths)
                for path in res_batch_paths:
                    sly.fs.silent_remove(path)
            else:
                try:
                    api.image.upload_hashes(
                        dataset_id=dataset_info.id, names=batch_names, hashes=batch_hashes
                    )
                except Exception as e:
                    sly.logger.warn(e)


if __name__ == "__main__":
    sly.logger.info(
        "Script arguments",
        extra={
            "context.teamId": g.TEAM_ID,
            "context.workspaceId": g.WORKSPACE_ID,
            "modal.state.slyFolder": g.INPUT_PATH,
        },
    )

    import_images(g.api)
    try:
        sly.app.fastapi.shutdown()
    except KeyboardInterrupt:
        sly.logger.info("Application shutdown successfully")
