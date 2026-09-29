# 人脸识别签到系统 — 完整文档

基于 InsightFace_Pytorch (MTCNN + MobileFaceNet) 构建的课堂/会议人脸识别签到系统，支持 **Web 管理后台** + **微信小程序** 双端使用。

---

## 一键启动

```bash
cd D:\LiNan\InsightFace_Pytorch-master
"C:\ProgramData\miniconda3\envs\insightface\python.exe" start_all.py
```

| 功能 | 地址 |
|------|------|
| 管理后台 | `http://localhost:8090/` |
| 签到台 | `http://localhost:8090/kiosk/{课程名}` |
| 实时大屏 | `http://localhost:8090/dashboard/{课程名}` |
| 学生注册 | `http://localhost:8090/register/{课程名}` |
| 班级注册 | `http://localhost:8090/register/class/{班级名}` |

远程访问：`linan.xyz:18088` → `127.0.0.1:8090`（FRP）

---

## 项目结构

> 本项目由原始人脸识别模型和二次开发的签到业务组成。详细归属见
> [`docs/PROJECT_BOUNDARIES.md`](docs/PROJECT_BOUNDARIES.md)。

```
├── core/                    # 后端核心
│   ├── course.py            # 课程/学生/班级/签到次数/特征库
│   ├── checkin.py           # 签到记录管理
│   ├── report.py            # 签到报告统计
│   ├── Learner.py           # MobileFaceNet 识别模型
│   └── mtcnn.py             # MTCNN 人脸检测
├── checkin_web/             # Web 服务 (Flask, 80+路由)
│   ├── app.py               # 主应用
│   ├── camera.py            # 摄像头管理
│   ├── templates/           # 页面模板
│   └── static/              # CSS/JS
├── weapp/                   # 微信小程序
│   ├── pages/index/         # 课程列表（主页Tab）
│   ├── pages/course/        # 课程详情（签到操作入口）
│   ├── pages/checkin/       # 实时签到（摄像头+人脸框）
│   ├── pages/result/        # 签到结果
│   ├── pages/history/       # 签到历史
│   ├── pages/admin/         # 管理后台（课程/班级/学生/签到）
│   └── pages/detect/        # 人脸检测测试
├── data/
│   ├── courses/{name}/      # 课程数据
│   ├── students/            # 全局学生索引+照片
│   ├── classes.json         # 全局班级注册表
│   └── class_faces/         # 班级特征库（按班级构建，课程复用）
└── start_all.py             # 一键启动
```

---

## 数据模型

### 全局学生（独立于课程）
```json
{"张三": {"name":"张三","class":"计算机一班","phone":"138xxx","courses":["Python"],"created_at":"..."}}
```

### 全局班级（独立于课程）
```json
["计算机一班", "计算机二班"]
```

### 签到次数（同课程可多次签到）
```json
{"sessions":[{"id":"1","name":"第1次签到"},...],"active":"1"}
```

### 班级特征库（data/class_faces/）
```
data/class_faces/
├── _names.json           # 班级名→hash映射
├── {hash}/               # 按 hash 存储（避中文路径问题）
│   ├── facebank.pth      # 特征张量 [n, 512]
│   └── names.npy         # 姓名数组
```

---

## 核心功能

### 微信小程序
| 功能 | 说明 |
|------|------|
| 课程列表 | Tab主页，点击进入课程详情 |
| 课程详情 | 当前签到/新建签到/签到历史/签到总览 |
| 实时签到 | 摄像头拍照上传，人脸框叠加，实时速度显示 |
| 签到结果 | 已签到/未签到名单、签到率 |
| 签到历史 | 每次签到展开查看详细名单 |
| 管理后台 | 课程/班级/学生/签到 4个Tab |
| 人脸检测测试 | MTCNN纯检测画框 |

### Web 管理后台
- 课程管理、班级管理、学生管理（含照片）
- 签到报告、特征库构建、签到码管理
- 大屏看板（实时显示签到状态+照片）
- 学生自助注册（扫码→自拍→注册）

---

## 人脸识别流程

```
takePhoto() → wx.uploadFile() → 服务端 MTCNN 检测
→ MobileFaceNet 512维特征 → 与班级特征库对比
→ 距离 < 1.0 → 签到成功（TTA增强，双倍推理）
```

| 参数 | 值 |
|------|-----|
| 人脸检测 | MTCNN（最多50张） |
| 人脸识别 | MobileFaceNet 512维 |
| 识别阈值 | 1.0 |
| 拍照间隔 | 400ms |
| TTA | 开启 |
| Web端口 | 8090 |

---

## 班级特征库机制（核心设计）

特征库按**班级**构建，而非按课程。一次构建，所有关联该班级的课程复用。

```
构建：班级管理 → 🔧 构建 → data/class_faces/{hash}/
使用：课程 → 关联班级 → 签到自动加载班级特征库
```

- 避免重复构建特征库
- 新增课程关联班级后直接可用
- 无课程特征库时自动降级到班级特征库

---

## 签到次数（Session）机制

每次签到按 `course + session` 双重隔离：

- 去重：`record_checkin()` 按 `name + session + course` 判断
- 签到率：按当前活跃 session 统计
- 历史查看：按 session 查看每次的已签/未签名单
- 不同课程相同班级：签到记录完全隔离

---

## API 路由

### 特征库（班级级）
| 方法 | 路由 | 说明 |
|------|------|------|
| GET | `/api/class/<name>/build-facebank` | 查询状态 |
| POST | `/api/class/<name>/build-facebank` | 构建特征库 |
| GET/POST | `/api/course/<name>/classes` | 关联/查询班级 |

### 移动端 API
| 方法 | 路由 | 说明 |
|------|------|------|
| GET | `/api/mobile/courses` | 课程列表+进度 |
| POST | `/api/mobile/checkin` | 上传照片签到（带session） |
| POST | `/api/mobile/checkin-frame` | 快速帧识别 |
| GET | `/api/mobile/checkin/result` | 签到结果（按session过滤） |
| POST | `/api/mobile/detect` | 人脸检测测试 |

### 班级注册
| 方法 | 路由 | 说明 |
|------|------|------|
| GET | `/register/class/<name>` | 班级注册页面 |
| POST | `/api/register/class/<name>` | 班级注册API |

---

## 关键技术决策

| 决策 | 原因 |
|------|------|
| 班级特征库替代课程特征库 | 一次构建，所有课程复用 |
| 中文路径改用 hash | PyTorch 在 Windows 不支持中文路径 |
| takePhoto + uploadFile | onCameraFrame+canvas兼容性差 |
| 签到记录按 session 过滤 | 避免跨次数干扰 |
| 实时页面列表从空开始 | 避免不同课程数据混淆 |

---

## 常见问题

1. 特征库0人 → 检查班级是否有学生、全局照片是否存在
2. 签到400 → 检查FRP、urlCheck、服务是否启动
3. 跨课程数据干扰 → 已修复（按course+session严格隔离）
4. model_model_路径错误 → load_state传'mobilefacenet.pth'
5. 中文路径报错 → torch.save不支持中文，已用hash替代
6. GBK启动崩溃 → start_all.py避免print emoji
