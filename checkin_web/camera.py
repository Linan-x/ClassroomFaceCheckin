"""摄像头管理模块 — 背景线程推流 + 人脸识别签到"""

import threading
import time
import traceback
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
from PIL import Image
import torch

from model import l2_norm
import checkin as checkin_mod
from PIL import ImageDraw, ImageFont

# 语音播报（可选，无依赖时静默跳过）
try:
    from checkin_web.speaker import say_checkin as _say_checkin
except Exception:
    _say_checkin = None


# ─── 中文文本绘制（OpenCV cv2.putText 不支持中文，用 PIL 代替）───

# 尝试加载中文字体（Windows 系统字体）
_CHINESE_FONT = None
_FONT_PATHS = [
    "C:/Windows/Fonts/msyh.ttc",      # 微软雅黑
    "C:/Windows/Fonts/simhei.ttf",     # 黑体
    "C:/Windows/Fonts/simsun.ttc",     # 宋体
    "C:/Windows/Fonts/yahei.ttf",      # 微软雅黑 (别名)
    "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",  # Linux 文泉驿
]
for _fp in _FONT_PATHS:
    try:
        _CHINESE_FONT = ImageFont.truetype(_fp, 24)
        break
    except (IOError, OSError):
        continue


def draw_chinese_text(frame, text, pos, color=(255, 255, 255), font_size=24):
    """在 OpenCV 帧上绘制中文文本（BGR 格式）

    Args:
        frame: OpenCV BGR numpy array (会直接修改)
        text: 要绘制的文本（支持中文）
        pos: (x, y) 左上角坐标
        color: BGR 颜色元组 (b, g, r)
        font_size: 字体大小
    Returns:
        (tw, th) 文本宽度和高度
    """
    if not text:
        return (0, 0)

    # 转换为 PIL RGB
    pil_img = Image.fromarray(frame[..., ::-1])
    draw = ImageDraw.Draw(pil_img)

    # 获取或创建字体
    font = _CHINESE_FONT
    if font is None:
        # 无中文字体时回退到默认字体
        font = ImageFont.load_default()
    else:
        # 按需调整字体大小
        try:
            font = ImageFont.truetype(font.path, font_size)
        except Exception:
            pass

    # 计算文本尺寸
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]

    # 绘制文本 (PIL 用 RGB，需要转换)
    rgb_color = (color[2], color[1], color[0])  # BGR -> RGB
    draw.text(pos, text, font=font, fill=rgb_color)

    # 转回 OpenCV BGR
    frame[...] = np.array(pil_img)[..., ::-1]
    return (tw, th)


def draw_chinese_label_bg(frame, text, pos, text_color, bg_color, font_size=24):
    """绘制带背景的中文标签（类似 cv2.putText + cv2.rectangle）

    Args:
        frame: OpenCV BGR numpy array
        text: 标签文本
        pos: (x, y) 标签左上角
        text_color: 文字颜色 BGR
        bg_color: 背景颜色 BGR
        font_size: 字体大小
    Returns:
        (tw, th) 文本尺寸
    """
    tw, th = draw_chinese_text(frame, text, pos, text_color, font_size)
    # 在文字下方画背景（用 OpenCV 矩形，效率更高）
    if tw > 0 and th > 0:
        pad = 4
        cv2.rectangle(frame,
                      (pos[0] - pad, pos[1] - pad),
                      (pos[0] + tw + pad, pos[1] + th + pad),
                      bg_color, -1)
        # 背景画完再画一次文字（避免被背景覆盖）
        draw_chinese_text(frame, text, pos, text_color, font_size)
    return (tw, th)

# 全局摄像头管理器（单例）
_camera_manager = None
_lock = threading.Lock()


def get_camera_manager():
    global _camera_manager
    with _lock:
        if _camera_manager is None:
            _camera_manager = CameraManager()
        return _camera_manager


# 帧率优化配置
CAMERA_WIDTH = 640        # 采集宽度 (越小越快)
CAMERA_HEIGHT = 480       # 采集高度 (越小越快)
CAMERA_FPS = 30           # 目标帧率
JPEG_QUALITY = 55         # JPEG 压缩质量 (0-100, 越小编码越快)
DETECTION_INTERVAL = 3    # 每 N 帧检测一次 (越大越流畅但检测响应变慢)


def _open_camera():
    """尝试打开摄像头，兼容不同 OpenCV 版本

    返回 (cap, backend_name, idx) 或 (None, msg, -1)
    """
    _CAP_ANY = getattr(cv2, 'CAP_ANY', 0)
    _CAP_DSHOW = getattr(cv2, 'CAP_DSHOW', None)

    def _try_cap(cap, name, idx):
        """尝试设置分辨率并测试读取"""
        if cap is None or not cap.isOpened():
            return None
        # 设置低分辨率加快速度
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        ret, frame = cap.read()
        if ret and frame is not None and frame.size > 0:
            h, w = frame.shape[:2]
            print(f"[camera] 打开成功: {name} backend, index {idx}, {w}x{h}")
            return cap
        cap.release()
        return None

    # 策略 1: default backend
    for idx in range(2):
        try:
            cap = _try_cap(cv2.VideoCapture(idx), "default", idx)
            if cap: return cap, "default", idx
        except Exception as e:
            print(f"[camera] default {idx}: {e}")

    # 策略 2: DirectShow (Windows)
    if _CAP_DSHOW is not None:
        for idx in range(2):
            try:
                cap = _try_cap(cv2.VideoCapture(idx, _CAP_DSHOW), "DirectShow", idx)
                if cap: return cap, "DirectShow", idx
            except Exception as e:
                print(f"[camera] DirectShow {idx}: {e}")

    # 策略 3: MSMF (Windows Media Foundation)
    _CAP_MSMF = getattr(cv2, 'CAP_MSMF', None)
    if _CAP_MSMF is not None:
        for idx in range(2):
            try:
                cap = _try_cap(cv2.VideoCapture(idx, _CAP_MSMF), "MSMF", idx)
                if cap: return cap, "MSMF", idx
            except Exception as e:
                print(f"[camera] MSMF {idx}: {e}")

    return None, "无法连接摄像头 (已尝试 default/DirectShow/MSMF, index 0/1)", -1


class CameraManager:
    """摄像头管理器，在后台线程中运行人脸识别签到"""

    def __init__(self):
        self._thread = None
        self._stop_event = threading.Event()
        self._frame_bytes = None
        self._frame_lock = threading.Lock()
        self._status = {
            "active": False,
            "meeting": None,
            "total": 0,
            "checked_in": 0,
            "checked_names": [],
            "unchecked_names": [],
            "last_checkin": None,
            "error": None,
            "camera_ok": False,
        }
        self._status_lock = threading.Lock()
        self._cap = None

    @property
    def is_active(self):
        return self._thread is not None and self._thread.is_alive()

    def start(self, meeting_name, learner, mtcnn, conf, threshold=None):
        """启动签到摄像头"""
        if self.is_active:
            # 如果已有活动签到，先停掉
            self.stop()

        if threshold is not None:
            learner.threshold = threshold

        # 加载 facebank
        proj_root = Path(__file__).resolve().parent.parent
        meeting_path = proj_root / 'data' / 'courses' / meeting_name
        fb_path = meeting_path / 'facebank.pth'
        names_path = meeting_path / 'names.npy'

        if not fb_path.exists() or not names_path.exists():
            raise FileNotFoundError(f"会议 '{meeting_name}' 特征库不存在，请先构建")

        targets = torch.load(fb_path)
        names = np.load(names_path)

        self._stop_event.clear()
        self._frame_bytes = None
        self._status = {
            "active": True,
            "meeting": meeting_name,
            "total": int(len(names) - 1),
            "checked_in": 0,
            "checked_names": [],
            "unchecked_names": list(names[1:]) if len(names) > 1 else [],
            "last_checkin": None,
            "error": None,
            "camera_ok": False,
        }

        # 加载已有签到记录
        already_checked = checkin_mod.get_checked_in_names(meeting_name)
        self._update_checked(already_checked, names)

        self._thread = threading.Thread(
            target=self._camera_loop,
            args=(meeting_name, learner, mtcnn, conf, targets, names),
            daemon=True
        )
        self._thread.start()
        # 等待摄像头初始化（最长 5 秒）
        for i in range(10):
            time.sleep(0.5)
            with self._status_lock:
                err = self._status.get("error")
                if err:
                    raise RuntimeError(err)
                if self._status.get("camera_ok"):
                    return True  # 摄像头就绪
        # 超时
        with self._status_lock:
            err = self._status.get("error", "摄像头初始化超时")
        raise RuntimeError(err)

    def stop(self):
        """停止摄像头签到"""
        self._stop_event.set()

        # 强制释放摄像头（即使 cap.read 阻塞中）
        if self._cap is not None:
            try:
                self._cap.release()
            except Exception:
                pass
            self._cap = None

        if self._thread:
            self._thread.join(timeout=2.0)
            # 如果线程还没结束，daemon=True 会在主进程退出时自动结束
            self._thread = None

        self._cap = None
        with self._status_lock:
            self._status["active"] = False
            self._status["camera_ok"] = False
        with self._frame_lock:
            self._frame_bytes = None
        return True

    def get_frame(self):
        with self._frame_lock:
            return self._frame_bytes

    def get_status(self):
        with self._status_lock:
            return dict(self._status)

    def _update_checked(self, checked_set, names):
        with self._status_lock:
            self._status["checked_in"] = len(checked_set)
            self._status["checked_names"] = sorted(checked_set)
            self._status["unchecked_names"] = [
                n for n in names[1:] if n not in checked_set
            ]

    def _make_error_frame(self, msg):
        """生成带有错误信息的帧"""
        frame = np.full((480, 640, 3), 30, dtype=np.uint8)
        draw_chinese_text(frame, "⚠ " + msg, (50, 200),
                          color=(0, 0, 255), font_size=28)
        draw_chinese_text(frame, "请检查摄像头连接后重试", (50, 250),
                          color=(200, 200, 200), font_size=22)
        ret, jpeg = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
        if ret:
            with self._frame_lock:
                self._frame_bytes = jpeg.tobytes()

    def _make_stopped_frame(self, meeting_name, checked_set, names):
        """生成签到结束的总结帧"""
        frame = np.full((480, 640, 3), 30, dtype=np.uint8)
        draw_chinese_text(frame, "签到已结束", (170, 80),
                          color=(16, 185, 129), font_size=36)
        y = 140
        for n in names[1:]:
            mark = "[已到]" if n in checked_set else "[未到]"
            color = (16, 185, 129) if n in checked_set else (200, 200, 200)
            draw_chinese_text(frame, f"  {mark}  {n}", (200, y),
                              color=color, font_size=22)
            y += 36
        ret, jpeg = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 75])
        if ret:
            with self._frame_lock:
                self._frame_bytes = jpeg.tobytes()

    def _camera_loop(self, meeting_name, learner, mtcnn, conf, targets, names):
        """摄像头主循环（后台线程）— 优化版：支持多人快速签到"""
        # 打开摄像头
        self._cap, backend_name, idx = _open_camera()
        if self._cap is None:
            err_msg = backend_name
            print(f"[camera] 打开失败: {err_msg}")
            with self._status_lock:
                self._status["error"] = err_msg
                self._status["active"] = False
            self._make_error_frame(err_msg)
            return

        with self._status_lock:
            self._status["camera_ok"] = True
            self._status["error"] = None

        checked_set = checkin_mod.get_checked_in_names(meeting_name)

        # 跳帧策略：每 DETECTION_INTERVAL 帧做一次完整检测
        # 其余帧直接用上次的检测结果画框，大幅提高画面流畅度
        frame_count = 0
        # 缓存上一轮检测结果，跳帧时复用
        cached_detections = []  # list of {"bbox": (x1,y1,x2,y2), "label": str, "color": tuple}

        # 多人签到通知：显示最近 N 人的签到通知
        recent_checkins = []  # list of {"name": str, "time": float, "late": bool}
        notify_duration = 2.0  # 每个通知显示2秒

        # 先输出一帧原始画面（快速出图，让用户看到画面）
        ret, first_frame = self._cap.read()
        if ret and first_frame is not None and first_frame.size > 0:
            ret_jpeg, jpeg_buf = cv2.imencode(
                '.jpg', first_frame, [cv2.IMWRITE_JPEG_QUALITY, 75]
            )
            if ret_jpeg:
                with self._frame_lock:
                    self._frame_bytes = jpeg_buf.tobytes()

        while not self._stop_event.is_set():
            ret, frame = self._cap.read()
            if not ret or frame is None or frame.size == 0:
                if self._stop_event.is_set():
                    break
                time.sleep(0.03)
                continue

            frame_count += 1
            do_detect = (frame_count % DETECTION_INTERVAL == 0)

            try:
                h, w = frame.shape[:2]
                total_people = len(names) - 1
                checked_now = len(checked_set)

                if do_detect:
                    # ── 完整检测帧：MTCNN + 识别 ──
                    rgb = frame[..., ::-1].copy()
                    image = Image.fromarray(rgb)
                    bboxes, faces = mtcnn.align_multi(
                        image, conf.face_limit, conf.min_face_size
                    )

                    current_detections = []
                    if len(bboxes) > 0 and len(faces) > 0:
                        bboxes_arr = bboxes[:, :-1].astype(int)
                        bboxes_arr = bboxes_arr + [-1, -1, 1, 1]
                        results, scores = learner.infer(
                            conf, faces, targets, True
                        )

                        for idx, bbox in enumerate(bboxes_arr):
                            person_idx = int(results[idx])
                            if person_idx == -1:
                                label = "Unknown"
                                color = (68, 68, 239)  # BGR 红
                            else:
                                name = names[person_idx + 1]
                                score = float(scores[idx])
                                if name not in checked_set:
                                    # 自动签到（无需确认）
                                    recorded = checkin_mod.record_checkin(
                                        meeting_name, name, score
                                    )
                                    if recorded:
                                        recent_checkins.append({
                                            "name": name,
                                            "time": time.time(),
                                            "late": recorded.get('late', False),
                                            "late_min": recorded.get('late_minutes', 0)
                                        })
                                        if recorded.get('late'):
                                            late_min = recorded.get('late_minutes', 0)
                                            print(f"[Web签到] {name} (迟到{late_min}分钟)")
                                            if _say_checkin:
                                                _say_checkin(name, late=True, late_minutes=late_min)
                                        else:
                                            print(f"[Web签到] {name} (准时)")
                                            if _say_checkin:
                                                _say_checkin(name)
                                    checked_set.add(name)
                                    self._update_checked(checked_set, names)
                                    label = name
                                    color = (246, 130, 59)  # BGR 蓝 — 新签到
                                else:
                                    label = f"{name} (已到)"
                                    color = (129, 185, 16)  # BGR 绿

                            current_detections.append({
                                "bbox": bbox, "label": label, "color": color
                            })

                    cached_detections = current_detections

                # ── 绘制人脸框（使用缓存的检测结果） ──
                for det in cached_detections:
                    bbox = det["bbox"]
                    cv2.rectangle(
                        frame, (bbox[0], bbox[1]),
                        (bbox[2], bbox[3]), det["color"], 2
                    )
                    label_pos = (bbox[0], bbox[1] - 28)
                    draw_chinese_label_bg(
                        frame, det["label"], label_pos,
                        text_color=(255, 255, 255),
                        bg_color=det["color"], font_size=22
                    )

                # ── HUD 信息 ──
                draw_chinese_text(frame, meeting_name, (16, 8),
                                  color=(255, 255, 255), font_size=26)
                cv2.putText(frame, f"{checked_now}/{total_people}",
                            (w - 120, 36),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.9,
                            (16, 185, 129), 2)

                # ── 多人签到通知条（同时显示最近签到的多人） ──
                now = time.time()
                # 过滤出还在通知有效期内的签到（取最近 4 人）
                active = [c for c in recent_checkins
                          if now - c["time"] < notify_duration]
                # 从最新到最旧排序（最新的在最下方）
                active_reversed = list(reversed(active))
                for ni, ci in enumerate(active_reversed[:4]):
                    alpha = max(0.3, 1.0 - (now - ci["time"]) / notify_duration)
                    bar_w = 320
                    bar_x = (w - bar_w) // 2
                    bar_y = h - 140 + ni * 40

                    overlay = frame.copy()
                    if ci.get("late"):
                        bg_color = (11, 158, 245)  # 橙色 (BGR)
                    else:
                        bg_color = (16, 185, 129)  # 绿色
                    cv2.rectangle(overlay,
                                  (bar_x, bar_y), (bar_x + bar_w, bar_y + 30),
                                  bg_color, -1)
                    cv2.addWeighted(overlay, 0.85 * alpha, frame, 0.15, 0, frame)
                    draw_chinese_text(
                        frame, f"✓  {ci['name']}",
                        (bar_x + 16, bar_y + 3),
                        color=(255, 255, 255), font_size=20
                    )
                    # 如果迟到，标注
                    late_min = ci.get("late_min", 0)
                    if ci.get("late") and late_min > 0:
                        draw_chinese_text(
                            frame, f"迟到{late_min}分钟",
                            (bar_x + bar_w - 130, bar_y + 3),
                            color=(255, 255, 200), font_size=16
                        )

            except Exception:
                traceback.print_exc()

            # 编码为 JPEG（低质量=更快的编码+更小的网络传输）
            ret_jpeg, jpeg_buf = cv2.imencode(
                '.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY]
            )
            if ret_jpeg:
                with self._frame_lock:
                    self._frame_bytes = jpeg_buf.tobytes()

        # 循环结束：生成结束画面
        self._make_stopped_frame(meeting_name, checked_set, names)

        if self._cap:
            try:
                self._cap.release()
            except Exception:
                pass
            self._cap = None

        with self._status_lock:
            self._status["active"] = False
            self._status["camera_ok"] = False
