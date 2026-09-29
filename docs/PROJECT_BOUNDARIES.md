# 项目边界与代码归属

本项目由原始人脸识别模型代码和课堂/会议签到业务二次开发代码组成。为了保持现有 Python 导入路径和启动方式稳定，运行代码暂不做物理搬迁；下面的边界文件是维护和后续重构的依据。

## 原始项目部分

这些文件主要提供人脸检测、特征提取、模型训练和验证能力，原则上不包含签到业务：

- `core/model.py`：ArcFace/MobileFaceNet 网络结构
- `core/Learner.py`：模型加载、特征库推理和识别
- `core/mtcnn.py`：MTCNN 人脸检测封装
- `core/utils.py`：模型和图像处理基础工具
- `core/verifacation.py`：原始验证流程
- `core/mtcnn_pytorch/`：MTCNN 相关原始实现、权重和示例
- `core/config.py`：原始模型运行配置
- `work_space/save/model_mobilefacenet.pth`：模型权重
- `core/mtcnn_pytorch/src/weights/`：MTCNN 权重

## 二次开发部分

这些文件构成课堂/会议签到产品：

- `core/course.py`：课程、班级、学生、参与者和特征库业务
- `core/checkin.py`：签到记录和签到次数管理
- `core/report.py`：签到报告和导出
- `checkin_web/`：Flask 管理后台、签到台、摄像头和页面
- `weapp/`：微信小程序客户端
- `start_all.py`：统一启动入口，监听 8090 端口
- `checkin_system.py`：命令行签到业务入口
- `meeting.py`：兼容旧导入的业务模块
- `data/`：课程、学生、班级和签到运行数据
- `docs/`：本项目的设计、运行和维护文档

## 修改原则

1. 修改人脸识别算法时，优先只改“原始项目部分”。
2. 修改课程、签到、后台或小程序功能时，优先只改“二次开发部分”。
3. `start_all.py` 会把 `core/` 加入模块搜索路径，因此不要直接移动 `core` 下的 Python 文件，除非同步更新全部导入路径并完成启动验证。
4. `data/` 和模型权重属于运行时资产，不要与源码混放，也不要提交个人照片或生产数据。
