import os
from dotenv import load_dotenv
import supervisely as sly

# for convenient debug, has no effect in production
if sly.is_development():
    load_dotenv("local.env")
    load_dotenv(os.path.expanduser("~/supervisely.env"))
    sly.fs.clean_dir(sly.app.get_data_dir())

# import functions as f
# import globals as g
import src.globals as g
import src.functions as f


from supervisely.app.widgets import Container, Card, Input

card = Card(
    "1️⃣ Input project",
    "Select videos in current project",
    collapsable=True,
    content=Input(),
)

layout = Container(
    widgets=[card],
    direction="vertical",
    gap=15,
)

app = sly.Application(layout=layout)


class MyImport(sly.app.Import):
    def is_path_required(self) -> bool:
        return False

    def process(self, context: sly.app.Import.Context):
        dir_info = g.api.file.list(context.team_id, g.INPUT_PATH)
        if len(dir_info) == 0:
            raise Exception(f"There are no files in selected directory: '{g.INPUT_PATH}'")

        if context.project_id is None:
            project_name = (
                f.get_project_name_from_input_path(g.INPUT_PATH)
                if len(g.OUTPUT_PROJECT_NAME) == 0
                else g.OUTPUT_PROJECT_NAME
            )
            project = g.api.project.create(
                workspace_id=context.workspace_id, name=project_name, change_name_if_conflict=True
            )
        else:
            project = g.api.project.get_info_by_id(context.project_id)

        if g.NEED_DOWNLOAD:
            sly.logger.info(f"Data will be downloaded: {g.INPUT_PATH}")
            f.download_project(g.api, g.INPUT_PATH, context.team_id)

        dataset_info = None
        if context.dataset_id is not None:
            dataset_info = g.api.dataset.get_info_by_id(context.dataset_id)
            datasets_names, datasets_images_map = f.get_datasets_images_map(
                dir_info, dataset_info.name
            )
        else:
            datasets_names, datasets_images_map = f.get_datasets_images_map(dir_info, None)

        for dataset_name in datasets_names:
            if context.dataset_id is None:
                dataset_info = g.api.dataset.create(
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

            progress = sly.Progress(
                f"Uploading images to dataset {dataset_name}", total_cnt=len(images_names)
            )
            for batch_names, batch_paths, batch_hashes in zip(
                sly.batched(seq=images_names, batch_size=10),
                sly.batched(seq=images_paths, batch_size=10),
                sly.batched(seq=images_hashes, batch_size=10),
            ):
                if g.NEED_DOWNLOAD:
                    res_batch_names, res_batch_paths = f.normalize_exif_and_remove_alpha_channel(
                        names=batch_names, paths=batch_paths
                    )

                    res_batch_names = f.validate_mimetypes(
                        res_batch_names, res_batch_paths, context.team_id
                    )

                    g.api.image.upload_paths(
                        dataset_id=dataset_info.id,
                        names=res_batch_names,
                        paths=res_batch_paths,
                    )
                else:
                    try:

                        batch_names = f.validate_mimetypes(
                            batch_names, batch_paths, context.team_id
                        )
                        g.api.image.upload_hashes(
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
            g.api.file.remove(team_id=context.team_id, path=g.INPUT_PATH)
            source_dir_name = g.INPUT_PATH.lstrip("/").rstrip("/")
            sly.logger.info(msg=f"Source directory: '{source_dir_name}' was successfully removed.")


# app = MyImport()
# app.run()
