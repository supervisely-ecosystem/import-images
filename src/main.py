import supervisely as sly

import functions as f
import globals as g


@g.my_app.callback("import_images_from_team_files")
@sly.timeit
def import_images_from_team_files(
    api: sly.Api, task_id: int, context: dict, state: dict, app_logger
):
    dir_info = api.file.list(g.TEAM_ID, g.INPUT_PATH)
    project_name = f.get_project_name_from_input_path(g.INPUT_PATH)
    datasets_names, datasets_images_map = f.get_datasets_images_map(
        dir_info, project_name
    )

    project = api.project.create(workspace_id=g.WORKSPACE_ID, name=project_name)
    for dataset_name in datasets_names:
        dataset_info = api.dataset.create(project_id=project.id, name=dataset_name)
        images_names = datasets_images_map[dataset_name]["img_names"]
        images_hashes = datasets_images_map[dataset_name]["img_hashes"]

        progress = sly.Progress(
            "Dataset: {!r}".format(dataset_name), len(images_hashes)
        )
        for batch_names, batch_hashes in zip(
            sly.batched(images_names, 10), sly.batched(images_hashes, 10)
        ):
            api.image.upload_hashes(
                dataset_id=dataset_info.id,
                names=batch_names,
                hashes=batch_hashes,
                progress_cb=None,
                metas=None,
            )
            progress.iters_done_report(len(batch_hashes))

    g.my_app.stop()


def main():
    sly.logger.info(
        "Script arguments",
        extra={
            "context.teamId": g.TEAM_ID,
            "context.workspaceId": g.WORKSPACE_ID,
            "modal.state.slyFolder": g.INPUT_PATH,
        },
    )

    data = {}
    state = {}

    g.my_app.run(
        state=state,
        data=data,
        initial_events=[{"state": state, "command": "import_images_from_team_files"}],
    )


if __name__ == "__main__":
    sly.main_wrapper("main", main)
