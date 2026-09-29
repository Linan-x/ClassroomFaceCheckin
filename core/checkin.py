"""签到执行模块 — 摄像头人脸识别签到"""

import json
import traceback
from pathlib import Path
from datetime import datetime
from PIL import Image
import cv2
import numpy as np
import torch

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MEETINGS_ROOT = PROJECT_ROOT / 'data' / 'courses'


def _meeting_path(name):
    return MEETINGS_ROOT / name


# ─── 签到记录管理 ──────────────────────────────────

def _load_attendance(meeting_name):
    """加载签到记录"""
    path = _meeting_path(meeting_name) / 'attendance.json'
    if not path.exists():
        return []
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def _save_attendance(meeting_name, records):
    """保存签到记录"""
    path = _meeting_path(meeting_name) / 'attendance.json'
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(records, f, ensure_ascii=False, indent=2)


def record_checkin(meeting_name, name, confidence, session=None):
    """记录一条签到

    Args:
        meeting_name: 课程名称
        name: 学生姓名
        confidence: 匹配距离（越小越可靠）
        session: 签到次数ID（同一课程可多次签到）

    Returns:
        dict 包含签到信息（含迟到状态）或 False（已签到）
    """
    records = _load_attendance(meeting_name)
    now = datetime.now()
    time_str = now.isoformat()

    # 如果没有指定session，获取当前活跃的签到次数
    if not session:
        try:
            from course import get_active_session
            s = get_active_session(meeting_name)
            session = s['id']
        except Exception:
            session = time_str[:10]  # 降级到按天

    # 去重：同一签到次数内不重复
    for r in records:
        if r['name'] == name and r.get('session') == session:
            return False

    # 判断是否迟到
    try:
        from course import is_late
        late, late_min = is_late(meeting_name, time_str)
    except Exception:
        late, late_min = False, 0

    record = {
        "name": name,
        "time": time_str,
        "session": session,
        "confidence": float(confidence),
        "late": late,
        "late_minutes": late_min
    }
    records.append(record)
    _save_attendance(meeting_name, records)
    return record


def is_checked_in(meeting_name, name):
    """检查某人是否已签到"""
    records = _load_attendance(meeting_name)
    return any(r['name'] == name for r in records)


def get_checked_in_names(meeting_name, session=None):
    """获取已签到者姓名（可按签到次数过滤）"""
    records = _load_attendance(meeting_name)
    if session:
        records = [r for r in records if r.get('session') == session]
    return set(r['name'] for r in records)


# ─── 签到主流程 ────────────────────────────────────

def start_checkin(meeting_name, learner, mtcnn, conf, threshold=None, tta=True):
    """启动摄像头签到

    Args:
        meeting_name: 会议名称
        learner: face_learner 实例（已加载模型）
        mtcnn: MTCNN 检测器
        conf: 配置
        threshold: 识别阈值（默认用 conf.threshold）
        tta: 是否启用测试时增强
    """
    if threshold is not None:
        learner.threshold = threshold

    # 加载会议 facebank
    meeting_path = _meeting_path(meeting_name)
    fb_path = meeting_path / 'facebank.pth'
    names_path = meeting_path / 'names.npy'

    if not fb_path.exists() or not names_path.exists():
        print(f"错误: 会议 '{meeting_name}' 的特征库不存在，请先执行构建facebank")
        return

    targets = torch.load(fb_path)
    names = np.load(names_path)
    print(f"已加载特征库: {len(targets)} 人")

    # 打开摄像头
    cap = cv2.VideoCapture(0)
    cap.set(3, 1280)
    cap.set(4, 720)
    if not cap.isOpened():
        print("摄像头打开失败")
        return

    print("\n===== 签到已启动 =====")
    print(f"会议: {meeting_name}")
    print(f"参与者: {len(names) - 1} 人")
    print("按 q 退出签到 | 按 r 显示当前签到报告")
    print("=" * 25)

    # 已签到集合（用于实时去重）
    checked_in = get_checked_in_names(meeting_name)

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            continue

        try:
            image = Image.fromarray(frame)
            bboxes, faces = mtcnn.align_multi(image, conf.face_limit, conf.min_face_size)

            if len(bboxes) > 0 and len(faces) > 0:
                bboxes = bboxes[:, :-1].astype(int)
                bboxes = bboxes + [-1, -1, 1, 1]

                results, scores = learner.infer(conf, faces, targets, tta)

                for idx, bbox in enumerate(bboxes):
                    person_idx = int(results[idx])
                    if person_idx == -1:
                        # 未识别
                        label = "Unknown"
                        color = (0, 0, 255)  # BGR 红
                    else:
                        name = names[person_idx + 1]  # +1 偏移跳过 Unknown
                        score = float(scores[idx])
                        if name not in checked_in:
                            # 首次识别到 → 签到
                            recorded = record_checkin(meeting_name, name, score)
                            if recorded:
                                print(f"[签到] {name}  ({datetime.now().strftime('%H:%M:%S')}, 距离:{score:.3f})")
                            checked_in.add(name)
                            label = f"{name}"
                            color = (255, 0, 0)  # BGR 蓝（新识别）
                        else:
                            label = f"{name} ✓"
                            color = (0, 255, 0)  # BGR 绿（已签到）

                    # 画框
                    cv2.rectangle(frame, (bbox[0], bbox[1]), (bbox[2], bbox[3]), color, 3)
                    # 背景标签
                    (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.8, 2)
                    cv2.rectangle(frame, (bbox[0], bbox[1] - th - 10), (bbox[0] + tw, bbox[1]), color, -1)
                    cv2.putText(frame, label, (bbox[0], bbox[1] - 5),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
        except Exception:
            traceback.print_exc()

        # 右上角显示签到统计
        total = len(names) - 1
        stats = f"签到: {len(checked_in)}/{total}"
        cv2.putText(frame, stats, (frame.shape[1] - 250, 40),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 2)
        cv2.putText(frame, f"会议: {meeting_name}", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        cv2.putText(frame, "q:退出 r:报告", (10, frame.shape[0] - 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 2)

        cv2.imshow('Meeting Check-in', frame)
        key = cv2.waitKey(1) & 0xFF

        if key == ord('q'):
            break
        elif key == ord('r'):
            # 显示实时签到报告（在终端）
            checked = get_checked_in_names(meeting_name)
            print(f"\n--- 签到报告 ({datetime.now().strftime('%H:%M:%S')}) ---")
            for n in names[1:]:
                mark = "✓ 已签到" if n in checked else "○ 未签到"
                print(f"  {mark}: {n}")
            print(f"  总计: {len(checked)}/{len(names)-1}\n")

    cap.release()
    cv2.destroyAllWindows()

    # 退出时打印汇总
    print("\n===== 签到结束 =====")
    records = _load_attendance(meeting_name)
    checked_names = set(r['name'] for r in records)
    print(f"总签到人数: {len(checked_names)}/{len(names) - 1}")
    for n in names[1:]:
        mark = "✓" if n in checked_names else "○"
        print(f"  {mark} {n}")
    print("=" * 20)
