# 课堂人脸识别签到系统

这是从 InsightFace_Pytorch 二次开发并独立复制出来的课堂人脸识别签到项目，基于 MTCNN + MobileFaceNet，支持 Web 管理后台和微信小程序。

本副本只面向课堂签到场景；原始项目与本项目互不共用运行目录，后续修改不会影响原项目。

------

## 1. Intro

- This repo is a reimplementation of Arcface[(paper)](https://arxiv.org/abs/1801.07698), or Insightface[(github)](https://github.com/deepinsight/insightface)
- For models, including the pytorch implementation of the backbone modules of Arcface and MobileFacenet
- Codes for transform MXNET data records in Insightface[(github)](https://github.com/deepinsight/insightface) to Image Datafolders are provided
- Pretrained models are posted, include the [MobileFacenet](https://arxiv.org/abs/1804.07573) and IR-SE50 in the original paper

------

## 2. Pretrained Models & Performance

[IR-SE50 @ BaiduNetdisk](https://pan.baidu.com/s/12BUjjwy1uUTEF9HCx5qvoQ), [IR-SE50 @ Onedrive](https://1drv.ms/u/s!AhMqVPD44cDOhkPsOU2S_HFpY9dC)

| LFW(%) | CFP-FF(%) | CFP-FP(%) | AgeDB-30(%) | calfw(%) | cplfw(%) | vgg2_fp(%) |
| ------ | --------- | --------- | ----------- | -------- | -------- | ---------- |
| 0.9952 | 0.9962    | 0.9504    | 0.9622      | 0.9557   | 0.9107   | 0.9386     |

[Mobilefacenet @ BaiduNetDisk](https://pan.baidu.com/s/1hqNNkcAjQOSxUjofboN6qg), [Mobilefacenet @ OneDrive](https://1drv.ms/u/s!AhMqVPD44cDOhkSMHodSH4rhfb5u)

| LFW(%) | CFP-FF(%) | CFP-FP(%) | AgeDB-30(%) | calfw(%) | cplfw(%) | vgg2_fp(%) |
| ------ | --------- | --------- | ----------- | -------- | -------- | ---------- |
| 0.9918 | 0.9891    | 0.8986    | 0.9347      | 0.9402   | 0.866    | 0.9100     |

## 3. How to use

- clone

  ```
  git clone https://github.com/TropComplique/mtcnn-pytorch.git
  ```

### 3.1 Data Preparation

#### 3.1.1 Prepare Facebank (For testing over camera or video)

Provide the face images your want to detect in the data/face_bank folder, and guarantee it have a structure like following:

```
data/facebank/
        ---> id1/
            ---> id1_1.jpg
        ---> id2/
            ---> id2_1.jpg
        ---> id3/
            ---> id3_1.jpg
           ---> id3_2.jpg
```

#### 3.1.2 download the pretrained model to work_space/model

If more than 1 image appears in one folder, an average embedding will be calculated

#### 3.2.3 Prepare Dataset ( For training)

download the refined dataset: (emore recommended)

- [emore dataset @ BaiduDrive](https://pan.baidu.com/s/1eXohwNBHbbKXh5KHyItVhQ), [emore dataset @ Dropbox](https://www.dropbox.com/s/wpx6tqjf0y5mf6r/faces_ms1m-refine-v2_112x112.zip?dl=0)
- More Dataset please refer to the [original post](https://github.com/deepinsight/insightface/wiki/Dataset-Zoo)

**Note:** If you use the refined [MS1M](https://arxiv.org/abs/1607.08221) dataset and the cropped [VGG2](https://arxiv.org/abs/1710.08092) dataset, please cite the original papers.

- after unzip the files to 'data' path, run :

  ```
  python prepare_data.py
  ```

  after the execution, you should find following structure:

```
faces_emore/
            ---> agedb_30
            ---> calfw
            ---> cfp_ff
            --->  cfp_fp
            ---> cfp_fp
            ---> cplfw
            --->imgs
            ---> lfw
            ---> vgg2_fp
```

------

### 3.2 detect over camera:

- 1. download the desired weights to model folder:

- [IR-SE50 @ BaiduNetdisk](https://pan.baidu.com/s/12BUjjwy1uUTEF9HCx5qvoQ)
- [IR-SE50 @ Onedrive](https://1drv.ms/u/s!AhMqVPD44cDOhkPsOU2S_HFpY9dC)
- [Mobilefacenet @ BaiduNetDisk](https://pan.baidu.com/s/1hqNNkcAjQOSxUjofboN6qg)
- [Mobilefacenet @ OneDrive](https://1drv.ms/u/s!AhMqVPD44cDOhkSMHodSH4rhfb5u)

- 2 to take a picture, run

  ```
  python take_pic.py -n name
  ```

  press q to take a picture, it will only capture 1 highest possibility face if more than 1 person appear in the camera

- 3 or you can put any preexisting photo into the facebank directory, the file structure is as following:

```
- facebank/
         name1/
             photo1.jpg
             photo2.jpg
             ...
         name2/
             photo1.jpg
             photo2.jpg
             ...
         .....
    if more than 1 image appears in the directory, average embedding will be calculated
```

- 4 to start

  ```
  python face_verify.py 
  ```

- - -

### 3.3 detect over video:

```
​```
python infer_on_video.py -f [video file name] -s [save file name]
​```
```

the video file should be inside the data/face_bank folder

- Video Detection Demo [@Youtube](https://www.youtube.com/watch?v=6r9RCRmxtHE)

### 3.4 Training:

```
​```
python train.py -b [batch_size] -lr [learning rate] -e [epochs]

# python train.py -net mobilefacenet -b 200 -w 4
​```
```

## 4. References 

- This repo is mainly inspired by [deepinsight/insightface](https://github.com/deepinsight/insightface) and [InsightFace_TF](https://github.com/auroua/InsightFace_TF)

## PS

- PRs are welcome, in case that I don't have the resource to train some large models like the 100 and 151 layers model
- Email : treb1en@qq.com

---

# 人脸识别签到系统 — 启动说明

基于 InsightFace_Pytorch 构建的课堂/会议签到系统，支持 Web 管理后台 + 微信小程序。

## 环境配置

### 1. 创建环境
```bash
conda create -n insightface python=3.7
conda activate insightface
```

### 2. 安装依赖
```bash
pip install flask flask-cors numpy pillow opencv-python
# CPU 版 PyTorch
pip install torch==1.13.1+cpu torchvision==0.14.1+cpu -f https://download.pytorch.org/whl/torch_stable.html
# 或 GPU 版（需 CUDA 11.7）
pip install torch==1.13.1+cu117 torchvision==0.14.1+cu117 -f https://download.pytorch.org/whl/cu117
```

### 3. 模型权重
下载以下文件放入对应目录：

| 文件 | 路径 |
|------|------|
| pnet.npy / rnet.npy / onet.npy | core/mtcnn_pytorch/src/weights/ |
| model_mobilefacenet.pth | work_space/save/ |

MTCNN 权重：https://github.com/StrangerThings98/MTCNN-Pytorch/tree/master/src/weights

### 4. 微信小程序
用微信开发者工具打开 `weapp/` 目录，修改 `app.js` 中 `serverUrl` 为实际服务器地址，`project.config.json` 中 `urlCheck` 设为 `false`。

## 启动服务
```bash
conda activate insightface

# 生产环境请设置一个随机的长期密钥（PowerShell）
$env:FLASK_SECRET_KEY = "请替换为随机字符串"

python start_all.py
```

访问 http://localhost:8090/ 进入管理后台。

> `data/` 中的学生照片、人脸库、签到记录和课程运行数据属于本地数据，默认已被 `.gitignore` 忽略，不应上传到公开仓库。

## 项目结构
```
├── core/           # 后端核心（课程/学生/签到/特征库/MTCNN/MobileFaceNet）
├── checkin_web/    # Flask Web 服务（80+路由）
├── weapp/          # 微信小程序（7个页面）
├── data/           # 数据存储
├── work_space/     # 模型与运行工作目录
├── docs/           # 设计文档、实验 notebook、历史归档
├── legacy/         # 旧版训练与推理脚本
├── requirements.txt
└── start_all.py    # 一键启动（8090端口）
```

完整文档见 `CHECKIN_SYSTEM.md`、`docs/design-document.md` 和 `docs/PROJECT_BOUNDARIES.md`。

## 原始代码与二次开发边界

本项目保留了原始 InsightFace_Pytorch 的模型与 MTCNN 能力，同时增加了课堂/会议签到系统。代码归属和修改边界见 [`docs/PROJECT_BOUNDARIES.md`](docs/PROJECT_BOUNDARIES.md)。

- 原始模型部分：`core/model.py`、`core/Learner.py`、`core/mtcnn.py`、`core/mtcnn_pytorch/`
- 二次开发部分：`core/course.py`、`core/checkin.py`、`core/report.py`、`checkin_web/`、`weapp/`、`start_all.py`
