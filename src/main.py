import os
from dotenv import load_dotenv
import supervisely as sly

# for convenient debug, has no effect in production
# if sly.is_development():
load_dotenv("local.env")
load_dotenv(os.path.expanduser("~/supervisely.env"))
sly.fs.clean_dir(sly.app.get_data_dir())


import src.globals as g
import src.functions as f

from supervisely.app.widgets import Container, Checkbox, Text


def initiate_current_widgets():
    exif_main_text = Text(text="Normalize exif")
    exif_add_text = Text(
        text="If images you import has exif rotation or they look rotated in labeling interfaces please enable normalize exif"
    )
    exif_checkboxes_data = Container(widgets=[exif_main_text, exif_add_text], direction="vertical")
    global exif
    exif = Checkbox(content=exif_checkboxes_data)

    alpha_channel_main_text = Text(text="Remove alpha channel")
    alpha_channel_add_text = Text(
        text="If your images have alpha channel, enable remove alpha channel"
    )
    alpha_channel_checkboxes_data = Container(
        widgets=[alpha_channel_main_text, alpha_channel_add_text], direction="vertical"
    )
    global alpha_channel
    alpha_channel = Checkbox(content=alpha_channel_checkboxes_data)

    return [exif, alpha_channel]


class MyImport(sly.app.Import):
    def is_path_required(self) -> bool:
        return False

    def process(self):

        if self._folder is None:
            current_tab = self.radio_tabs.get_active_tab()
            if current_tab == self.drag_drop_title:
                try:
                    g.INPUT_PATH = self.file_upload.path

                except TypeError:
                    raise TypeError("Grag & drop folders/files for uploading")
            else:
                g.INPUT_PATH = self.team_files.get_selected_paths[0]  # TODO check it

        else:
            g.INPUT_PATH = self._folder

        if self._project_id is None:
            project_name = self.destination_project.get_project_name()
            project_id = self.destination_project.get_selected_project_id()

            dataset_name = self.destination_project.get_dataset_name()
            dataset_id = self.destination_project.get_selected_dataset_id()

            if project_id is None:
                if project_name == "":
                    project_name = g.DEFAULT_PROJECT_NAME
                project = g.api.project.create(
                    workspace_id=self._workspace_id,
                    name=project_name,
                    change_name_if_conflict=True,
                )
            else:
                project = g.api.project.get_info_by_id(project_id)

        else:
            project = g.api.project.get_info_by_id(self._project_id)
            if self._dataset_id is None:
                dataset_id = None
                dataset_name = None
            else:
                dataset_id = self._dataset_id

        g.IS_ON_AGENT = g.api.file.is_on_agent(g.INPUT_PATH)  # TODO check it
        g.NORMALIZE_EXIF = exif.is_checked()
        g.REMOVE_ALPHA_CHANNEL = alpha_channel.is_checked()
        g.REMOVE_SOURCE = self.temporary_files.is_checked()
        g.NEED_DOWNLOAD = g.NORMALIZE_EXIF or g.REMOVE_ALPHA_CHANNEL or g.IS_ON_AGENT

        dir_info = g.api.file.list(self._team_id, g.INPUT_PATH)

        if g.NEED_DOWNLOAD:
            sly.logger.info(f"Data will be downloaded: {g.INPUT_PATH}")
            f.download_project(g.api, g.INPUT_PATH, self._team_id)

        if dataset_id is not None:
            dataset_info = g.api.dataset.get_info_by_id(dataset_id)
            datasets_names, datasets_images_map = f.get_datasets_images_map(
                dir_info, dataset_info.name
            )

        elif dataset_name is not None:
            if len(dataset_name) == 0:
                dataset_name = g.DEFAULT_DATASET_NAME
            datasets_names, datasets_images_map = f.get_datasets_images_map(dir_info, dataset_name)

        else:
            datasets_names, datasets_images_map = f.get_datasets_images_map(dir_info, None)

        for dataset_name in datasets_names:
            if dataset_id is None:
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
                        res_batch_names, res_batch_paths, self._team_id
                    )

                    g.api.image.upload_paths(
                        dataset_id=dataset_info.id,
                        names=res_batch_names,
                        paths=res_batch_paths,
                    )
                else:
                    try:

                        batch_names = f.validate_mimetypes(batch_names, batch_paths, self._team_id)
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
            g.api.file.remove(team_id=self._team_id, path=g.INPUT_PATH)
            source_dir_name = g.INPUT_PATH.lstrip("/").rstrip("/")
            sly.logger.info(msg=f"Source directory: '{source_dir_name}' was successfully removed.")

        self.run_button.disable()
        sly.app.show_dialog(
            title="Import done",
            description="Import successfully completed",
            status="success",
        )


import_images = MyImport()
main_widgets_init = import_images.initiate_import_widgets(
    input_path=g.INPUT_PATH, current_widgets=initiate_current_widgets()
)
app = import_images.app
run_button = import_images.run_button


@run_button.click
def run_app():
    import_images.process()
