# 人脸识别签到系统 — 设计文档

> 版本 2.1 | 2026年6月

---

## 1. 问题定义

### 1.1 背景
传统课堂/会议签到方式存在以下痛点：
- **纸质名单**：发放、回收、统计效率极低
- **扫码签到**：需学生主动操作，易遗漏
- **刷卡签到**：需硬件设备，代签无法防范
- **统计困难**：迟到、缺勤数据需人工整理

### 1.2 目标
构建一套基于人脸识别的智能签到系统，实现：
- **无感签到**：学生入镜即自动识别，无需任何操作
- **实时反馈**：签到结果即时显示在大屏和教师手机
- **多课多次**：同一课程可进行多次独立签到
- **跨平台**：教师手机（微信小程序）+ 电脑后台（Web）

### 1.3 用户场景
1. 教师创建课程，导入学生名单与照片
2. 教师打开小程序，选择课程和签到次数
3. 学生依次进入教室，摄像头自动识别签到
4. 大屏实时显示签到进度，已签/未签一目了然
5. 教师查看签到报告，导出数据

---

## 2. 核心模型与算法

### 2.1 人脸检测：MTCNN

MTCNN（Multi-Task Cascaded Convolutional Networks）是一个三阶段级联架构：

```
输入图像 → PNet (Proposal Network) → RNet (Refine Network) → ONet (Output Network)
```

- **PNet**：快速扫描全图，生成大量候选框
- **RNet**：对候选框精炼过滤，去除假阳性
- **ONet**：输出最终人脸框 + 5个关键点坐标

```
参数: min_face_size=20, face_limit=50
耗时: ~30ms (CPU), ~5ms (GPU)
```

### 2.2 人脸识别：MobileFaceNet + ArcFace

MobileFaceNet 是轻量级 CNN，专为移动端设计：

```
MobileFaceNet(输入112x112) → 512维特征向量 → L2归一化
                         ↕
              ArcFace Loss (训练时使用)
```

- **特征维度**：512
- **输入尺寸**：112x112
- **推理耗时**：~80ms (CPU), ~5ms (GPU)
- **TTA增强**：原图 + 水平翻转，取平均特征

### 2.3 识别流程

```
拍照(takePhoto) → JPEG压缩 → HTTP上传 → MTCNN检测
→ MobileFaceNet特征提取 → 与Facebank对比 → 距离<1.0 → 签到
```

### 2.4 签到次数（Session）机制

每次签到独立记录，按 `name + session_id` 双重去重：

```python
def record_checkin(course, name, score, session='1'):
    records = load_attendance(course)
    for r in records:
        if r['name'] == name and r.get('session') == session:
            return False  # 同一次签到内不重复
```

---

## 3. 系统架构

### 3.1 总体架构

```
┌─────────────────────────────────────────────────────────┐
│                    微信小程序 (WeApp)                     │
│  ┌──────┐ ┌────────┐ ┌────────┐ ┌──────┐ ┌──────────┐  │
│  │课程列表│ │课程详情│ │实时签到│ │签到结果│ │管理后台  │  │
│  └──────┘ └────────┘ └────────┘ └──────┘ └──────────┘  │
└──────────────────────┬──────────────────────────────────┘
                       │ HTTP API
                       ▼
┌─────────────────────────────────────────────────────────┐
│                  Flask Web 服务 (端口 8090)               │
│  checkin_web/app.py — 80+ 路由                          │
│  ├ 课程管理接口  ├ 学生管理接口  ├ 签到接口  ├ 移动端API │
└──────────────┬──────────────────────────────────────────┘
               │
┌──────────────┴──────────────────────────────────────────┐
│                    核心模块                               │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐   │
│  │ course.py│ │checkin.py│ │report.py │ │ Learner  │   │
│  │ 课程/学生 │ │ 签到记录  │ │ 报告统计  │ │ 识别模型 │   │
│  │ 班级/特征 │ │ 去重管理  │ │ 数据导出  │ │ MTCNN   │   │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘   │
└─────────────────────────────────────────────────────────┘

数据存储:
  JSON文件: data/courses/{name}/, data/students/, data/classes.json
  Tensor:   facebank.pth [n, 512], names.npy
  Image:    data/students/photos/{name}.jpg
```

### 3.2 数据模型

```
全局学生 (students_index.json)
├── name: 唯一标识
├── class: 所属班级
├── phone: 电话
├── courses: 报名课程列表

全局班级 (classes.json)
└── 班级名称数组 ["计算机一班", "计算机二班"]

课程 (data/courses/{name}/)
├── meeting_info.json    课程信息 + 关联班级
├── participants/{name}/ 学生照片
├── facebank.pth         特征张量
├── attendance.json      签到记录
├── sessions.json        签到次数管理
└── checkin_codes.json   签到码
```

### 3.3 API 路由设计

| 分组 | 示例路由 | 说明 |
|------|---------|------|
| 课程 | GET /api/meetings | CRUD |
| 学生 | GET /api/global/students | 全局增删改查 |
| 班级 | POST /api/global-classes | 全局管理 |
| 关联 | POST /api/course/{name}/classes | 班级→课程 |
| 签到次数 | POST /api/course/{name}/sessions | 新建/切换 |
| 特征库 | POST /api/meeting/{name}/build | 构建facebank |
| 移动端 | POST /api/mobile/checkin | 小程序签到 |

---

## 4. 难点与解决方案

### 4.1 微信小程序摄像头数据获取
**难点**：需实时获取摄像头帧数据上传识别，但小程序功能受限。
**方案**：采用 `takePhoto()` + `wx.uploadFile()` 组合，放弃 `onCameraFrame()` + canvas（兼容性差）。

### 4.2 多用户同时签到
**难点**：多人在镜头前同时出现时需一次性识别。
**方案**：MTCNN 的 `align_multi()` 支持同时检测多张人脸，`face_limit=50`。

### 4.3 同一课程多次签到
**难点**：同一课程在不同日期的签到需独立记录，不能混淆。
**方案**：Session 机制，每条签到记录带 session_id，去重和统计都按 session 过滤。

### 4.4 跨平台数据一致性
**难点**：Web 后台和小程序共享同一套数据，班级和学生需独立于课程存在。
**方案**：全局学生索引 + 全局班级注册表，课程只通过"关联"引用班级。

### 4.5 Python 3.7 兼容
**难点**：环境使用 Python 3.7，`Path.unlink()` 不支持 `missing_ok` 参数。
**方案**：所有 `unlink(missing_ok=True)` 改为 `if path.exists(): path.unlink()`。

### 4.6 Windows GBK 编码
**难点**：Windows 终端默认 GBK 编码，print emoji 会崩溃。
**方案**：`start_all.py` 中使用 ASCII 安全字符替代 emoji。

---

## 5. AI 工具使用说明

### 5.1 使用的 AI 工具
本项目使用 **Claude Code（Anthropic Claude）** 作为 AI 辅助开发工具，版本为 Claude Opus 4 / Sonnet 4。

### 5.2 典型提示词（Prompts）

**需求分析与架构设计：**
```
我想做一个基于 InsightFace_Pytorch 的人脸识别会议签到系统，
需要 Web 管理后台和微信小程序，该怎么做？
```

**功能迭代：**
```
学生注册可以选择课程和班级，不同课程可以批量导入班级学生，
学生只能选择一个班级多个课程
```

**Bug 修复：**
```
删除课程时会把已注册的学生信息删除，学生信息应该可以单独存在
```

**界面优化：**
```
重新设计课程那一页的布局，适合移动端
```

### 5.3 AI 生成的内容范围

| 模块 | AI 参与程度 | 说明 |
|------|-----------|------|
| 系统架构 | 设计+实现 | 从零搭建 Flask + 小程序架构 |
| 核心算法 | 集成 | MTCNN/MobileFaceNet 为开源模型，AI 负责集成调用 |
| 数据模型 | 设计+优化 | AI 设计全局学生/班级/签到次数模型 |
| Web 前端 | 全部生成 | admin.html、meeting_detail.html 等 |
| 小程序 | 全部生成 | 7个页面全部由 AI 生成 |
| API 路由 | 全部生成 | 80+ 路由 |
| Bug 修复 | 全部 | 路径错误、编码问题、Session 去重等 |
| 设计文档 | 全部生成 | 本文档 |

### 5.4 AI 辅助开发流程

```
1. 需求分析（Claude 提问→用户回答→明确需求）
2. 架构设计（Claude 提出方案→用户确认）
3. 编码实现（Claude 生成代码→用户测试）
4. Bug 修复（用户反馈→Claude 定位→修复）
5. 文档生成（Claude 撰写→用户审阅）
```

### 5.5 关键交互统计

- 总对话轮次：约 200+ 轮
- 代码文件生成：50+ 个
- Bug 修复次数：20+ 次
- 架构重构次数：3 次（单体→核心/遗留分离、路径统一、Session 机制）

---

## 6. 环境要求

### 6.1 硬件
- CPU: 双核 2.0GHz+ (推荐四核)
- 内存: 4GB+ (推荐 8GB)
- 硬盘: 5GB+ 可用空间
- 摄像头: 720p+ (签到台使用)
- 手机: Android/iOS (微信小程序)

### 6.2 软件
- 操作系统: Windows 10/11
- Python: 3.7.12
- 框架: Flask 2.2.x, PyTorch 1.13.1
- 数据库: JSON 文件系统
- 小程序 SDK: 3.16.1+

### 6.3 关键技术参数

| 参数 | 值 |
|------|-----|
| 人脸检测 | MTCNN (face_limit=50) |
| 人脸识别 | MobileFaceNet 512维 |
| 识别阈值 | 1.0 (距离) |
| 拍照间隔 | 250ms |
| Web 端口 | 8090 |
| 照片质量 | normal (签到) / low (检测) |
| TTA | 开启 |

---

## 7. 代码包说明

项目代码包不包含以下文件（需自行下载或生成）：
- `work_space/save/model_mobilefacenet.pth` (MobileFaceNet 权重)
- `core/mtcnn_pytorch/src/weights/*.npy` (MTCNN 权重)
- `venv/`, `.venv/`, `__pycache__/` (虚拟环境和缓存)
- `data/` 目录下的用户数据
