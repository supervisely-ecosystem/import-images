
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
[![views](https://app.supervise.ly/img/badges/views/supervisely-ecosystem/import-images.png)](https://supervise.ly)
[![runs](https://app.supervise.ly/img/badges/runs/supervisely-ecosystem/import-images.png)](https://supervise.ly)

</div>

# Overview

This app allows you to upload only images without any annotations. By default, flags "normalize exif", "remove alpha channel" and "convert .tiff to .jpeg" are disabled. 
If images you import have exif rotation, or they look rotated in labeling interfaces please enable "normalize exif" flag in the modal window.
If your images have alpha channel, enable "remove alpha channel" flag. 
Be aware that "remove files after successful import" flag is enabled by default, it will automatically remove source directory after import. 
Images in `.nrrd` format can be viewed in annotation tool v2 only.

Supported images formats: `.jpg`, `.jpeg`, `jpe`, `.bmp`, `.png`, `.webp`, `.mpo`, `.tiff`, `.nrrd`(annotation tool v2 only). 

🔥 Starting from version `v1.2.0` application automatically compares image file extension with actual image mimetype and corrects extension if needed. For example: if you import image `my_image.png` but it is actually a TIFF then the image will be automatically renamed to `my_image.tiff`.

🏋️ Starting from version `v1.2.6` application supports import from special directory on your local computer. It is made for Enterprise Edition customers who need to upload tens or even hundreds of gigabytes of data without using drag-ang-drop mechanism:

1. Run agent on your computer where data is stored.
2. Copy your data to special folder on your computer that was created by agent. Agent mounts this directory to your Supervisely instance and it becomes accessible in Team Files. Learn more [in documentation](https://github.com/supervisely/docs/blob/master/customization/agents/agent-storage/agent-storage.md).
3. Go to `Team Files` -> `Supervisely Agent` and find your folder there.
4. Right click to open context menu and start app. Now app will upload data directly from your computer to the platform.

#### Input files structure

directories define dataset names. Images in root directory will be moved to dataset with name "`ds0`".
 
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

As a result we will get project with 3 datasets with the names: `ds0`, `my_folder1`, `my_folder3`. Dataset `my_folder1` will also contain images from `my_folder2` directory.

# How to Run

App can be launched from ecosystem, team files, images project and images dataset
* [running the app from ecosystem](#run-from-ecosystem) you will be given options to create new project, upload images to existing project or existing dataset
* [running the app from team files](#run-from-team-files) will result in new project
* [running the app from images project](#run-from-images-project) will upload images to existing project, from which it was launched
* [running the app from images dataset](#run-from-images-dataset) will upload images to existing dataset, from which it was launched

## Run from Ecosystem

**Step 1.** Run the app from Ecosystem

<img src="https://user-images.githubusercontent.com/48913536/178972013-f3d04518-6014-43c2-bc79-53813040331a.png" width="80%" style='padding-top: 10px'>  

**Step 2.** Drag & drop folder or images files, select options and press the Run button

<img src="https://user-images.githubusercontent.com/48913536/178972034-ea4ad77b-015a-4a4c-a065-3ffcef554296.png" width="80%" style='padding-top: 10px'>

## Run from Team Files

**Step 1.** Run the application from the context menu of the directory with images on Team Files page

<img src="https://user-images.githubusercontent.com/48913536/178972045-d2cb63bc-71e9-4fb5-8da0-5fa31511e614.png" width="80%" style='padding-top: 10px'>  

**Step 2.** Select options and press the Run button

<img src="https://user-images.githubusercontent.com/48913536/178972052-4bbc403e-b10a-4abc-91d2-fa0698b01a0a.png" width="80%" style='padding-top: 10px'>

## Run from Images Project

**Step 1.** Run the application from the context menu of the Images Project

<img src="https://user-images.githubusercontent.com/48913536/178972065-6b8f0ef6-9e7a-4753-9765-93ee6995fa7f.png" width="80%" style='padding-top: 10px'>  

**Step 2.** Drag & drop folder or images files, select options and press the Run button

<img src="https://user-images.githubusercontent.com/48913536/178972073-9bb47ed4-e859-4fb8-b8ee-dc7e40f9b49a.png" width="80%" style='padding-top: 10px'>

## Run from Images Dataset

**Step 1.** Run the application from the context menu of the Images Dataset

<img src="https://user-images.githubusercontent.com/48913536/178972085-69ffc5c7-02ee-43f2-a6fa-4eb74160496a.png" width="80%" style='padding-top: 10px'>  

**Step 2.** Drag & drop folder or images files, select options and press the Run button

<img src="https://user-images.githubusercontent.com/48913536/178972098-d5c8632c-4489-435a-9909-73c77ae6f656.png" width="80%" style='padding-top: 10px'>

## Result

<img src="https://user-images.githubusercontent.com/48913536/178972113-4d53f0dc-6323-4721-9ec2-f09de16ad0bc.png" width="80%" style='padding-top: 10px'>

### Demo
Example of uploading a flat set of images to Team Files:

![](https://i.imgur.com/EkLt9ii.gif)
