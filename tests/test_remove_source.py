"""`remove_source` must only delete the Team Files source after a complete import.

Before the fix every upload batch was wrapped in `except Exception: logger.warn` and
`api.file.remove(team_id, INPUT_PATH)` ran unconditionally, so a partial import deleted
the only copy of the images that did not make it into the project.
"""
JPEG = "image/jpeg"


def _import(main, g, api):
    """Run the import; return the exception the task would end with (None on success)."""
    try:
        main.import_images(api, g.TASK_ID)
    except Exception as e:  # noqa: BLE001 - the task's final error is what we check
        return e
    return None


def _images(n, folder="/images/"):
    return {f"{folder}img_{i:02d}.jpg": JPEG for i in range(n)}


def test_full_success_removes_source(run_app):
    main, g, api = run_app(_images(12))

    assert _import(main, g, api) is None

    assert len(api.image.uploaded) == 12
    assert api.file.removed == ["/images/"]
    assert api.output_project == 100


def test_pdf_disguised_as_jpg_keeps_source_and_fails_task(run_app):
    # validate_mimetypes raises for the whole 10-image batch -> 10 of 12 images are lost
    files = _images(12)
    files["/images/img_03.jpg"] = "application/pdf"
    main, g, api = run_app(files)

    err = _import(main, g, api)

    assert api.file.removed == []  # source kept: it holds the only copy of 10 images
    assert len(api.image.uploaded) == 2  # what was imported stays in the project
    assert api.output_project == 100
    assert api.project.removed == []
    assert err is not None and "10 of 12 images failed" in str(err)  # task not "success"


def test_server_rejection_keeps_source_and_fails_task(run_app):
    main, g, api = run_app(_images(12), reject_names={"img_11.jpg"})

    err = _import(main, g, api)

    assert api.file.removed == []
    assert len(api.image.uploaded) == 10
    assert api.project.removed == []
    assert err is not None and "2 of 12 images failed" in str(err)


def test_unsupported_files_keep_source(run_app):
    files = _images(3)
    files["/images/labels.txt"] = "text/plain"
    main, g, api = run_app(files)

    assert _import(main, g, api) is None  # skipping non-images is not an error

    assert len(api.image.uploaded) == 3
    assert api.file.removed == []


def test_remove_source_off_never_removes(run_app):
    main, g, api = run_app(_images(2), remove_source=False)

    assert _import(main, g, api) is None

    assert api.file.removed == []


# --- nothing imported: the task must fail and must not leave an empty project ---------


def test_no_supported_images_fails_without_creating_project(run_app):
    # the folder holds files, but none of them is a supported image
    files = {"/images/report.pdf": "application/pdf", "/images/notes.docx": "application/msword"}
    main, g, api = run_app(files)

    err = _import(main, g, api)

    assert err is not None and "No supported images found in '/images/'" in str(err)
    assert "Supported extensions:" in str(err) and ".jpg" in str(err)
    assert api.project.created == []  # checked before creating anything
    assert api.output_project is None
    assert api.file.removed == []  # source kept


def test_all_images_rejected_removes_the_empty_project_it_created(run_app):
    # ".jpg" files that are really PDFs: planned, but validate_mimetypes rejects the batch
    files = {"/images/a.jpg": "application/pdf", "/images/b.jpg": "application/pdf"}
    main, g, api = run_app(files)

    err = _import(main, g, api)

    assert err is not None and "2 of 2 images failed" in str(err)
    assert api.image.uploaded == []
    assert api.project.created == [100]
    assert api.project.removed == [100]  # the empty project this run created
    assert api.output_project is None  # no output pointing at a removed project
    assert api.file.removed == []


def test_all_images_rejected_keeps_an_existing_project(run_app):
    files = {"/images/a.jpg": "application/pdf", "/images/b.jpg": "application/pdf"}
    main, g, api = run_app(files, project_id=7)

    err = _import(main, g, api)

    assert err is not None and "2 of 2 images failed" in str(err)
    assert api.project.created == []
    assert api.project.removed == []  # never remove a project the run did not create
    assert api.output_project == 7
    assert api.file.removed == []


def test_no_supported_images_into_existing_project_fails(run_app):
    main, g, api = run_app({"/images/a.pdf": "application/pdf", "/images/b.txt": "text/plain"},
                           project_id=7)

    err = _import(main, g, api)

    assert err is not None and "No supported images found" in str(err)
    assert api.project.created == [] and api.project.removed == []
    assert api.file.removed == []
