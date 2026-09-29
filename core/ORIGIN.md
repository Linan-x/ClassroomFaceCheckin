# core 目录归属

`core/` 同时包含原始模型代码和二次开发业务模块。为保持历史导入路径不变，文件继续放在当前目录。

## 原始模型代码

`model.py`、`Learner.py`、`mtcnn.py`、`utils.py`、`verifacation.py`、`config.py` 以及 `mtcnn_pytorch/` 属于原始人脸识别能力。

## 二次开发代码

`course.py`、`checkin.py`、`report.py` 是在原始识别能力之上增加的课程、学生、签到和报表业务。

完整边界说明见 [`../docs/PROJECT_BOUNDARIES.md`](../docs/PROJECT_BOUNDARIES.md)。

