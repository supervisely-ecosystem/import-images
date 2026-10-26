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
    assert err is not None and "10 of 12 images failed" in str(err)  # task not "success"


def test_server_rejection_keeps_source_and_fails_task(run_app):
    main, g, api = run_app(_images(12), reject_names={"img_11.jpg"})

    err = _import(main, g, api)

    assert api.file.removed == []
    assert len(api.image.uploaded) == 10
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
