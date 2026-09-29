# 独立项目副本说明

本目录是从 `InsightFace_Pytorch-master` 复制出的独立课堂签到项目。

## 保留内容

- `core/`：人脸检测、特征提取和课堂签到业务
- `checkin_web/`：Web 管理后台和签到台
- `weapp/`：微信小程序
- `data/`：课堂、学生和签到数据
- `work_space/`：模型权重和运行工作目录
- `start_all.py`：统一启动入口，端口 8090

## 未复制内容

- Python 虚拟环境：`venv/`、`.venv/`
- IDE 和本地工具配置：`.idea/`、`.vscode/`、`.claude/`
- 历史压缩包、开发对话和临时日志
- 原始训练、视频推理等非课堂签到工具

## 启动

在本目录执行：

```powershell
& "D:\conda\envs\insightface\python.exe" start_all.py
```

然后访问 `http://localhost:8090/`。

## 数据隔离

本项目使用自己的 `data/` 和 `work_space/`。新增课程、学生照片、特征库和签到记录只会写入本副本，不会写入原项目。
