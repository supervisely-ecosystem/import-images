
<div align="center" markdown>
<img src="https://github.com/supervisely-ecosystem/import-images/releases/download/v1.0.0/poster.png"/>  

# Import Images

<p align="center">
  <a href="#Overview">Overview</a> •
  <a href="#How-To-Run">How To Run</a> •
  <a href="#Demo">Demo</a>
</p>

[![](https://img.shields.io/badge/supervisely-ecosystem-brightgreen)](https://ecosystem.supervise.ly/apps/supervisely-ecosystem/import-images)
[![](https://img.shields.io/badge/slack-chat-green.svg?logo=slack)](https://supervise.ly/slack)
![GitHub release (latest SemVer)](https://img.shields.io/github/v/release/supervisely-ecosystem/import-images)
[![views](https://app.supervise.ly/public/api/v3/ecosystem.counters?repo=supervisely-ecosystem/import-images&counter=views&label=views)](https://supervise.ly)
[![used by teams](https://app.supervise.ly/public/api/v3/ecosystem.counters?repo=supervisely-ecosystem/import-images&counter=downloads&label=used%20by%20teams)](https://supervise.ly)
[![runs](https://app.supervise.ly/public/api/v3/ecosystem.counters?repo=supervisely-ecosystem/import-images&counter=runs&label=runs&123)](https://supervise.ly)

</div>

# Overview

This app allows you to upload only images without any annotations. By default, flags "normalize exif", "remove alpha channel" and "convert .tiff to .jpeg" are disabled. 
If images you import has exif rotation, or they look rotated in labeling interfaces please enable "normalize exif" flag in the modal window.
If your images have alpha channel, enable "remove alpha channel" flag. 
Supervisely currently doesn't support `.tiff` image format, but if you want to import `.tiff` images, enable "convert .tiff to .jpeg" flag in the modal window. 
Be aware that "remove files after successful import" flag is enabled by default, it will automatically remove source directory after import. 
Images in `.nrrd` format can be viewed in Annotation Tool v2 only.

Supported images formats: `.jpg`, `.jpeg`, `.bmp`, `.png`, `.webp`, `.mpo`, `.tiff`(enable flag), `.nrrd`(Annotation Tool v2 only)'

#### Input files structure

Directory name defines project name, subdirectories define dataset names. Images in root directory will be moved to dataset with name "`ds0`".
 
```
.
my_images_project
├── img_01.jpeg
├── ...
├── img_09.png
├── my_folder1
│   ├── img_01.JPG
│   ├── img_02.jpeg
│   └── my_folder2
│       ├── img_13.jpeg
│       ├── ...
│       └── img_9999.png
└── my_folder3
    ├── img_01.JPG
    ├── img_02.jpeg
    └── img_03.png
```

As a result we will get project `my_images_project` with 3 datasets with the names: `ds0`, `my_folder1`, `my_folder3`. Dataset `my_folder1` will also contain images from `my_folder2` directory.

# How to Run

**Step 1.** Add [Import Images](https://ecosystem.supervise.ly/apps/supervisely-ecosystem/import-images) app to your team from Ecosystem

<img data-key="sly-module-link" data-module-slug="supervisely-ecosystem/import-images" src="https://i.imgur.com/7dfX1s2.png" width="350px" style='padding-bottom: 10px'/>

**Step 2.** Run the application from the context menu of the directory with images on Team Files page

<img src="https://i.imgur.com/0DF8igu.png" width="80%" style='padding-top: 10px'>  

**Step 3.** Select options and press the Run button

<img src="https://i.imgur.com/G6UjpD2.png" width="80%" style='padding-top: 10px'>  

### Demo
Example of uploading a flat set of images:
![](https://i.imgur.com/EkLt9ii.gif)
