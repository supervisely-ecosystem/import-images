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

from supervisely.project.project_type import ProjectType


from supervisely.app.widgets import (
    Container,
    Card,
    Input,
    Select,
    Checkbox,
    Text,
    FileStorageUpload,
    RadioGroup,
    OneOf,
    SelectProject,
    SelectDataset,
    Button,
)

# FOLDER ===========================================================================================
team_id = int(os.environ["context.teamId"])
INPUT_PATH = "/import_images"
file_upload = FileStorageUpload(team_id=team_id, path=INPUT_PATH, change_name_if_conflict=True)
team_files = Text(text="Team Files here")  # TODO check it
items = [
    RadioGroup.Item(value="Drag & drop", content=file_upload),
    RadioGroup.Item(value="Team files", content=team_files),
]
radio_group = RadioGroup(items=items)
one_of = OneOf(radio_group)
widgets = Container(widgets=[radio_group, one_of])
card_upload_or_tf = Card(content=widgets)

input_project_name = Input(placeholder="Enter Project Name")
card_project_name = Card(
    title="Result Project Name",
    description="Enter project name manually (optional) or keep empty to generate it automatically",
    content=input_project_name,
)


folder = Container(widgets=[card_upload_or_tf, card_project_name])

select_project = SelectProject(allowed_types=[ProjectType.IMAGES], compact=True)
project = Container(widgets=[select_project, file_upload])

select_dataset = SelectDataset()
dataset = Container(widgets=[select_dataset, file_upload])

selector_items = [
    Select.Item(value="Folder", label="Folder", content=folder),
    Select.Item(value="Images project", label="Images project", content=project),
    Select.Item(value="Images dataset", label="Images dataset", content=dataset),
]


select = Select(items=selector_items)
one_of = OneOf(conditional_widget=select)
card1 = Card(
    title="One of",
    content=Container(widgets=[select, one_of]),
)


# ====================================================================================================================
exif = Checkbox(content="Normalize exif")
exif_text = Text(
    text="If images you import has exif rotation or they look rotated in labeling interfaces please enable normalize exif",
    status="info",
)

exif_data = Container(
    widgets=[exif, exif_text],
    direction="vertical",
)

card_exif = Card(
    content=exif_data,
)

alpha_channel = Checkbox(content="Remove alpha channel")
alpha_channel_text = Text(
    text="If your images have alpha channel, enable remove alpha channel",
    status="info",
)

alpha_channel_data = Container(
    widgets=[alpha_channel, alpha_channel_text],
    direction="vertical",
)

card_alpha_channel = Card(
    content=alpha_channel_data,
)

temporary_files = Checkbox(content="Remove temporary files after successful import", checked=True)
temporary_files_text = Text(
    text="Removes source directory from Team Files after successful import",
    status="info",
)

temporary_files_data = Container(
    widgets=[
        temporary_files,
        temporary_files_text,
    ],
    direction="vertical",
)

card_temporary_files = Card(
    content=temporary_files_data,
)
# ===================================================================================================
run_button = Button(text="Run")

# ===================================================================================================
layout = Container(
    widgets=[card1, card_exif, card_alpha_channel, card_temporary_files, run_button],
    direction="vertical",
    gap=15,
)

app = sly.Application(layout=layout)


class MyImport(sly.app.Import):
    def is_path_required(self) -> bool:
        return False

    def process(self, context: sly.app.Import.Context):
        try:
            paths = file_upload.get_uploaded_paths()
            INPUT_PATH = file_upload.path
        except TypeError:
            raise TypeError("Grag & drop folders/files for uploading")

        project_name = input_project_name.get_value()
        project_id = select_project.get_selected_id()

        dataset_id = select_dataset.get_selected_id()
        if dataset_id == [None]:
            dataset_id = None
        if dataset_id is not None:
            dataset_info = g.api.dataset.get_info_by_id(dataset_id)
            project_id = dataset_info.project_id

        if project_id is None:
            if project_name == "":
                project_name = f.get_project_name_from_input_path(paths[0])
            project = g.api.project.create(
                workspace_id=context.workspace_id, name=project_name, change_name_if_conflict=True
            )
        else:
            project = g.api.project.get_info_by_id(project_id)

        g.IS_ON_AGENT = g.api.file.is_on_agent(paths[0])  # TODO check it
        g.NORMALIZE_EXIF = exif.is_checked()
        g.REMOVE_ALPHA_CHANNEL = alpha_channel.is_checked()
        g.REMOVE_SOURCE = temporary_files.is_checked()
        g.NEED_DOWNLOAD = g.NORMALIZE_EXIF or g.REMOVE_ALPHA_CHANNEL or g.IS_ON_AGENT

        dir_info = g.api.file.list(context.team_id, INPUT_PATH)

        if g.NEED_DOWNLOAD:
            sly.logger.info(f"Data will be downloaded: {INPUT_PATH}")
            f.download_project(g.api, INPUT_PATH, context.team_id)

        if dataset_id is not None:
            datasets_names, datasets_images_map = f.get_datasets_images_map(
                dir_info, dataset_info.name
            )
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
            g.api.file.remove(team_id=context.team_id, path=INPUT_PATH)
            source_dir_name = INPUT_PATH.lstrip("/").rstrip("/")
            sly.logger.info(msg=f"Source directory: '{source_dir_name}' was successfully removed.")


@run_button.click
def run_app():
    app = MyImport()
    app.run()
