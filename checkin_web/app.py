"""人脸识别会议签到系统 — Flask Web 应用"""

import sys
import os
import json
import time

# 将项目根目录和 core/ 加入 path
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DATA_ROOT = os.path.join(_PROJECT_ROOT, 'data')
sys.path.insert(0, _PROJECT_ROOT)
sys.path.insert(0, os.path.join(_PROJECT_ROOT, 'core'))
# 切换到 core/ 目录（MTCNN 权重路径基于此）
os.chdir(os.path.join(_PROJECT_ROOT, 'core'))

from pathlib import Path
from flask import (Flask, render_template, jsonify, request, send_file,
                   Response, redirect)
from flask_cors import CORS

# 显式指定模板和静态文件路径（解决直接运行时路径不对的问题）
_APP_ROOT = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__,
            template_folder=os.path.join(_APP_ROOT, 'templates'),
            static_folder=os.path.join(_APP_ROOT, 'static'))
app.secret_key = os.environ.get('FLASK_SECRET_KEY') or os.urandom(32)
CORS(app)

from config import get_config
from mtcnn import MTCNN
from Learner import face_learner
import course as meeting
import report as report_mod
import checkin as checkin_mod
from checkin_web.camera import get_camera_manager, _open_camera

# 语音播报（可选）
try:
    from checkin_web.speaker import say_checkin as _say_checkin
except Exception:
    _say_checkin = None

# 全局模型实例（懒加载）
_models_loaded = False
_mtcnn = None
_learner = None
_conf = None


def _get_conf():
    global _conf
    if _conf is None:
        _conf = get_config(False)
        # 修正路径为绝对路径（CWD 可能不是项目根目录）
        _conf.work_path = Path(_PROJECT_ROOT) / 'work_space'
        _conf.model_path = _conf.work_path / 'models'
        _conf.save_path = _conf.work_path / 'save'
        # 提高人脸检测上限
        _conf.face_limit = 50
        _conf.min_face_size = 20
        # 识别阈值（距离越小越严格，1.0 可有效防止误签）
        _conf.threshold = 1.0
    return _conf


def _load_models():
    global _models_loaded, _mtcnn, _learner
    if _models_loaded:
        return _mtcnn, _learner
    conf = _get_conf()
    print("正在加载 MTCNN...")
    _mtcnn = MTCNN()
    print("正在加载人脸识别模型...")
    _learner = face_learner(conf, inference=True)
    _learner.threshold = conf.threshold
    _learner.load_state(conf, 'mobilefacenet.pth', True, True)
    _learner.model.eval()
    _models_loaded = True
    print("模型加载完成")
    return _mtcnn, _learner


# ─── 页面路由 ──────────────────────────────────────

@app.route('/')
def dashboard():
    return render_template('admin.html')


@app.route('/registration')
def registration_admin():
    """自助注册管理独立页面"""
    return render_template('registration_admin.html')


@app.route('/meeting/<name>')
def meeting_detail(name):
    return render_template('meeting_detail.html', meeting_name=name)


@app.route('/report/<name>')
def report_page(name):
    return render_template('report.html', meeting_name=name)


# ─── API: 会议管理 ─────────────────────────────────

@app.route('/api/meetings', methods=['GET'])
def api_list_meetings():
    meetings = meeting.list_meetings()
    return jsonify(meetings)


@app.route('/api/meetings', methods=['POST'])
def api_create_meeting():
    data = request.get_json()
    name = data.get('name', '').strip()
    if not name:
        return jsonify({"error": "会议名称不能为空"}), 400
    desc = data.get('description', '').strip()
    try:
        info = meeting.create_meeting(name, desc)
        return jsonify(info), 201
    except FileExistsError as e:
        return jsonify({"error": str(e)}), 409
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/meeting/<name>', methods=['GET'])
def api_get_meeting(name):
    try:
        info = meeting.load_meeting(name)
        participants = meeting.get_participants(name)
        # 签到统计
        try:
            stats = report_mod.get_statistics(name)
            info.update(stats)
        except Exception:
            info['checked_in'] = 0
        info['participants'] = participants
        # 用实际参与者目录数量覆盖 facebank 数量（避免未重建导致不一致）
        info['total_participants'] = len(participants)
        info['participant_count'] = len(participants)
        # 预期人数如果为 0 也回退到实际人数
        if info.get('expected_count', 0) == 0:
            info['expected_count'] = len(participants)
        return jsonify(info)
    except FileNotFoundError:
        return jsonify({"error": f"会议 '{name}' 不存在"}), 404


@app.route('/api/meeting/<name>', methods=['PUT'])
def api_update_meeting(name):
    """更新会议信息"""
    data = request.get_json()
    try:
        info = meeting.update_meeting(name, **data)
        return jsonify(info)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/meeting/<name>', methods=['DELETE'])
def api_delete_meeting(name):
    try:
        meeting.delete_meeting(name)
        return jsonify({"success": True})
    except FileNotFoundError as e:
        return jsonify({"error": str(e)}), 404


@app.route('/api/meeting/<name>/rename', methods=['POST'])
def api_rename_meeting(name):
    """重命名会议"""
    data = request.get_json()
    new_name = data.get('new_name', '').strip()
    if not new_name:
        return jsonify({"error": "新名称不能为空"}), 400
    try:
        info = meeting.rename_meeting(name, new_name)
        return jsonify({"success": True, "info": info})
    except (FileNotFoundError, FileExistsError) as e:
        return jsonify({"error": str(e)}), 400


# ─── API: 参与者管理 ───────────────────────────────

@app.route('/api/meeting/<name>/participants', methods=['GET'])
def api_get_participants(name):
    try:
        participants = meeting.update_participants_get(name)
        return jsonify(participants)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/meeting/<name>/participants', methods=['POST'])
def api_add_participant(name):
    person_name = request.form.get('name', '').strip()
    if not person_name:
        return jsonify({"error": "姓名不能为空"}), 400

    if 'photo' in request.files:
        # 上传照片
        photo = request.files['photo']
        if photo.filename:
            # 保存到临时位置
            tmp_dir = Path(_DATA_ROOT) / 'tmp'
            tmp_dir.mkdir(exist_ok=True)
            tmp_path = tmp_dir / photo.filename
            photo.save(str(tmp_path))
            try:
                result = meeting.add_participant(name, person_name, str(tmp_path))
                if tmp_path.exists(): tmp_path.unlink()
                # 同步到全局学生索引
                class_name = request.form.get('class_name', '')
                meeting.sync_student_to_global(person_name, class_name=class_name, course_name=name)
                if class_name:
                    meeting.set_participant_meta(name, person_name, department=class_name)
                return jsonify({"success": True, "path": result}), 201
            except Exception as e:
                if tmp_path.exists(): tmp_path.unlink()
                return jsonify({"error": str(e)}), 500
        else:
            return jsonify({"error": "请选择照片文件"}), 400
    else:
        # 可能是在线拍照（data URL）
        data_url = request.form.get('photo_data', '')
        if data_url:
            import base64
            try:
                header, encoded = data_url.split(',', 1)
                img_data = base64.b64decode(encoded)
                tmp_dir = Path(_DATA_ROOT) / 'tmp'
                tmp_dir.mkdir(exist_ok=True)
                tmp_path = tmp_dir / f"{person_name}_{int(__import__('time').time())}.jpg"
                with open(tmp_path, 'wb') as f:
                    f.write(img_data)
                result = meeting.add_participant(name, person_name, str(tmp_path))
                # 同步到全局学生索引
                meeting.sync_student_to_global(person_name, course_name=name)
                return jsonify({"success": True, "path": result}), 201
            except Exception as e:
                return jsonify({"error": str(e)}), 500

    return jsonify({"error": "缺少照片数据"}), 400


@app.route('/api/meeting/<name>/participants/<person>', methods=['DELETE'])
def api_remove_participant(name, person):
    try:
        meeting.remove_participant(name, person)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/meeting/<name>/participants/batch', methods=['POST'])
def api_batch_add_participants(name):
    """批量添加参与者（支持多文件上传，文件名=姓名）"""
    files = request.files.getlist('photos')
    if not files:
        return jsonify({"error": "请选择照片文件"}), 400

    items = []
    errors = []
    for f in files:
        if not f.filename:
            continue
        # 从文件名提取姓名（去掉扩展名）
        stem = Path(f.filename).stem
        img_bytes = f.read()
        items.append((stem, img_bytes, f.filename))

    if not items:
        return jsonify({"error": "没有有效的文件"}), 400

    added = meeting.add_participants_batch(name, items)
    # 同步到全局学生索引
    for sname in added:
        meeting.sync_student_to_global(sname, course_name=name)
    return jsonify({"success": True, "added": added, "count": len(added)}), 201


@app.route('/api/meeting/<name>/participants/batch-delete', methods=['POST'])
def api_batch_delete_participants(name):
    """批量删除参与者"""
    data = request.get_json()
    names = data.get('names', [])
    if not names:
        return jsonify({"error": "请指定要删除的参与者"}), 400
    removed = meeting.remove_participants_batch(name, names)
    return jsonify({"success": True, "removed": removed})


@app.route('/api/meeting/<name>/participants/search', methods=['GET'])
def api_search_participants(name):
    """搜索参与者"""
    query = request.args.get('q', '')
    try:
        results = meeting.search_participants(name, query)
        return jsonify(results)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/meeting/<name>/participants/<person>/rename', methods=['POST'])
def api_rename_participant(name, person):
    """重命名参与者"""
    data = request.get_json()
    new_name = data.get('new_name', '').strip()
    if not new_name:
        return jsonify({"error": "新名称不能为空"}), 400
    try:
        meeting.rename_participant(name, person, new_name)
        return jsonify({"success": True, "new_name": new_name})
    except (FileNotFoundError, FileExistsError) as e:
        return jsonify({"error": str(e)}), 400


@app.route('/api/meeting/<name>/participants/export', methods=['GET'])
def api_export_participants(name):
    """导出参与者名单"""
    try:
        path = meeting.export_participants_csv(name)
        return send_file(path, mimetype='text/csv',
                         as_attachment=True,
                         download_name=f'{name}_参与者名单.csv')
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/meeting/<name>/participants/meta', methods=['GET'])
def api_get_participants_meta(name):
    """获取所有参与者元数据"""
    try:
        meta = meeting.get_all_participant_meta(name)
        return jsonify(meta)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/meeting/<name>/participants/meta', methods=['POST'])
def api_set_participant_meta(name):
    """设置参与者元数据"""
    data = request.get_json()
    person_name = data.get('name', '').strip()
    if not person_name:
        return jsonify({"error": "姓名不能为空"}), 400
    try:
        result = meeting.set_participant_meta(
            name, person_name,
            phone=data.get('phone', ''),
            department=data.get('department', '')
        )
        return jsonify({"success": True, "data": result})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/meeting/<name>/participants/by-department', methods=['GET'])
def api_get_participants_by_department(name):
    """按部门分组获取参与者"""
    try:
        groups = meeting.get_participants_by_department(name)
        return jsonify(groups)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/meeting/<name>/departments', methods=['GET'])
def api_list_departments(name):
    """列出部门"""
    try:
        depts = meeting.list_departments(name)
        return jsonify(depts)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/meeting/<name>/departments', methods=['POST'])
def api_add_department(name):
    """添加部门"""
    data = request.get_json()
    dept_name = data.get('name', '').strip()
    if not dept_name:
        return jsonify({"error": "部门名称不能为空"}), 400
    try:
        depts = meeting.add_department(name, dept_name)
        return jsonify({"success": True, "departments": depts})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@app.route('/api/meeting/<name>/departments/<dept_name>', methods=['DELETE'])
def api_remove_department(name, dept_name):
    """删除部门"""
    try:
        depts = meeting.remove_department(name, dept_name)
        return jsonify({"success": True, "departments": depts})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@app.route('/api/meeting/<name>/participants/phones', methods=['POST'])
def api_batch_upload_phones(name):
    """批量上传姓名+电话+部门"""
    data = request.get_json()
    items = data.get('items', [])
    if not items:
        return jsonify({"error": "请提供人员数据"}), 400
    results = []
    for item in items:
        pname = item.get('name', '').strip()
        if not pname:
            continue
        meeting.set_participant_meta(
            name, pname,
            phone=item.get('phone', ''),
            department=item.get('department', '')
        )
        meeting.sync_student_to_global(
            pname,
            class_name=item.get('department', ''),
            course_name=name,
            phone=item.get('phone', '')
        )
        results.append({"name": pname, "phone": item.get('phone',''), "department": item.get('department','')})
    return jsonify({"success": True, "count": len(results), "results": results})


@app.route('/api/meeting/<name>/expected', methods=['GET'])
def api_get_expected(name):
    """获取预期参会人员"""
    try:
        expected = meeting.get_expected_participants(name)
        return jsonify({"expected": expected})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/meeting/<name>/expected', methods=['POST'])
def api_set_expected(name):
    """设置预期参会人员"""
    data = request.get_json()
    names = data.get('names', [])
    meeting.set_expected_participants(name, names)
    return jsonify({"success": True, "expected": names})


@app.route('/api/meeting/<name>/deadline', methods=['GET'])
def api_get_deadline(name):
    """获取签到截止时间"""
    try:
        dl = meeting.get_checkin_deadline(name)
        return jsonify({"deadline": dl})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/meeting/<name>/deadline', methods=['POST'])
def api_set_deadline(name):
    """设置签到截止时间"""
    data = request.get_json()
    deadline_str = data.get('deadline', '').strip()
    try:
        result = meeting.set_checkin_deadline(name, deadline_str or None)
        return jsonify({"success": True, "deadline": result})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ─── API: 特征库 ───────────────────────────────────

@app.route('/api/meeting/<name>/build', methods=['POST'])
def api_build_facebank(name):
    try:
        mtcnn, learner = _load_models()
        conf = _get_conf()
        embs, names = meeting.build_facebank(name, learner.model, mtcnn, conf, tta=True)
        return jsonify({
            "success": True,
            "count": len(embs),
            "names": list(names[1:]) if len(names) > 1 else []
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ─── API: 报告 ─────────────────────────────────────

@app.route('/api/meeting/<name>/report', methods=['GET'])
def api_get_report(name):
    try:
        stats = report_mod.get_statistics(name)
        return jsonify(stats)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/meeting/<name>/export/csv', methods=['GET'])
def api_export_csv(name):
    try:
        path = report_mod.export_csv(name)
        return send_file(path, mimetype='text/csv',
                         as_attachment=True,
                         download_name=f'{name}_签到记录.csv')
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/meeting/<name>/export/html', methods=['GET'])
def api_export_html(name):
    try:
        path = report_mod.export_html(name)
        return send_file(path, mimetype='text/html',
                         as_attachment=True,
                         download_name=f'{name}_签到报告.html')
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ─── 课堂大屏看板 ─────────────────────────────

@app.route('/screen')
def screen_selector():
    """大屏入口 — 选择课程后进入看板"""
    meetings = meeting.list_meetings()
    html = '<!DOCTYPE html><html><head><meta charset="utf-8">'
    html += '<title>大屏看板 - 选择课程</title>'
    html += '<style>body{font-family:"Microsoft YaHei",sans-serif;background:#0f172a;color:#e2e8f0;display:flex;flex-direction:column;align-items:center;justify-content:center;min-height:100vh;margin:0;padding:20px}'
    html += 'h1{font-size:2rem;margin-bottom:30px}.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:16px;width:100%;max-width:800px}'
    html += '.card{background:#1e293b;border-radius:12px;padding:20px;text-align:center;cursor:pointer;transition:all 0.2s;text-decoration:none;color:#e2e8f0}'
    html += '.card:hover{transform:scale(1.05);background:#2563eb}.card .name{font-size:1.2rem;font-weight:700}.card .stat{font-size:0.85rem;color:#94a3b8;margin-top:6px}</style></head><body>'
    html += '<h1>📊 选择课程查看大屏</h1><div class="grid">'
    for m in meetings:
        html += f'<a class="card" href="/dashboard/{m["name"]}"><div class="name">{m["name"]}</div>'
        html += f'<div class="stat">已签 {m.get("checked_in",0)}/{m.get("participant_count",0)}</div></a>'
    html += '</div></body></html>'
    return html


@app.route('/dashboard/<name>')
def classroom_dashboard(name):
    """实时签到大屏看板 — 投影到教室大屏"""
    return render_template('classroom_dashboard.html', meeting_name=name)


@app.route('/api/meeting/<name>/checkin/status')
def api_checkin_status(name):
    """签到实时状态（供大屏看板使用，只显示当前活跃签到）"""
    import checkin as checkin_mod
    import report as report_mod
    from course import _load_sessions
    records = checkin_mod._load_attendance(name)
    # 按活跃 session 过滤（不自动创建）
    session_id = ''
    session_name = ''
    try:
        sdata = _load_sessions(name)
        if sdata.get('active'):
            for s in sdata.get('sessions', []):
                if s['id'] == sdata['active']:
                    session_id = s['id']
                    session_name = s['name']
                    break
        session_records = [r for r in records if r.get('session') == session_id] if session_id else []
    except Exception:
        session_records = []
    checked_names = set(r['name'] for r in session_records)
    try:
        participants = meeting.get_participants(name)
        all_names = [p['name'] for p in participants]
    except Exception:
        all_names = []
    if not all_names:
        try:
            fb_names = report_mod._load_names(name)
            all_names = list(fb_names[1:]) if fb_names is not None and len(fb_names) > 1 else []
        except Exception:
            pass
    return jsonify({
        "checked_names": sorted(checked_names),
        "unchecked_names": [n for n in all_names if n not in checked_names],
        "total": len(all_names),
        "checked_in": len(checked_names),
        "records": session_records[-20:] if session_records else [],
        "session_name": session_name
    })


# ─── API: 签到码 ────────────────────────────────

@app.route('/api/meeting/<name>/checkin-codes', methods=['GET'])
def api_get_checkin_codes(name):
    """获取所有参与者的签到码"""
    try:
        codes = meeting.get_all_checkin_codes(name)
        from checkin import get_checked_in_names
        checked = get_checked_in_names(name)
        result = []
        for code, person in sorted(codes.items(), key=lambda x: x[1]):
            result.append({"code": code, "name": person, "checked_in": person in checked})
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/meeting/<name>/checkin-codes/generate', methods=['POST'])
def api_generate_checkin_codes(name):
    """为所有未分配码的参与者批量生成签到码"""
    try:
        codes = meeting.batch_generate_codes(name)
        return jsonify({"success": True, "count": len(codes)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/meeting/<name>/checkin-code/reset', methods=['POST'])
def api_reset_checkin_code(name):
    """重置某人的签到码"""
    data = request.get_json()
    person = data.get('name', '').strip()
    if not person:
        return jsonify({"error": "请指定姓名"}), 400
    try:
        new_code = meeting.reset_checkin_code(name, person)
        return jsonify({"success": True, "code": new_code, "name": person})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ─── 学生自助注册 ─────────────────────────────

@app.route('/register/<name>')
def student_register(name):
    """学生自助注册页面 — 扫码自拍 + 输入姓名 + 选择班级"""
    info = meeting.load_meeting(name)
    try:
        departments = meeting.list_departments(name)
    except Exception:
        departments = []
    return render_template('student_register.html', meeting_name=name,
                           description=info.get('description', ''),
                           departments=departments)


@app.route('/api/register/<name>', methods=['POST'])
def api_student_register(name):
    """学生自助注册 API — 接收自拍+姓名+班级"""
    person_name = request.form.get('name', '').strip()
    class_name = request.form.get('class_name', '').strip()
    if not person_name:
        return jsonify({"error": "请输入姓名"}), 400
    if 'photo' not in request.files:
        return jsonify({"error": "请拍摄照片"}), 400
    photo = request.files['photo']
    if not photo.filename:
        return jsonify({"error": "请拍摄照片"}), 400

    # 保存到临时位置
    import uuid
    tmp_dir = Path(_DATA_ROOT) / 'tmp'
    tmp_dir.mkdir(exist_ok=True)
    ext = os.path.splitext(photo.filename)[1] or '.jpg'
    tmp_path = tmp_dir / f"reg_{uuid.uuid4().hex}{ext}"
    photo.save(str(tmp_path))

    try:
        result = meeting.add_participant(name, person_name, str(tmp_path))
        # 同步到全局学生索引
        meeting.sync_student_to_global(person_name, class_name=class_name, course_name=name)
        # 设置班级到课程的元数据
        if class_name:
            meeting.set_participant_meta(name, person_name, department=class_name)
        # 清理临时文件
        if tmp_path.exists():
            tmp_path.unlink()
        return jsonify({"success": True, "name": person_name, "path": result}), 201
    except Exception as e:
        if tmp_path.exists():
            tmp_path.unlink()
        return jsonify({"error": str(e)}), 500


# ─── 班级自助注册（扫码 → 自拍 → 加入班级） ─────

@app.route('/register/class/<name>')
def student_register_class(name):
    """班级自助注册页面 — 扫码自拍 + 输入姓名"""
    return render_template('student_register.html', meeting_name=name,
                           description=f'班级: {name}', departments=[],
                           reg_class=name)


@app.route('/api/register/class/<name>', methods=['POST'])
def api_student_register_class(name):
    """班级自助注册 API — 学生加入全局班级"""
    person_name = request.form.get('name', '').strip()
    if not person_name:
        return jsonify({"error": "请输入姓名"}), 400
    if 'photo' not in request.files:
        return jsonify({"error": "请拍摄照片"}), 400
    photo = request.files['photo']
    if not photo.filename:
        return jsonify({"error": "请拍摄照片"}), 400

    import uuid, base64
    tmp_dir = Path(_DATA_ROOT) / 'tmp'
    tmp_dir.mkdir(exist_ok=True)
    ext = os.path.splitext(photo.filename)[1] or '.jpg'
    tmp_path = tmp_dir / f"reg_{uuid.uuid4().hex}{ext}"
    photo.save(str(tmp_path))

    try:
        import shutil
        from PIL import Image
        # 保存到全局学生照片目录
        photos_dir = Path(_DATA_ROOT) / 'students' / 'photos'
        photos_dir.mkdir(parents=True, exist_ok=True)
        dst = photos_dir / f"{person_name}{ext}"
        shutil.copy2(str(tmp_path), str(dst))

        # 同步到全局学生索引
        meeting.sync_student_to_global(person_name, class_name=name, course_name='')

        if tmp_path.exists():
            tmp_path.unlink()
        return jsonify({"success": True, "name": person_name, "class": name}), 201
    except Exception as e:
        if tmp_path.exists():
            tmp_path.unlink()
        return jsonify({"error": str(e)}), 500


@app.route('/api/qr/<name>')
def api_qr_code(name):
    """生成注册二维码信息"""
    public_url = request.host_url.rstrip('/')
    register_url = f"{public_url}/register/{name}"
    return jsonify({
        "url": register_url,
        "course": name
    })


# ─── API: 班级查询与批量导入 ─────────────────────

@app.route('/api/classes')
def api_get_all_classes():
    """获取所有班级（从全局索引 + 各课程合并）"""
    from course import get_all_global_classes
    global_classes = get_all_global_classes()
    course_classes = set()
    for m in meeting.list_meetings():
        try:
            depts = meeting.list_departments(m['name'])
            course_classes.update(depts)
        except Exception:
            pass
    all_classes = sorted(set(global_classes) | course_classes)
    return jsonify({"classes": all_classes})


@app.route('/api/class/<cname>/students')
def api_get_class_students(cname):
    """获取某班级的所有学生及其课程报名情况"""
    from course import get_global_students_by_class
    students = get_global_students_by_class(cname)
    # 也搜索各课程的 participants_meta.json 补全
    for m in meeting.list_meetings():
        try:
            meta = meeting.get_all_participant_meta(m['name'])
            for pname, info in meta.items():
                if info.get('department') == cname:
                    if pname not in students:
                        students[pname] = {
                            "name": pname,
                            "class": cname,
                            "phone": info.get('phone', ''),
                            "courses": [m['name']]
                        }
                    elif m['name'] not in students[pname]['courses']:
                        students[pname]['courses'].append(m['name'])
        except Exception:
            pass
    result = []
    for sname, info in sorted(students.items()):
        result.append({
            "name": sname,
            "phone": info.get('phone', ''),
            "class": info.get('class', cname),
            "courses": info.get('courses', [])
        })
    return jsonify({"students": result, "class_name": cname})


@app.route('/api/batch/enroll', methods=['POST'])
def api_batch_enroll():
    """批量将某班级学生导入到指定课程"""
    data = request.get_json()
    class_name = data.get('class_name', '').strip()
    course_names = data.get('courses', [])
    if not class_name or not course_names:
        return jsonify({"error": "请指定班级和目标课程"}), 400
    from course import get_global_students_by_class, batch_enroll_students, sync_student_to_global
    # 从全局索引获取该班级学生
    students = get_global_students_by_class(class_name)
    # 也搜索各课程元数据中该班级的学生（兼容旧数据）
    for m in meeting.list_meetings():
        try:
            meta = meeting.get_all_participant_meta(m['name'])
            for pname, info in meta.items():
                if info.get('department') == class_name and pname not in students:
                    # 补充到全局索引
                    sync_student_to_global(pname, class_name=class_name, course_name=m['name'])
                    students[pname] = {"class": class_name, "courses": [m['name']]}
        except Exception:
            pass
    names = list(students.keys())
    if not names:
        return jsonify({"error": f"班级 '{class_name}' 没有学生"}), 400
    results = {}
    for cn in course_names:
        try:
            added = batch_enroll_students(cn, names)
            results[cn] = {"added": added, "count": len(added)}
        except Exception as e:
            results[cn] = {"error": str(e)}
    return jsonify({"success": True, "results": results, "class_name": class_name})


# ─── API: 全局班级管理（独立于课程） ──────────────

@app.route('/api/global-classes')
def api_list_global_classes():
    """获取所有全局班级"""
    from course import _load_global_classes
    return jsonify({"classes": _load_global_classes()})


@app.route('/api/global-classes', methods=['POST'])
def api_add_global_class():
    """创建全局班级"""
    data = request.get_json()
    name = data.get('name', '').strip()
    if not name:
        return jsonify({"error": "班级名称不能为空"}), 400
    from course import add_global_class
    try:
        classes = add_global_class(name)
        return jsonify({"success": True, "classes": classes}), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@app.route('/api/global-classes/<name>', methods=['DELETE'])
def api_remove_global_class(name):
    """删除全局班级"""
    from course import remove_global_class
    try:
        classes = remove_global_class(name)
        return jsonify({"success": True, "classes": classes})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@app.route('/api/class/<name>/build-facebank', methods=['GET', 'POST'])
def api_build_class_facebank(name):
    """为班级构建/查询特征库（GET查状态，POST构建）"""
    from course import _class_facebank_path
    from pathlib import Path
    if request.method == 'GET':
        # 查询班级特征库状态
        base = _class_facebank_path(name)
        pdir = base.parent / base.name
        fb_path = pdir / 'facebank.pth'
        if fb_path.exists():
            import numpy as np
            names = np.load(str(pdir / 'names.npy'), allow_pickle=True)
            return jsonify({"built": True, "count": len(names) - 1})
        else:
            return jsonify({"built": False, "count": 0})
    from course import build_class_facebank
    try:
        mtcnn, learner = _load_models()
        conf = _get_conf()
        embs, names = build_class_facebank(name, learner.model, mtcnn, conf, tta=True)
        return jsonify({"success": True, "count": len(embs), "names": list(names[1:])})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/course/<name>/classes', methods=['GET'])
def api_course_get_classes(name):
    """获取课程关联的班级列表"""
    from course import course_get_classes
    return jsonify({"classes": course_get_classes(name)})


@app.route('/api/course/<name>/classes', methods=['POST'])
def api_course_set_classes(name):
    """设置课程关联的班级（自动构建特征库）"""
    data = request.get_json()
    class_names = data.get('classes', [])
    from course import course_set_classes
    result = course_set_classes(name, class_names)
    # 自动构建关联班级的特征库（一次构建，所有课程复用）
    built_classes = []
    try:
        mtcnn, learner = _load_models()
        conf = _get_conf()
        for cn in class_names:
            try:
                embs, names = meeting.build_class_facebank(cn, learner.model, mtcnn, conf, tta=True)
                if len(embs) > 0:
                    built_classes.append({"class": cn, "count": len(embs)})
            except Exception:
                pass
    except Exception:
        pass
    return jsonify({
        "success": True, "classes": result,
        "facebank_built": built_classes
    })


# ─── API: 全局学生管理（独立于课程） ──────────────

@app.route('/api/global/students')
def api_list_global_students():
    """获取所有全局学生（不依赖课程）"""
    from course import _load_students_index
    students = []
    for name, info in sorted(_load_students_index().items()):
        has_photo = any((STUDENT_PHOTOS_DIR / f"{name}{e}").exists() for e in ['.jpg','.jpeg','.png','.bmp'])
        students.append({
            "name": name,
            "class": info.get('class', ''),
            "phone": info.get('phone', ''),
            "courses": info.get('courses', []),
            "created_at": info.get('created_at', ''),
            "has_photo": has_photo
        })
    return jsonify({"students": students})


@app.route('/api/global/students', methods=['POST'])
def api_add_global_student():
    """添加/更新全局学生"""
    data = request.get_json()
    name = data.get('name', '').strip()
    if not name:
        return jsonify({"error": "姓名不能为空"}), 400
    from course import sync_student_to_global
    entry = sync_student_to_global(
        name,
        class_name=data.get('class', ''),
        phone=data.get('phone', '')
    )
    return jsonify({"success": True, "student": entry}), 201


@app.route('/api/global/students/<name>', methods=['DELETE'])
def api_delete_global_student(name):
    """从全局删除学生（包括照片和所有课程中的记录）"""
    from course import _load_students_index, _save_students_index
    index = _load_students_index()
    if name not in index:
        return jsonify({"error": f"学生 '{name}' 不存在"}), 404

    # 1. 删除全局索引记录
    del index[name]
    _save_students_index(index)

    # 2. 删除全局照片
    for ext in ['.jpg', '.jpeg', '.png', '.bmp']:
        p = STUDENT_PHOTOS_DIR / f"{name}{ext}"
        if p.exists():
            p.unlink()

    # 3. 从所有课程的参与者目录和元数据中删除
    courses_root = Path(_DATA_ROOT) / 'courses'
    for course_dir in courses_root.iterdir():
        if not course_dir.is_dir():
            continue
        # 删除参与者目录
        pdir = course_dir / 'participants' / name
        if pdir.exists() and pdir.is_dir():
            import shutil
            shutil.rmtree(pdir)
        # 删除元数据
        meta_path = course_dir / 'participants_meta.json'
        if meta_path.exists():
            try:
                with open(meta_path, 'r', encoding='utf-8') as f:
                    meta = json.load(f)
                if name in meta:
                    del meta[name]
                    with open(meta_path, 'w', encoding='utf-8') as f:
                        json.dump(meta, f, ensure_ascii=False, indent=2)
            except Exception:
                pass

    return jsonify({"success": True})


STUDENT_PHOTOS_DIR = Path(_DATA_ROOT) / 'students' / 'photos'


@app.route('/api/global/students/<name>/photo', methods=['POST'])
def api_upload_student_photo(name):
    """上传学生照片（全局，不依赖课程）"""
    if 'photo' not in request.files:
        return jsonify({"error": "缺少照片"}), 400
    photo = request.files['photo']
    if not photo.filename:
        return jsonify({"error": "请选择照片文件"}), 400
    STUDENT_PHOTOS_DIR.mkdir(parents=True, exist_ok=True)
    ext = os.path.splitext(photo.filename)[1] or '.jpg'
    save_path = STUDENT_PHOTOS_DIR / f"{name}{ext}"
    photo.save(str(save_path))
    return jsonify({"success": True, "path": str(save_path)}), 201


@app.route('/api/global/students/<name>/photo')
def api_get_student_photo(name):
    """获取学生照片"""
    for ext in ['.jpg', '.jpeg', '.png', '.bmp']:
        p = STUDENT_PHOTOS_DIR / f"{name}{ext}"
        if p.exists():
            return send_file(str(p), mimetype=f'image/{ext[1:]}')
    return jsonify({"error": "照片不存在"}), 404


# ─── API: 签到次数管理 ──────────────────────────

@app.route('/api/course/<name>/sessions', methods=['GET'])
def api_list_sessions(name):
    """获取课程的所有签到次数"""
    from course import list_sessions
    sessions, active = list_sessions(name)
    return jsonify({"sessions": sessions, "active": active})


@app.route('/api/course/<name>/sessions', methods=['POST'])
def api_create_session(name):
    """创建新的签到次数"""
    from course import create_session
    data = request.get_json() or {}
    session = create_session(name, data.get('name'))
    return jsonify({"success": True, "session": session}), 201


@app.route('/api/course/<name>/sessions/switch', methods=['POST'])
def api_switch_session(name):
    """切换活跃签到次数"""
    from course import switch_session
    data = request.get_json()
    session_id = data.get('session_id', '')
    if not session_id:
        return jsonify({"error": "缺少session_id"}), 400
    try:
        session = switch_session(name, session_id)
        return jsonify({"success": True, "session": session})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@app.route('/api/course/<name>/sessions/end', methods=['POST'])
def api_end_session(name):
    """结束当前活跃签到次数"""
    from course import end_active_session
    old = end_active_session(name)
    return jsonify({"success": True, "ended": old})


# ─── 移动端 API（微信小程序） ────────────────────

@app.route('/api/mobile/detect', methods=['POST'])
def api_mobile_detect():
    """人脸检测测试（不需要特征库，只返回人脸框）

    支持 multipart/form-data（wx.uploadFile）和 JSON（base64）两种方式
    """
    import base64, io
    from PIL import Image
    from mtcnn import MTCNN

    img_bytes = None
    # 尝试 multipart 上传
    if 'image' in request.files:
        photo = request.files['image']
        img_bytes = photo.read()
    else:
        # 尝试 JSON base64
        data = request.get_json()
        if data:
            image_b64 = data.get('image', '')
            if image_b64:
                if ',' in image_b64:
                    image_b64 = image_b64.split(',', 1)[1]
                img_bytes = base64.b64decode(image_b64)

    if not img_bytes:
        return jsonify({"error": "缺少图片"}), 400

    try:
        image = Image.open(io.BytesIO(img_bytes)).convert('RGB')
        img_w, img_h = image.size

        mtcnn = MTCNN()
        bboxes, faces = mtcnn.align_multi(image, 50, 10)

        result = []
        for bbox in bboxes:
            bx1, by1, bx2, by2 = bbox[:4]
            result.append({
                "x": float(bx1) / img_w,
                "y": float(by1) / img_h,
                "w": float(bx2 - bx1) / img_w,
                "h": float(by2 - by1) / img_h
            })

        return jsonify({"success": True, "faces": result, "count": len(result)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/mobile/courses')
def api_mobile_courses():
    """获取教师课程列表（含当前签到次数进度）"""
    meetings = meeting.list_meetings()
    result = []
    for m in meetings:
        try:
            import checkin as checkin_mod
            from course import get_active_session
            # 获取活跃签到次数的签到人数
            records = checkin_mod._load_attendance(m['name'])
            try:
                active = get_active_session(m['name'])
                session_records = [r for r in records if r.get('session') == active['id']]
            except Exception:
                session_records = records
            checked_in = len(set(r['name'] for r in session_records))
            total = m.get('participant_count', 0)
            rate = f"{round(checked_in / total * 100, 1) if total > 0 else 0}%"
            result.append({
                "name": m['name'],
                "description": m.get('description', ''),
                "total": total,
                "checked_in": checked_in,
                "rate": rate
            })
        except Exception:
            result.append({
                "name": m['name'],
                "description": m.get('description', ''),
                "total": 0, "checked_in": 0, "rate": "0%"
            })
    return jsonify({"courses": result})


@app.route('/api/mobile/checkin', methods=['POST'])
def api_mobile_checkin():
    """微信小程序 — 上传照片签到

    请求: multipart/form-data
      - course: 课程名
      - image: 照片文件
    """
    course = request.form.get('course', '').strip()
    print(f"[mobile] checkin course='{course}', has_image={'image' in request.files}, form_keys={list(request.form.keys())}")
    if not course:
        print(f"[mobile] 400 缺少课程名")
        return jsonify({"error": "缺少课程名"}), 400
    if 'image' not in request.files:
        print(f"[mobile] 400 缺少照片")
        return jsonify({"error": "缺少照片"}), 400

    # 获取当前签到次数（优先客户端指定的 session）
    sess_id = request.form.get('session', '').strip() if request.form else ''
    if not sess_id:
        try:
            from course import get_active_session
            sess_id = get_active_session(course)['id']
        except Exception:
            sess_id = ''

    photo = request.files['image']
    import uuid
    import time as _time_module
    tmp_dir = Path(_DATA_ROOT) / 'tmp'
    tmp_dir.mkdir(exist_ok=True)
    tmp_path = tmp_dir / f"mobile_{uuid.uuid4().hex}.jpg"
    photo.save(str(tmp_path))
    # 清理 30 分钟前的临时文件
    try:
        now = _time_module.time()
        for f in tmp_dir.iterdir():
            if f.is_file() and now - f.stat().st_mtime > 1800:
                f.unlink()
    except Exception:
        pass

    try:
        import torch
        import numpy as np
        from PIL import Image

        mtcnn, learner = _load_models()
        conf = _get_conf()

        # 加载特征库：优先班级级（一次构建，所有课程复用）
        from course import get_course_facebanks
        targets, names = get_course_facebanks(course)
        if targets is None or targets.shape[0] == 0:
            # 降级到课程级（兼容旧数据）
            meeting_path = Path(_DATA_ROOT) / 'courses' / course
            fb_path = meeting_path / 'facebank.pth'
            names_path = meeting_path / 'names.npy'
            if fb_path.exists() and names_path.exists():
                targets = torch.load(fb_path)
                names = np.load(names_path)
            else:
                return jsonify({"error": "该课程尚未构建特征库"}), 400

        # 检测人脸
        image = Image.open(str(tmp_path)).convert('RGB')
        bboxes, faces = mtcnn.align_multi(image, conf.face_limit, conf.min_face_size)

        if len(bboxes) == 0 or len(faces) == 0:
            tmp_path.unlink()
            return jsonify({"success": True, "faces": [], "unknown_count": 0, "message": "未检测到人脸"})

        # 识别
        results, scores = learner.infer(conf, faces, targets, True)

        # 记录签到
        import checkin as checkin_mod
        checked_set = checkin_mod.get_checked_in_names(course, session=sess_id)
        faces_result = []
        # 图片尺寸，用于归一化坐标
        img_w, img_h = image.size
        for idx in range(len(results)):
            person_idx = int(results[idx])
            # 获取人脸框坐标（归一化为百分比）
            bbox_raw = bboxes[idx]
            bx1, by1, bx2, by2 = bbox_raw[:4]
            bbox_norm = {
                "x": float(bx1) / img_w,
                "y": float(by1) / img_h,
                "w": float(bx2 - bx1) / img_w,
                "h": float(by2 - by1) / img_h
            }
            if person_idx == -1:
                faces_result.append({
                    "name": None, "confidence": None,
                    "checked_in": False, "bbox": bbox_norm
                })
            else:
                name = names[person_idx + 1]
                score = float(scores[idx])
                if name not in checked_set:
                    checkin_mod.record_checkin(course, name, score, session=sess_id)
                    checked_set.add(name)
                faces_result.append({
                    "name": name,
                    "confidence": round(score, 3),
                    "checked_in": True,
                    "bbox": bbox_norm
                })

        tmp_path.unlink()
        return jsonify({
            "success": True,
            "faces": faces_result,
            "unknown_count": sum(1 for f in faces_result if f['name'] is None),
            "total_checked": len(checked_set)
        })

    except Exception as e:
        if tmp_path.exists():
            tmp_path.unlink()
        return jsonify({"error": str(e)}), 500


@app.route('/api/mobile/checkin-frame', methods=['POST'])
def api_mobile_checkin_frame():
    """微信小程序 — 实时帧识别（接收 base64 图片，返回人脸框+姓名）

    请求: JSON
      - course: 课程名
      - image: base64 编码的 JPEG 图片数据
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "无效请求"}), 400
    course = data.get('course', '').strip()
    image_b64 = data.get('image', '')
    if not course or not image_b64:
        return jsonify({"error": "缺少参数"}), 400

    # 获取签到次数（优先客户端指定）
    sess_id = data.get('session', '').strip()
    if not sess_id:
        try:
            from course import get_active_session
            sess_id = get_active_session(course)['id']
        except Exception:
            sess_id = ''

    try:
        import base64
        import io
        import torch
        import numpy as np
        from PIL import Image
        # 解码 base64
        if ',' in image_b64:
            image_b64 = image_b64.split(',', 1)[1]
        img_bytes = base64.b64decode(image_b64)
        image = Image.open(io.BytesIO(img_bytes)).convert('RGB')
        img_w, img_h = image.size

        # 复用 app.py 的模型加载（共享实例，避免重复加载）
        mtcnn, learner = _load_models()
        conf = _get_conf()

        # 加载特征库：优先班级级（一次构建，所有课程复用）
        from course import get_course_facebanks
        targets, names = get_course_facebanks(course)
        if targets is None or targets.shape[0] == 0:
            # 降级到课程级（兼容旧数据）
            meeting_path = Path(_DATA_ROOT) / 'courses' / course
            fb_path = meeting_path / 'facebank.pth'
            names_path = meeting_path / 'names.npy'
            if fb_path.exists() and names_path.exists():
                targets = torch.load(fb_path)
                names = np.load(names_path)
            else:
                return jsonify({"error": "该课程尚未构建特征库"}), 400

        # 检测人脸
        bboxes, faces = mtcnn.align_multi(image, conf.face_limit, conf.min_face_size)

        if len(bboxes) == 0 or len(faces) == 0:
            return jsonify({"success": True, "faces": [], "count": 0})

        # 识别
        results, scores = learner.infer(conf, faces, targets, True)

        # 记录签到
        import checkin as checkin_mod
        checked_set = checkin_mod.get_checked_in_names(course, session=sess_id)
        faces_result = []
        new_checkins = 0
        for idx in range(len(results)):
            person_idx = int(results[idx])
            bbox_raw = bboxes[idx]
            bx1, by1, bx2, by2 = bbox_raw[:4]
            bbox_norm = {
                "x": float(bx1) / img_w, "y": float(by1) / img_h,
                "w": float(bx2 - bx1) / img_w, "h": float(by2 - by1) / img_h
            }
            if person_idx == -1:
                faces_result.append({"name": None, "bbox": bbox_norm})
            else:
                name = names[person_idx + 1]
                score = float(scores[idx])
                if name not in checked_set:
                    checkin_mod.record_checkin(course, name, score, session=sess_id)
                    checked_set.add(name)
                    new_checkins += 1
                faces_result.append({
                    "name": name, "confidence": round(score, 3),
                    "checked_in": True, "bbox": bbox_norm
                })

        return jsonify({
            "success": True,
            "faces": faces_result,
            "count": len(faces_result),
            "new_checkins": new_checkins,
            "total_checked": len(checked_set)
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/mobile/checkin/result')
def api_mobile_checkin_result():
    """获取签到结果（可按签到次数过滤，同一课程可多次签到）"""
    course = request.args.get('course', '').strip()
    session_param = request.args.get('session', '').strip()
    if not course:
        return jsonify({"error": "缺少课程名"}), 400

    import checkin as checkin_mod
    import report as report_mod

    # 获取签到次数
    try:
        from course import get_active_session, list_sessions
        if session_param:
            # 指定了session
            sessions, _ = list_sessions(course)
            session_id = session_param
            session_name = ''
            for s in sessions:
                if s['id'] == session_param:
                    session_name = s['name']
                    break
        else:
            # 获取当前活跃的
            active = get_active_session(course)
            session_id = active['id']
            session_name = active['name']
    except Exception:
        session_id = ''
        session_name = ''

    records = checkin_mod._load_attendance(course)
    # 按 session 过滤
    if session_id:
        session_records = [r for r in records if r.get('session') == session_id]
    else:
        session_records = records
    checked_names = set(r['name'] for r in session_records)
    try:
        participants = meeting.get_participants(course)
        all_names = [p['name'] for p in participants]
    except Exception:
        all_names = []
    if not all_names:
        try:
            fb_names = report_mod._load_names(course)
            all_names = list(fb_names[1:]) if fb_names is not None and len(fb_names) > 1 else []
        except Exception:
            pass

    return jsonify({
        "course": course,
        "total": len(all_names),
        "checked_in": len(checked_names),
        "unchecked": [n for n in all_names if n not in checked_names],
        "checked_list": sorted(list(checked_names)),
        "records": session_records[-50:] if session_records else [],
        "session_id": session_id,
        "session_name": session_name,
        "rate": f"{round(len(checked_names) / len(all_names) * 100, 1) if all_names else 0}%"
    })


# ─── 签到台路由 ──────────────────────────────────

def _make_placeholder(text="等待签到启动..."):
    import cv2
    import numpy as np
    frame = np.full((480, 640, 3), 40, dtype=np.uint8)
    cv2.putText(frame, "📷", (290, 200),
                cv2.FONT_HERSHEY_SIMPLEX, 3, (100, 100, 100), 3)
    cv2.putText(frame, text, (180, 280),
                cv2.FONT_HERSHEY_SIMPLEX, 0.9, (150, 150, 150), 2)
    ret, buf = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 60])
    return buf.tobytes() if ret else b''

_PLACEHOLDER_JPEG = _make_placeholder()


@app.route('/kiosk/<name>')
def kiosk_page(name):
    """签到台（人脸识别模式）"""
    return render_template('kiosk_standalone.html', meeting_name=name)


@app.route('/kiosk/<name>/code')
def kiosk_code_page(name):
    """签到码模式 — 大数字键盘"""
    return render_template('kiosk_code.html', meeting_name=name)


@app.route('/kiosk/<name>/dashboard')
def kiosk_dashboard(name):
    """大屏看板 — 课程现场实时签到进度"""
    info = meeting.load_meeting(name)
    return render_template('kiosk_dashboard.html', meeting_name=name,
                           description=info.get('description', ''))


@app.route('/kiosk/<name>/codes')
def kiosk_print_codes(name):
    """打印签到码页面"""
    codes_data = meeting.get_all_checkin_codes(name)
    participants = meeting.get_participants(name)
    items = []
    for p in participants:
        code = None
        for c, n in codes_data.items():
            if n == p['name']:
                code = c
                break
        items.append({'name': p['name'], 'code': code or '—'})
    return render_template('kiosk_print_codes.html', meeting_name=name, items=items)


@app.route('/checkin/<name>')
def checkin_phone_page(name):
    """手机扫码签到页 — 输入姓名或签到码"""
    info = meeting.load_meeting(name)
    return render_template('checkin_qr.html', meeting_name=name,
                           description=info.get('description', ''))


@app.route('/api/meeting/<name>/department-stats')
def api_department_stats(name):
    """班级签到率统计"""
    try:
        groups = meeting.get_participants_by_department(name)
        checked = checkin_mod.get_checked_in_names(name)
        result = []
        total_people = 0
        total_checked = 0
        for dept, members in sorted(groups.items()):
            member_names = [m['name'] if isinstance(m, dict) else m for m in members]
            dept_checked = sum(1 for n in member_names if n in checked)
            total = len(member_names)
            rate = round(dept_checked / total * 100, 1) if total > 0 else 0
            result.append({
                "department": dept, "total": total,
                "checked": dept_checked, "rate": rate
            })
            total_people += total
            total_checked += dept_checked
        return jsonify({
            "departments": result, "total_people": total_people,
            "total_checked": total_checked,
            "overall_rate": round(total_checked / total_people * 100, 1) if total_people > 0 else 0
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/meeting/<name>/checkin-by-code', methods=['POST'])
def api_checkin_by_code(name):
    """通过签到码签到"""
    data = request.get_json()
    code = str(data.get('code', '')).strip()
    if not code:
        return jsonify({"error": "请输入签到码"}), 400
    result = meeting.checkin_by_code(name, code)
    if result is None:
        return jsonify({"error": "签到码无效"}), 404
    if result is False:
        return jsonify({"error": "您已签到"}), 409
    if _say_checkin:
        _say_checkin(result['name'], late=result.get('late', False),
                     late_minutes=result.get('late_minutes', 0))
    return jsonify({"success": True, "record": result})


@app.route('/api/camera/test')
def api_camera_test():
    try:
        cap, msg, idx = _open_camera()
        if cap is None:
            return jsonify({"success": False, "error": msg})
        ret, frame = cap.read()
        cap.release()
        if not ret or frame is None:
            return jsonify({"success": False, "error": "无法读取画面"})
        h, w = frame.shape[:2]
        return jsonify({"success": True, "message": msg, "resolution": f"{w}x{h}"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route('/api/camera/snapshot')
def api_camera_snapshot():
    import cv2
    cap = None
    try:
        cap, msg, idx = _open_camera()
        if cap is None:
            return jsonify({"success": False, "error": msg}), 500
        for _ in range(3):
            ret, frame = cap.read()
            if ret and frame is not None and frame.size > 0:
                break
        if not ret or frame is None:
            return jsonify({"error": "无法读取画面"}), 500
        ret_jpeg, buf = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
        if not ret_jpeg:
            return jsonify({"error": "编码失败"}), 500
        return Response(buf.tobytes(), mimetype='image/jpeg')
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if cap is not None:
            cap.release()


@app.route('/api/meeting/<name>/checkin/start', methods=['POST'])
def api_start_checkin(name):
    cam = get_camera_manager()
    if cam.is_active:
        cam.stop()
    try:
        from Learner import face_learner
        from config import get_config
        mtcnn, learner = _load_models()
        conf = _get_conf()
        conf.face_limit = 10
        conf.min_face_size = 30
        cam.start(name, learner, mtcnn, conf)
        return jsonify({"success": True, "status": cam.get_status()})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/meeting/<name>/checkin/stop', methods=['POST'])
def api_stop_checkin(name):
    cam = get_camera_manager()
    if cam.is_active:
        cam.stop()
    return jsonify({"success": True})


@app.route('/video_feed/<name>')
def video_feed(name):
    cam = get_camera_manager()

    def generate():
        if not (cam.is_active and cam.get_status().get('meeting') == name):
            yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' +
                   _PLACEHOLDER_JPEG + b'\r\n')
            yield b'--frame--\r\n'
            return
        empty_count = 0
        while cam.is_active and cam.get_status().get('meeting') == name:
            frame = cam.get_frame()
            if frame is not None:
                empty_count = 0
                yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' +
                       frame + b'\r\n')
            else:
                empty_count += 1
                time.sleep(0.1)
                if empty_count > 50:
                    break
        yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' +
               _PLACEHOLDER_JPEG + b'\r\n')
        yield b'--frame--\r\n'

    return Response(generate(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')


# ─── 启动 ──────────────────────────────────────────

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='启动签到系统 Web 服务')
    parser.add_argument('--host', type=str, default='127.0.0.1', help='监听地址')
    parser.add_argument('--port', type=int, default=5000, help='监听端口')
    parser.add_argument('--debug', action='store_true', help='调试模式')
    args = parser.parse_args()

    print(f"\n{'='*50}")
    print(f"  人脸识别会议签到系统 Web 服务")
    print(f"{'='*50}")
    print(f"  访问地址: http://{args.host}:{args.port}")
    print(f"  本机访问: http://localhost:{args.port}")
    print(f"{'='*50}\n")

    app.run(host=args.host, port=args.port, debug=args.debug, threaded=True)
