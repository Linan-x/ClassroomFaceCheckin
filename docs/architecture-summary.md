# 人脸识别签到系统 — 最终架构总结

> 经过多次迭代重构后的正确设计

---

## 核心设计理念

### 1. 班级为中心，课程为上层

```
全局班级 (classes.json) ─── 班级特征库 (class_faces)
       ↕ 关联
   全局学生 (students_index.json)
       ↕ 关联
    课程 (data/courses/{name}/) ─── 签到记录 (attendance.json)
       ↕ 创建
    签到次数 (sessions.json) ─── 签到记录按次数隔离
```

**关键原则：** 特征库绑定班级而非课程。一次构建，所有关联该班级的课程复用。

### 2. 数据独立三层隔离

| 层级 | 隔离方式 | 说明 |
|------|---------|------|
| 课程 | 不同文件 | 每个课程独立 `attendance.json` |
| 签到次数 | session 字段 | 同课程不同次数按 `session` 过滤 |
| 班级特征库 | 共享 | 只用于人脸识别，不记录签到 |

### 3. 全局实体独立存在

- **学生** — 独立于课程，可归属一个班级，报名多个课程
- **班级** — 独立于课程，是特征库的单位

---

## 数据存储结构

```
data/
├── classes.json                    # 全局班级列表
├── students_index.json             # 全局学生索引（姓名/班级/电话）
├── students/photos/{name}.jpg      # 全局学生照片
├── class_faces/                    # 班级特征库（核心）
│   ├── _names.json                 # 班级名 → hash 映射
│   ├── {hash}/facebank.pth         # 特征张量 [n, 512]
│   └── {hash}/names.npy            # 姓名数组
└── courses/{name}/                 # 课程数据
    ├── meeting_info.json           # 课程信息 + 关联班级列表
    ├── participants/{name}/        # 学生照片（自动从全局复制）
    ├── attendance.json             # 签到记录（按 session 标记）
    └── sessions.json               # 签到次数管理
```

---

## 正确的工作流程

### 新建课程 → 签到全流程

```
1. 创建课程           → data/courses/{name}/meeting_info.json
2. 创建班级           → data/classes.json
3. 添加学生（拍照）    → data/students_index.json + 全局照片
4. 构建班级特征库      → data/class_faces/{hash}/ (一次构建，终身使用)
5. 课程关联班级        → meeting_info.json 写入 classes 字段
6. 新建签到次数        → sessions.json
7. 开始签到           → 自动使用班级特征库识别
8. 识别成功           → 写入 attendance.json (course + session 隔离)
```

### 关键：第 4 步只需做一次

班级特征库构建一次后，所有关联该班级的课程都自动使用，不需要为每个课程重复构建。

---

## API 正确调用关系

```
小程序签到页
  ├── loadCourseInfo()
  │   └── GET /api/mobile/checkin/result?course=X&session=Y
  │       └── 返回签到数据（按 course + session 过滤）
  │
  └── uploadPhoto()
      └── POST /api/mobile/checkin (course=X, session=Y, image=...)
          └── 服务端逻辑：
              1. 读取 session（优先客户端指定）
              2. 加载班级特征库（get_course_facebanks）
              3. MTCNN 检测人脸
              4. MobileFaceNet 提取特征
              5. 与特征库对比 → 识别
              6. 按 course + session 去重 → record_checkin
              7. 返回识别结果
```

---

## 解决的关键问题

| 问题 | 最终方案 |
|------|---------|
| 特征库重复构建 | 按班级构建，课程复用 |
| PyTorch 中文路径 | 班级名用 hash 替代 |
| 跨课程签到干扰 | course + session 双重隔离 |
| 实时页面数据不准 | 从空列表开始，只显示当前识别结果 |
| 识别速度慢 | TTA 可选、拍照间隔 400ms |
| 模型加载路径 | 绝对路径 + 共享模型实例 |
| GBK 编码崩溃 | print 避免 emoji |

---

## 技术栈最终版

| 层级 | 技术 | 版本 |
|------|------|------|
| 后端框架 | Flask | 2.2.x |
| 推理引擎 | PyTorch | 1.13.1 (CPU/GPU) |
| 人脸检测 | MTCNN | - |
| 人脸识别 | MobileFaceNet | 512维 + ArcFace |
| 识别阈值 | 距离 | 1.0 |
| 数据存储 | JSON + NumPy + PyTorch | - |
| Web 服务 | wsgiref + ThreadingMixIn | - |
| 小程序 SDK | WeChat | 3.16.1+ |
| 远程访问 | FRP | 0.67.0 |
