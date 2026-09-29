"""课程管理模块 — 课程/学生管理、Facebank 构建"""

import json
import shutil
import numpy as np
from pathlib import Path
from datetime import datetime
from PIL import Image
import torch
from torchvision import transforms as trans
from model import l2_norm

PROJECT_ROOT = Path(__file__).resolve().parent.parent  # core/ 的上一级是项目根
COURSES_ROOT = PROJECT_ROOT / 'data' / 'courses'


def _course_path(name):
    return COURSES_ROOT / name


def _participants_path(name):
    return _course_path(name) / 'participants'


# ─── 会议管理 ─────────────────────────────────────────

def create_course(name, description=""):
    """创建新课程目录结构"""
    path = _course_path(name)
    if path.exists():
        raise FileExistsError(f"会议 '{name}' 已存在")
    (path / 'participants').mkdir(parents=True)
    info = {
        "name": name,
        "description": description,
        "created_at": datetime.now().isoformat(),
        "participant_count": 0
    }
    with open(path / 'meeting_info.json', 'w', encoding='utf-8') as f:
        json.dump(info, f, ensure_ascii=False, indent=2)
    return info


def delete_course(name):
    """删除课程（保留全局学生记录）"""
    path = _course_path(name)
    if not path.exists():
        raise FileNotFoundError(f"课程 '{name}' 不存在")
    # 先更新全局学生索引：移除该课程
    index = _load_students_index()
    changed = False
    for entry in index.values():
        if name in entry.get("courses", []):
            entry["courses"].remove(name)
            changed = True
    if changed:
        _save_students_index(index)
    # 再删除课程目录
    shutil.rmtree(path)


def list_courses():
    """列出所有会议及其基本信息"""
    if not COURSES_ROOT.exists():
        return []
    meetings = []
    for d in sorted(COURSES_ROOT.iterdir()):
        if d.is_dir():
            info_path = d / 'meeting_info.json'
            if info_path.exists():
                with open(info_path, 'r', encoding='utf-8') as f:
                    info = json.load(f)
            else:
                info = {"name": d.name, "description": ""}
            # 统计参与者
            participant_dir = d / 'participants'
            participants = [p.name for p in participant_dir.iterdir() if p.is_dir()] if participant_dir.exists() else []
            info['participant_count'] = len(participants)
            info['path'] = str(d)
            # 读取签到数据（数量）- 按活跃签到次数
            att_path = d / 'attendance.json'
            sessions_path = d / 'sessions.json'
            if att_path.exists():
                with open(att_path, 'r', encoding='utf-8') as f:
                    records = json.load(f)
                # 按活跃 session 过滤
                if sessions_path.exists():
                    try:
                        with open(sessions_path, 'r', encoding='utf-8') as sf:
                            sdata = json.load(sf)
                        active_id = sdata.get('active')
                        if active_id:
                            records = [r for r in records if r.get('session') == active_id]
                    except Exception:
                        pass
                info['checked_in'] = len(set(r['name'] for r in records))
            else:
                info['checked_in'] = 0
            meetings.append(info)
    return meetings


def load_course(name):
    """加载课程信息"""
    path = _course_path(name)
    if not path.exists():
        raise FileNotFoundError(f"会议 '{name}' 不存在")
    info_path = path / 'meeting_info.json'
    if info_path.exists():
        with open(info_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"name": name, "description": ""}


def get_course_status(course_name):
    """获取课程状态

    Returns: "upcoming" | "today" | "ongoing" | "finished" | "unknown"
    """
    info = load_meeting(course_name)
    meeting_date = info.get('meeting_date', '')
    deadline = info.get('checkin_deadline', '')

    if not meeting_date:
        return "unknown"

    now = datetime.now()
    try:
        md = datetime.strptime(meeting_date, '%Y-%m-%d')
        if md.date() < now.date():
            return "finished"
        if md.date() > now.date():
            return "upcoming"
        # 今天
        if deadline:
            try:
                parts = deadline.split(':')
                dl_h, dl_m = int(parts[0]), int(parts[1])
                deadline_dt = now.replace(hour=dl_h, minute=dl_m, second=0)
                if now > deadline_dt + __import__('datetime').timedelta(hours=2):
                    return "finished"
                return "today"
            except Exception:
                pass
        return "today"
    except (ValueError, TypeError):
        return "unknown"


def update_course(name, **kwargs):
    """更新课程信息（带字段验证）

    支持的字段:
        name, description, meeting_date, checkin_deadline, expected_attendees
    """
    allowed = {'description', 'meeting_date', 'checkin_deadline',
               'expected_attendees', 'name'}
    info = load_meeting(name)

    for key, val in kwargs.items():
        if key not in allowed:
            continue
        if key == 'meeting_date' and val:
            try:
                datetime.strptime(str(val), '%Y-%m-%d')
            except (ValueError, TypeError):
                raise ValueError("日期格式错误，请使用 YYYY-MM-DD 格式")
        if key == 'checkin_deadline' and val:
            try:
                parts = str(val).split(':')
                h, m = int(parts[0]), int(parts[1])
                if not (0 <= h < 24 and 0 <= m < 60):
                    raise ValueError
            except (ValueError, IndexError):
                raise ValueError("截止时间格式错误，请使用 HH:MM 格式")
        info[key] = val

    info_path = _course_path(name) / 'meeting_info.json'
    with open(info_path, 'w', encoding='utf-8') as f:
        json.dump(info, f, ensure_ascii=False, indent=2)
    return info


def rename_course(old_name, new_name):
    """重命名课程"""
    old_path = _course_path(old_name)
    if not old_path.exists():
        raise FileNotFoundError(f"会议 '{old_name}' 不存在")
    new_path = _course_path(new_name)
    if new_path.exists():
        raise FileExistsError(f"会议 '{new_name}' 已存在")
    old_path.rename(new_path)
    info = load_meeting(new_name)
    info['name'] = new_name
    info_path = new_path / 'meeting_info.json'
    with open(info_path, 'w', encoding='utf-8') as f:
        json.dump(info, f, ensure_ascii=False, indent=2)
    return info


def update_course_info(name, **kwargs):
    """更新课程信息字段"""
    info = load_meeting(name)
    info.update(kwargs)
    info_path = _course_path(name) / 'meeting_info.json'
    with open(info_path, 'w', encoding='utf-8') as f:
        json.dump(info, f, ensure_ascii=False, indent=2)


# ─── 参与者管理 ─────────────────────────────────────

def add_participant(course_name, person_name, image_path):
    """添加学生照片到课程"""
    pdir = _participants_path(course_name) / person_name
    pdir.mkdir(parents=True, exist_ok=True)
    src = Path(image_path)
    if not src.exists():
        raise FileNotFoundError(f"照片文件不存在: {image_path}")
    # 复制或移动？复制更安全
    ext = src.suffix if src.suffix else '.jpg'
    dst = pdir / f"{person_name}{ext}"
    shutil.copy2(str(src), str(dst))
    # 更新课程信息中的参与者数量
    count = len(list(pdir.parent.iterdir()))
    update_meeting_info(course_name, participant_count=count)
    return str(dst)


def add_participants_from_dir(course_name, src_dir):
    """批量添加参与者

    要求目录结构: src_dir/<person_name>/<photo>.jpg
    """
    src = Path(src_dir)
    if not src.exists():
        raise FileNotFoundError(f"源目录不存在: {src_dir}")
    added = []
    for person_dir in sorted(src.iterdir()):
        if not person_dir.is_dir():
            continue
        name = person_dir.name
        # 找第一张图片
        images = sorted(person_dir.glob('*'))
        images = [p for p in images if p.suffix.lower() in ('.jpg', '.jpeg', '.png', '.bmp')]
        if not images:
            continue
        add_participant(course_name, name, str(images[0]))
        added.append(name)
    return added


def take_participant_photo(course_name, person_name, mtcnn):
    """调用摄像头拍照注册参与者

    依赖 MTCNN 进行人脸对齐。
    按 t 拍照，按 q 退出。
    """
    import cv2
    pdir = _participants_path(course_name) / person_name
    pdir.mkdir(parents=True, exist_ok=True)

    cap = cv2.VideoCapture(0)
    cap.set(3, 1280)
    cap.set(4, 720)
    if not cap.isOpened():
        raise RuntimeError("摄像头打开失败")

    saved = False
    print(f"按 t 拍照注册 '{person_name}'，按 q 跳过...")
    while True:
        ret, frame = cap.read()
        if not ret:
            continue
        cv2.putText(frame, "Press t to take picture, q to quit...", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
        cv2.imshow('Register Face', frame)
        key = cv2.waitKey(1) & 0xFF
        if key == ord('t'):
            try:
                img = Image.fromarray(frame[..., ::-1])
                aligned = mtcnn.align(img)
                if aligned is None:
                    print("未检测到人脸，请重试")
                    continue
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                save_path = pdir / f"{timestamp}.jpg"
                aligned.save(save_path)
                print(f"照片已保存: {save_path}")
                saved = True
                break
            except Exception as e:
                print(f"拍照失败: {e}")
                continue
        elif key == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()
    if saved:
        count = len(list(pdir.parent.iterdir()))
        update_meeting_info(course_name, participant_count=count)
    return saved


def get_participants(course_name):
    """获取学生名单"""
    pdir = _participants_path(course_name)
    if not pdir.exists():
        return []
    participants = []
    for d in sorted(pdir.iterdir()):
        if d.is_dir():
            # 列出该参与者的照片
            photos = [str(p) for p in d.glob('*') if p.suffix.lower() in ('.jpg', '.jpeg', '.png', '.bmp')]
            participants.append({
                "name": d.name,
                "photo_count": len(photos),
                "photos": photos
            })
    return participants


def search_participants(course_name, query=""):
    """搜索参与者（含部门/电话元数据）"""
    all_p = update_participants_get(course_name)
    if not query:
        return all_p
    q = query.lower().strip()
    return [p for p in all_p if q in p['name'].lower()]


def export_participants_csv(course_name):
    """导出学生名单为 CSV（含部门/电话）"""
    import csv
    participants = update_participants_get(course_name)
    output_path = _course_path(course_name) / 'participants_list.csv'
    with open(output_path, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        writer.writerow(['姓名', '部门', '电话', '照片数量'])
        for p in participants:
            writer.writerow([p['name'], p.get('department',''),
                           p.get('phone',''), p['photo_count']])
    return str(output_path)


def rename_participant(course_name, old_name, new_name):
    """重命名参与者"""
    old_dir = _participants_path(course_name) / old_name
    if not old_dir.exists():
        raise FileNotFoundError(f"参与者 '{old_name}' 不存在")
    new_dir = _participants_path(course_name) / new_name
    if new_dir.exists():
        raise FileExistsError(f"参与者 '{new_name}' 已存在")
    old_dir.rename(new_dir)
    # 删除缓存的 facebank
    fb_path = _course_path(course_name) / 'facebank.pth'
    if fb_path.exists():
        fb_path.unlink()
    names_path = _course_path(course_name) / 'names.npy'
    if names_path.exists():
        names_path.unlink()
    return new_name


def remove_participant(course_name, person_name):
    """删除参与者"""
    pdir = _participants_path(course_name) / person_name
    if not pdir.exists():
        raise FileNotFoundError(f"参与者 '{person_name}' 不存在")
    shutil.rmtree(pdir)
    # 如果 facebank 存在，删除它（需要重建）
    fb_path = _course_path(course_name) / 'facebank.pth'
    if fb_path.exists():
        fb_path.unlink()
    names_path = _course_path(course_name) / 'names.npy'
    if names_path.exists():
        names_path.unlink()
    count = len(list(pdir.parent.iterdir()))
    update_meeting_info(course_name, participant_count=count)


def remove_participants_batch(course_name, names):
    """批量删除参与者"""
    removed = []
    for name in names:
        pdir = _participants_path(course_name) / name
        if pdir.exists():
            shutil.rmtree(pdir)
            removed.append(name)
    # 删除 facebank 缓存
    fb_path = _course_path(course_name) / 'facebank.pth'
    if fb_path.exists():
        fb_path.unlink()
    names_path = _course_path(course_name) / 'names.npy'
    if names_path.exists():
        names_path.unlink()
    count = len([d for d in _participants_path(course_name).iterdir() if d.is_dir()])
    update_meeting_info(course_name, participant_count=count)
    return removed


def add_participant_from_bytes(course_name, person_name, image_bytes, filename=None):
    """从字节数据添加参与者（用于 web 上传）"""
    pdir = _participants_path(course_name) / person_name
    pdir.mkdir(parents=True, exist_ok=True)
    ext = Path(filename).suffix if filename else '.jpg'
    if ext not in ('.jpg', '.jpeg', '.png', '.bmp'):
        ext = '.jpg'
    dst = pdir / f"{person_name}{ext}"
    with open(dst, 'wb') as f:
        f.write(image_bytes)
    count = len(list(pdir.parent.iterdir()))
    update_meeting_info(course_name, participant_count=count)
    return str(dst)


def add_participants_batch(course_name, items):
    """批量添加参与者

    Args:
        course_name: 课程名称
        items: [(person_name, image_bytes, filename), ...]

    Returns:
        [成功添加的姓名]
    """
    added = []
    for name, img_bytes, fname in items:
        try:
            add_participant_from_bytes(course_name, name, img_bytes, fname)
            added.append(name)
        except Exception as e:
            print(f"添加 {name} 失败: {e}")
    return added


# ─── 学生元数据与班级管理 ─────────────────────────

def _meta_path(course_name):
    """学生元数据文件路径"""
    return _course_path(course_name) / 'participants_meta.json'


def _load_meta(course_name):
    """加载学生元数据"""
    path = _meta_path(course_name)
    if path.exists():
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def _save_meta(course_name, meta):
    """保存学生元数据"""
    path = _meta_path(course_name)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)


def set_participant_meta(course_name, person_name, **kwargs):
    """设置学生元数据（部门、电话等）

    Args:
        course_name: 课程名称
        person_name: 参与者姓名
        **kwargs: 支持 phone, department 字段
    """
    meta = _load_meta(course_name)
    if person_name not in meta:
        meta[person_name] = {"name": person_name, "phone": "", "department": ""}
    for key in ('phone', 'department'):
        if key in kwargs:
            meta[person_name][key] = str(kwargs[key] or '')
    _save_meta(course_name, meta)
    return meta[person_name]


def get_participant_meta(course_name, person_name):
    """获取单个学生元数据"""
    meta = _load_meta(course_name)
    return meta.get(person_name, {"name": person_name, "phone": "", "department": ""})


def get_all_participant_meta(course_name):
    """获取所有学生元数据"""
    return _load_meta(course_name)


def get_participants_by_department(course_name):
    """按班级分组获取学生"""
    meta = _load_meta(course_name)
    groups = {}
    for name, info in meta.items():
        dept = info.get('department', '') or '未分组'
        if dept not in groups:
            groups[dept] = []
        groups[dept].append(info)
    return groups


# ─── 班级管理 ────────────────────────────────────

def _dept_path(course_name):
    return _course_path(course_name) / 'departments.json'


def list_departments(course_name):
    """获取班级列表"""
    path = _dept_path(course_name)
    if path.exists():
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    # 从元数据中提取已有部门
    meta = _load_meta(course_name)
    depts = set()
    for info in meta.values():
        if info.get('department'):
            depts.add(info['department'])
    return sorted(depts)


def add_department(course_name, dept_name):
    """添加班级"""
    depts = list_departments(course_name)
    if dept_name in depts:
        raise ValueError(f"部门 '{dept_name}' 已存在")
    depts.append(dept_name)
    path = _dept_path(course_name)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(sorted(depts), f, ensure_ascii=False, indent=2)
    return sorted(depts)


def remove_department(course_name, dept_name):
    """删除班级（不删除参与者，只清除部门标记）"""
    depts = list_departments(course_name)
    if dept_name not in depts:
        raise ValueError(f"部门 '{dept_name}' 不存在")
    depts.remove(dept_name)
    path = _dept_path(course_name)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(sorted(depts), f, ensure_ascii=False, indent=2)
    # 清除该部门下所有参与者的部门标记
    meta = _load_meta(course_name)
    changed = False
    for info in meta.values():
        if info.get('department') == dept_name:
            info['department'] = ''
            changed = True
    if changed:
        _save_meta(course_name, meta)
    return sorted(depts)


def update_participants_get(course_name):
    """增强版 get_participants：合并元数据"""
    parts = get_participants(course_name)
    meta = _load_meta(course_name)
    for p in parts:
        m = meta.get(p['name'], {})
        p['phone'] = m.get('phone', '')
        p['department'] = m.get('department', '')
    return parts


# ─── 预期签到学生管理 ──────────────────────────────

def get_expected_participants(course_name):
    """获取预期签到学生名单

    如果未设置，默认返回所有已注册参与者
    """
    info = load_meeting(course_name)
    expected = info.get('expected_attendees')
    # 如果设置了但为空列表，视为"未设置"，回退到全部参与者
    if expected is not None and len(expected) > 0:
        return expected
    # 默认：所有注册参与者
    participants = get_participants(course_name)
    return [p['name'] for p in participants]


def set_expected_participants(course_name, names):
    """设置预期签到学生名单"""
    update_meeting_info(course_name, expected_attendees=list(names))
    return names


# ─── 签到截止时间管理 ──────────────────────────────

def set_checkin_deadline(course_name, deadline_str):
    """设置签到截止时间

    Args:
        course_name: 课程名称
        deadline_str: 截止时间 "HH:MM" 格式，例如 "09:00"
                      设为 None 或 "" 表示取消截止时间
    """
    if deadline_str:
        # 验证格式
        try:
            parts = deadline_str.strip().split(':')
            h, m = int(parts[0]), int(parts[1])
            if not (0 <= h < 24 and 0 <= m < 60):
                raise ValueError
            formatted = f"{h:02d}:{m:02d}"
        except (ValueError, IndexError):
            raise ValueError("截止时间格式错误，请使用 HH:MM 格式，例如 09:00")
    else:
        formatted = None
    update_meeting_info(course_name, checkin_deadline=formatted)
    return formatted


def get_checkin_deadline(course_name):
    """获取签到截止时间"""
    info = load_meeting(course_name)
    return info.get('checkin_deadline')


def is_late(course_name, checkin_time_str):
    """判断签到时间是否迟到

    Args:
        course_name: 课程名称
        checkin_time_str: 签到时间 ISO 格式字符串

    Returns:
        (bool, int) — (是否迟到, 迟到分钟数)
    """
    deadline = get_checkin_deadline(course_name)
    if not deadline:
        return False, 0  # 未设置截止时间
    try:
        from datetime import datetime
        t = datetime.fromisoformat(checkin_time_str)
        dl_h, dl_m = map(int, deadline.split(':'))
        deadline_dt = t.replace(hour=dl_h, minute=dl_m, second=0, microsecond=0)
        if t > deadline_dt:
            late_min = int((t - deadline_dt).total_seconds() / 60)
            return True, late_min
        return False, 0
    except Exception:
        return False, 0


# ─── Facebank 构建 ──────────────────────────────────

def build_facebank(course_name, model, mtcnn, conf, tta=True):
    """构建会议参与者的人脸特征库

    遍历 participants 目录，对每张照片提取特征并平均，保存 facebank.pth 和 names.npy。
    与 utils.prepare_facebank 逻辑一致，但路径不同。

    Args:
        course_name: 课程名称
        model: MobileFaceNet 或 Backbone 模型（eval 模式）
        mtcnn: MTCNN 检测器
        conf: 配置（含 test_transform、device）
        tta: 是否使用测试时增强

    Returns:
        (embeddings, names) 特征张量和姓名数组
    """
    model.eval()
    pdir = _participants_path(course_name)
    if not pdir.exists():
        raise FileNotFoundError(f"参与者目录不存在: {pdir}")

    embeddings_list = []
    names = ['Unknown']

    for person_dir in sorted(pdir.iterdir()):
        if not person_dir.is_dir():
            continue
        name = person_dir.name
        embs = []
        images = sorted(person_dir.glob('*'))
        images = [p for p in images if p.suffix.lower() in ('.jpg', '.jpeg', '.png', '.bmp')]
        if not images:
            continue
        for img_path in images:
            try:
                img = Image.open(img_path)
            except Exception:
                continue
            if img.size != (112, 112):
                try:
                    img = mtcnn.align(img)
                except Exception:
                    continue
                if img is None:
                    continue
            with torch.no_grad():
                if tta:
                    mirror = trans.functional.hflip(img)
                    emb = model(conf.test_transform(img).to(conf.device).unsqueeze(0))
                    emb_mirror = model(conf.test_transform(mirror).to(conf.device).unsqueeze(0))
                    embs.append(l2_norm(emb + emb_mirror))
                else:
                    embs.append(model(conf.test_transform(img).to(conf.device).unsqueeze(0)))
        if not embs:
            continue
        embedding = torch.cat(embs).mean(0, keepdim=True)
        embeddings_list.append(embedding)
        names.append(name)

    if not embeddings_list:
        # 没有参与者，返回空
        embeddings = torch.empty((0, conf.embedding_size), device=conf.device)
        names_arr = np.array(names)
    else:
        embeddings = torch.cat(embeddings_list)
        names_arr = np.array(names)

    # 保存到课程目录
    meeting_path = _course_path(course_name)
    torch.save(embeddings, meeting_path / 'facebank.pth')
    np.save(meeting_path / 'names', names_arr)

    print(f"特征库已构建: {len(embeddings_list)} 人")
    return embeddings, names_arr


# ═══════════════════════════════════════════
# 班级特征库 — 按班级构建，课程关联后直接使用
# ═══════════════════════════════════════════

CLASS_FACEBANK_ROOT = PROJECT_ROOT / 'data' / 'class_faces'


def _class_facebank_path(class_name):
    """中文班级名转 ASCII 安全路径（PyTorch 不支持中文路径）"""
    import hashlib
    safe = hashlib.md5(class_name.encode('utf-8')).hexdigest()[:12]
    return CLASS_FACEBANK_ROOT / safe


def _class_facebank_name_map():
    """读取/保存班级名映射"""
    path = CLASS_FACEBANK_ROOT / '_names.json'
    if path.exists():
        import json
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def _save_class_facebank_name(class_name, safe_name):
    import json
    mapping = _class_facebank_name_map()
    mapping[safe_name] = class_name
    path = CLASS_FACEBANK_ROOT / '_names.json'
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(mapping, f, ensure_ascii=False, indent=2)


def build_class_facebank(class_name, model, mtcnn, conf, tta=True):
    """为班级构建特征库（从全局学生照片提取）"""
    base = _class_facebank_path(class_name)
    pdir = base.parent / base.name  # CLASS_FACEBANK_ROOT / {safe_hash}
    pdir.mkdir(parents=True, exist_ok=True)
    _save_class_facebank_name(class_name, base.name)

    students = get_global_students_by_class(class_name)
    if not students:
        raise ValueError(f"班级 '{class_name}' 没有学生")

    model.eval()
    embeddings_list = []
    names = ['Unknown']

    for sname in students:
        # 从全局照片目录找照片
        src_photo = None
        for ext in ['.jpg', '.jpeg', '.png', '.bmp']:
            gp = PROJECT_ROOT / 'data' / 'students' / 'photos' / f"{sname}{ext}"
            if gp.exists():
                src_photo = str(gp)
                break
        if not src_photo:
            continue

        embs = []
        try:
            img = Image.open(src_photo)
        except Exception:
            continue

        if img.size != (112, 112):
            try:
                img = mtcnn.align(img)
            except Exception:
                continue
            if img is None:
                continue

        with torch.no_grad():
            if tta:
                mirror = trans.functional.hflip(img)
                emb = model(conf.test_transform(img).to(conf.device).unsqueeze(0))
                emb_mirror = model(conf.test_transform(mirror).to(conf.device).unsqueeze(0))
                embs.append(l2_norm(emb + emb_mirror))
            else:
                embs.append(model(conf.test_transform(img).to(conf.device).unsqueeze(0)))

        if not embs:
            continue
        embedding = torch.cat(embs).mean(0, keepdim=True)
        embeddings_list.append(embedding)
        names.append(sname)

    if not embeddings_list:
        embeddings = torch.empty((0, conf.embedding_size), device=conf.device)
        names_arr = np.array(names)
    else:
        embeddings = torch.cat(embeddings_list)
        names_arr = np.array(names)

    torch.save(embeddings, pdir / 'facebank.pth')
    np.save(pdir / 'names', names_arr)
    print(f"班级特征库已构建: {len(embeddings_list)} 人 ({class_name})")
    return embeddings, names_arr


def get_class_facebank(class_name):
    """加载班级特征库"""
    base = _class_facebank_path(class_name)
    pdir = base.parent / base.name
    fb_path = pdir / 'facebank.pth'
    names_path = pdir / 'names.npy'
    if not fb_path.exists() or not names_path.exists():
        return None, None
    return torch.load(fb_path), np.load(names_path)


def get_course_facebanks(course_name):
    """获取课程关联的所有班级特征库（合并为一个）"""
    classes = course_get_classes(course_name)
    all_embs = []
    all_names = ['Unknown']
    for cn in classes:
        embs, names = get_class_facebank(cn)
        if embs is not None and embs.shape[0] > 0:
            all_embs.append(embs)
            all_names.extend(list(names[1:]))
    if not all_embs:
        return torch.empty((0, 512)), np.array(all_names)
    return torch.cat(all_embs), np.array(all_names)


# ═══════════════════════════════════════════
# 签到码管理 — 人脸识别失败时的兜底方案
# ═══════════════════════════════════════════

def _checkin_codes_path(course_name):
    """签到码文件路径"""
    return _course_path(course_name) / 'checkin_codes.json'


def _load_checkin_codes(course_name):
    """加载签到码映射 {code: name}"""
    path = _checkin_codes_path(course_name)
    if not path.exists():
        return {}
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}


def _save_checkin_codes(course_name, codes):
    """保存签到码映射"""
    path = _checkin_codes_path(course_name)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(codes, f, ensure_ascii=False, indent=2)


def _generate_unique_code(existing_codes):
    """生成不重复的4位数字码"""
    import random
    existing = set(existing_codes)
    for _ in range(100):
        code = f"{random.randint(1000, 9999)}"
        if code not in existing:
            return code
    # 极端情况：全占满，用5位
    for _ in range(100):
        code = f"{random.randint(10000, 99999)}"
        if code not in existing:
            return code
    raise RuntimeError("无法生成唯一签到码（所有号码已用完）")


def get_checkin_code(course_name, person_name):
    """获取参与者的签到码（不存在则自动生成）

    Returns:
        str: 4位数字码
    """
    codes = _load_checkin_codes(course_name)
    # 按姓名查找（值匹配）
    for code, name in codes.items():
        if name == person_name:
            return code
    # 不存在则生成
    code = _generate_unique_code(codes.keys())
    codes[code] = person_name
    _save_checkin_codes(course_name, codes)
    return code


def get_all_checkin_codes(course_name):
    """获取所有签到码映射 {code: name}"""
    return _load_checkin_codes(course_name)


def verify_checkin_code(course_name, code):
    """通过签到码查询参与者姓名

    Args:
        course_name: 课程名称
        code: 4位数字码

    Returns:
        str or None: 参与者姓名，未找到返回 None
    """
    codes = _load_checkin_codes(course_name)
    return codes.get(code.strip())


def checkin_by_code(course_name, code):
    """通过签到码签到

    Args:
        course_name: 课程名称
        code: 4位数字码

    Returns:
        dict or None: 签到记录，码无效返回 None
    """
    name = verify_checkin_code(course_name, code)
    if not name:
        return None
    from checkin import record_checkin
    return record_checkin(course_name, name, -1)


def reset_checkin_code(course_name, person_name):
    """重置某人的签到码"""
    codes = _load_checkin_codes(course_name)
    # 删除旧的
    to_del = [k for k, v in codes.items() if v == person_name]
    for k in to_del:
        del codes[k]
    # 生成新的
    new_code = _generate_unique_code(codes.keys())
    codes[new_code] = person_name
    _save_checkin_codes(course_name, codes)
    return new_code


def batch_generate_codes(course_name):
    """为所有尚未分配签到码的参与者生成码"""
    participants = get_participants(course_name)
    codes = _load_checkin_codes(course_name)
    names_with_codes = set(codes.values())
    changed = False
    for p in participants:
        if p['name'] not in names_with_codes:
            code = _generate_unique_code(codes.keys())
            codes[code] = p['name']
            names_with_codes.add(p['name'])
            changed = True
    if changed:
        _save_checkin_codes(course_name, codes)
    return codes


# ═══════════════════════════════════════════
# 全局学生索引 — 跨课程身份
# ═══════════════════════════════════════════

STUDENTS_INDEX_PATH = PROJECT_ROOT / 'data' / 'students_index.json'


def _load_students_index():
    """加载全局学生索引"""
    if STUDENTS_INDEX_PATH.exists():
        with open(STUDENTS_INDEX_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def _save_students_index(index):
    """保存全局学生索引"""
    STUDENTS_INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(STUDENTS_INDEX_PATH, 'w', encoding='utf-8') as f:
        json.dump(index, f, ensure_ascii=False, indent=2)


def sync_student_to_global(name, class_name="", course_name="", phone=""):
    """同步学生到全局索引

    每次添加学生到课程时调用（自助注册或管理员添加）。
    学生存在则更新班级/电话/课程列表，不存在则创建新条目。

    Args:
        name: 学生姓名
        class_name: 所属班级
        course_name: 报名的课程名
        phone: 电话
    """
    index = _load_students_index()
    if name not in index:
        index[name] = {
            "name": name,
            "class": class_name,
            "phone": phone,
            "created_at": datetime.now().isoformat(),
            "courses": [],
            "photo_count": 0
        }
    entry = index[name]
    if class_name:
        entry["class"] = class_name
    if phone:
        entry["phone"] = phone
    if course_name and course_name not in entry["courses"]:
        entry["courses"].append(course_name)
    _save_students_index(index)
    return entry


def get_global_students_by_class(class_name):
    """获取某班级的所有学生（从全局索引）"""
    index = _load_students_index()
    return {n: d for n, d in index.items() if d.get("class") == class_name}


def get_all_global_classes():
    """获取全局所有班级名（去重排序）"""
    index = _load_students_index()
    classes = set()
    for entry in index.values():
        if entry.get("class"):
            classes.add(entry["class"])
    return sorted(classes)


def batch_enroll_students(course_name, student_names):
    """将已有全局记录的学生批量加入课程

    遍历每个学生名：
    1. 如果目标课程已有该学生 → 跳过
    2. 如果学生已在其他课程有照片 → 复制到目标课程
    3. 否则创建空目录占位
    4. 更新全局索引中的课程列表

    Args:
        course_name: 目标课程名
        student_names: 学生姓名列表

    Returns:
        [成功操作的学生姓名]
    """
    added = []
    index = _load_students_index()
    for name in student_names:
        if name not in index:
            continue
        # 检查目标课程是否已有该学生
        pdir = _participants_path(course_name) / name
        if pdir.exists():
            added.append(name)
            continue
        # 从其他课程找该学生的照片
        src_photo = None
        for enrolled_course in index[name].get("courses", []):
            candidate = _participants_path(enrolled_course) / name
            if candidate.exists():
                photos = [p for p in candidate.glob('*')
                          if p.suffix.lower() in ('.jpg', '.jpeg', '.png')]
                if photos:
                    src_photo = photos[0]
                    break
        if src_photo:
            add_participant(course_name, name, str(src_photo))
            # 同步班级到目标课程的元数据
            if index[name].get("class"):
                set_participant_meta(course_name, name,
                                     department=index[name]["class"])
        else:
            # 检查全局学生照片目录
            global_photo = None
            for ext in ['.jpg', '.jpeg', '.png', '.bmp']:
                gp = PROJECT_ROOT / 'data' / 'students' / 'photos' / f"{name}{ext}"
                if gp.exists():
                    global_photo = str(gp)
                    break
            if global_photo:
                add_participant(course_name, name, str(global_photo))
                if index[name].get("class"):
                    set_participant_meta(course_name, name,
                                         department=index[name]["class"])
            else:
                # 没有照片，只创建目录占位
                pdir.mkdir(parents=True, exist_ok=True)
        # 更新全局索引中的课程列表
        if course_name not in index[name]["courses"]:
            index[name]["courses"].append(course_name)
        added.append(name)
    _save_students_index(index)
    return added


# ═══════════════════════════════════════════
# 全局班级管理 — 班级独立于课程存在
# ═══════════════════════════════════════════

GLOBAL_CLASSES_PATH = PROJECT_ROOT / 'data' / 'classes.json'


def _load_global_classes():
    """加载全局班级列表"""
    if GLOBAL_CLASSES_PATH.exists():
        with open(GLOBAL_CLASSES_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []


def _save_global_classes(classes):
    """保存全局班级列表"""
    GLOBAL_CLASSES_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(GLOBAL_CLASSES_PATH, 'w', encoding='utf-8') as f:
        json.dump(classes, f, ensure_ascii=False, indent=2)


def add_global_class(name):
    """创建全局班级"""
    classes = _load_global_classes()
    if name in classes:
        raise ValueError(f"班级 '{name}' 已存在")
    classes.append(name)
    _save_global_classes(sorted(classes))
    return classes


def remove_global_class(name):
    """删除全局班级（同时清除关联数据）"""
    classes = _load_global_classes()
    if name not in classes:
        raise ValueError(f"班级 '{name}' 不存在")
    classes.remove(name)
    _save_global_classes(classes)

    # 从全局学生索引中清除该班级
    index = _load_students_index()
    changed = False
    for entry in index.values():
        if entry.get("class") == name:
            entry["class"] = ""
            changed = True
    if changed:
        _save_students_index(index)

    # 从所有课程的 participants_meta 中清除
    for d in COURSES_ROOT.iterdir():
        if d.is_dir():
            meta_path = d / 'participants_meta.json'
            if meta_path.exists():
                with open(meta_path, 'r', encoding='utf-8') as f:
                    meta = json.load(f)
                changed = False
                for info in meta.values():
                    if info.get('department') == name:
                        info['department'] = ''
                        changed = True
                if changed:
                    with open(meta_path, 'w', encoding='utf-8') as f:
                        json.dump(meta, f, ensure_ascii=False, indent=2)

    # 从所有课程的 meeting_info 中移除关联
    for d in COURSES_ROOT.iterdir():
        if d.is_dir():
            info_path = d / 'meeting_info.json'
            if info_path.exists():
                with open(info_path, 'r', encoding='utf-8') as f:
                    info = json.load(f)
                if 'classes' in info and name in info['classes']:
                    info['classes'].remove(name)
                    with open(info_path, 'w', encoding='utf-8') as f:
                        json.dump(info, f, ensure_ascii=False, indent=2)

    return classes


def course_get_classes(course_name):
    """获取课程关联的班级列表"""
    info = load_meeting(course_name)
    return info.get('classes', [])


def course_set_classes(course_name, class_names):
    """设置课程关联的班级（自动添加/移除学生）"""
    info = load_meeting(course_name)
    old_classes = set(info.get('classes', []))
    new_classes = set(class_names)

    # 新增的班级：把该班级所有学生加入课程
    added = new_classes - old_classes
    for cn in added:
        students = get_global_students_by_class(cn)
        if students:
            batch_enroll_students(course_name, list(students.keys()))

    # 移除的班级：把该班级所有学生移出课程（保留照片和全局记录）
    removed = old_classes - new_classes
    for cn in removed:
        students = get_global_students_by_class(cn)
        for sname in students:
            # 从全局索引移除课程
            index = _load_students_index()
            if sname in index and course_name in index[sname].get("courses", []):
                index[sname]["courses"].remove(course_name)
                _save_students_index(index)
            # 从课程元数据移除（保留照片目录不删除）
            meta_path = _course_path(course_name) / 'participants_meta.json'
            if meta_path.exists():
                try:
                    meta = json.loads(meta_path.read_text(encoding='utf-8'))
                    if sname in meta:
                        del meta[sname]
                    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding='utf-8')
                except Exception:
                    pass

    info['classes'] = sorted(class_names)
    info_path = _course_path(course_name) / 'meeting_info.json'
    with open(info_path, 'w', encoding='utf-8') as f:
        json.dump(info, f, ensure_ascii=False, indent=2)
    return info['classes']


# ═══════════════════════════════════════════
# 签到次数管理（同一课程可多次签到）
# ═══════════════════════════════════════════

def _sessions_path(course_name):
    return _course_path(course_name) / 'sessions.json'


def _load_sessions(course_name):
    path = _sessions_path(course_name)
    if path.exists():
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"sessions": [], "active": None}


def _save_sessions(course_name, data):
    path = _sessions_path(course_name)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def create_session(course_name, name=None):
    """创建新签到次数"""
    data = _load_sessions(course_name)
    sess_id = str(len(data['sessions']) + 1)
    if not name:
        name = f"第{sess_id}次签到"
    now = datetime.now().isoformat()[:16]
    session = {"id": sess_id, "name": name, "created_at": now}
    data['sessions'].append(session)
    data['active'] = sess_id
    _save_sessions(course_name, data)
    return session


def get_active_session(course_name):
    """获取当前活跃的签到次数"""
    data = _load_sessions(course_name)
    if data['active'] and data['sessions']:
        for s in data['sessions']:
            if s['id'] == data['active']:
                return s
    # 没有活跃次数则自动创建第一次
    return create_session(course_name)


def switch_session(course_name, session_id):
    """切换活跃签到次数"""
    data = _load_sessions(course_name)
    if not any(s['id'] == session_id for s in data['sessions']):
        raise ValueError(f"签到次数 '{session_id}' 不存在")
    data['active'] = session_id
    _save_sessions(course_name, data)
    return next(s for s in data['sessions'] if s['id'] == session_id)


def list_sessions(course_name):
    """列出所有签到次数"""
    data = _load_sessions(course_name)
    return data['sessions'], data['active']


def end_active_session(course_name):
    """结束当前活跃的签到次数"""
    data = _load_sessions(course_name)
    old_active = data.get('active')
    data['active'] = None
    _save_sessions(course_name, data)
    return old_active


# ═══════════════════════════════════════════
# 向后兼容别名
# ═══════════════════════════════════════════

create_meeting = create_course
delete_meeting = delete_course
list_meetings = list_courses
load_meeting = load_course
get_meeting_status = get_course_status
update_meeting = update_course
rename_meeting = rename_course
update_meeting_info = update_course_info
MEETINGS_ROOT = COURSES_ROOT
_meeting_path = lambda n: COURSES_ROOT / n
