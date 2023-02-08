import os
from copy import deepcopy
from distutils.util import strtobool
from os import environ, getenv
from os.path import basename

from dotenv import load_dotenv

import supervisely as sly
from supervisely.app.widgets import SlyTqdm
from supervisely.io.fs import get_file_name_with_ext, remove_dir

# for convenient debug, has no effect in production
if sly.is_development():
    load_dotenv("local.env")
    load_dotenv(os.path.expanduser("~/supervisely.env"))

import functions as f

progress_bar = SlyTqdm()
DEFAULT_DATASET_NAME = "ds0"
PROJECT_NAME = environ.get("modal.state.projectName", None)
NORMALIZE_EXIF = bool(strtobool(os.getenv("modal.state.normalizeExif", "False")))
REMOVE_ALPHA_CHANNEL = bool(strtobool(os.getenv("modal.state.removeAlphaChannel", "False")))
NEED_DOWNLOAD = NORMALIZE_EXIF or REMOVE_ALPHA_CHANNEL
REMOVE_SOURCE = bool(strtobool(getenv("modal.state.removeSource")))


class MyImport(sly.app.Import):
    def process(self, context: sly.app.Import.Context):
        api = sly.Api.from_env()

        if context.project_id is None:
            project_name = basename(context.path)
            project = api.project.create(
                workspace_id=context.workspace_id,
                name=project_name,
                change_name_if_conflict=True,
            )
        else:
            project = api.project.get_info_by_id(context.project_id)
            project_name = PROJECT_NAME or project.name

        ds_files_map = f.get_ds_files_map(context.path, DEFAULT_DATASET_NAME)
        for ds_name in ds_files_map:
            if context.dataset_id is None:
                dataset_info = api.dataset.create(
                    project_id=project.id, name=ds_name, change_name_if_conflict=True
                )
            else:
                dataset_info = api.dataset.get_info_by_id(id=context.dataset_id)

            images_names = [
                get_file_name_with_ext(file_path) for file_path in ds_files_map[ds_name]
            ]
            images_paths = list(ds_files_map[ds_name])

            for batch_names, batch_paths in progress_bar(
                zip(
                    sly.batched(seq=images_names, batch_size=10),
                    sly.batched(seq=images_paths, batch_size=10),
                ),
                total=len(images_paths),
                message="Dataset: {!r}".format(dataset_info.name),
            ):
                res_batch_paths = deepcopy(batch_paths)
                if NORMALIZE_EXIF or REMOVE_ALPHA_CHANNEL:
                    res_batch_names, res_batch_paths = f.normalize_exif_and_remove_alpha_channel(
                        names=batch_names, paths=batch_paths
                    )
                res_batch_names = f.validate_mimetypes(
                    api, batch_names, batch_paths, context.team_id
                )
                try:
                    api.image.upload_paths(
                        dataset_id=dataset_info.id,
                        names=res_batch_names,
                        paths=res_batch_paths,
                    )
                except Exception as ex:
                    sly.logger.warn(ex)

        remove_dir(context.path)
        return context.project_id


app = MyImport()
app.run()
