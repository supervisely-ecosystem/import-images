# Import Images

This app allows you to upload only images without any annotations. By default flags "normalize_exif" and 
"remove_alpha_channel" are disabled. If images you import has exif rotation or they look rotated in labeling interfaces
please enable "normalize_exif" flag: `"normalize_exif": true`. If your images have alpha channel, enable 
"remove_alpha_channel" flag:  `"remove_alpha_channel": true`.

#### Input files structure

You have to drag and drop one or few directories with images. Directory name defines Dataset name. Images in root directory will move to dataset with name "`ds`" (if it name is free, in othercase will generate random name with "`ds_`" prefix).
 
```
 .
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

As a result we will get project with four datasets with the names: `ds`, `my_folder1`, `my_folder1__my_folder2`, `my_folder3`.

### Example 
Example of uploading a flat set of images:
![](https://i.imgur.com/COfEHoM.gif)
