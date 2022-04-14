# Import Images

This app allows you to upload only images without any annotations. Supported images formats: 

#### Input files structure

You have to drag and drop one directory with images. Directory name defines project name, subdirectories define dataset names. Images in root directory will be moved to dataset with name "`ds0`".
 
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

As a result we will get project `my_images_project` with four datasets with the names: `ds0`, `my_folder1`, `my_folder1__my_folder2`, `my_folder3`.

### Example 
Example of uploading a flat set of images:
![](https://i.imgur.com/COfEHoM.gif)
