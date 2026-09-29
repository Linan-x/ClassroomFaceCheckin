"""签到台独立服务 — 可部署在签到机器上的简约版"""

import sys
import os
import time
import json

# 将项目根目录和 core/ 加入 path
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _PROJECT_ROOT)
sys.path.insert(0, os.path.join(_PROJECT_ROOT, 'core'))

from pathlib import Path
from flask import (Flask, render_template, jsonify, request,
                   Response, send_file, redirect)

_APP_ROOT = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__,
            template_folder=os.path.join(_APP_ROOT, 'templates'),
            static_folder=os.path.join(_APP_ROOT, 'static'))
app.secret_key = os.environ.get('FLASK_SECRET_KEY') or os.urandom(32)

from config import get_config
from mtcnn import MTCNN
from Learner import face_learner
import course as meeting
import checkin as checkin_mod
import report as report_mod
from checkin_web.camera import get_camera_manager, _open_camera

# 语音播报（可选）
try:
    from checkin_web.speaker import say_checkin as _say_checkin
except Exception:
    _say_checkin = None

# ─── 模型（懒加载） ────────────────────────────────

_models_loaded = False
_mtcnn = None
_learner = None
_conf = None


def _get_conf():
    global _conf
    if _conf is None:
        _conf = get_config(False)
    return _conf


def _load_models():
    global _models_loaded, _mtcnn, _learner
    if _models_loaded:
        return _mtcnn, _learner
    conf = _get_conf()
    print("[kiosk] 加载 MTCNN...")
    _mtcnn = MTCNN()
    print("[kiosk] 加载人脸识别模型...")
    _learner = face_learner(conf, inference=True)
    _learner.threshold = conf.threshold
    _learner.load_state(conf, 'mobilefacenet.pth', True, True)
    _learner.model.eval()
    _models_loaded = True
    print("[kiosk] 模型加载完成")
    return _mtcnn, _learner


# ─── 占位图 ────────────────────────────────────────

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


# ─── 页面路由 ──────────────────────────────────────

@app.route('/')
def index():
    """签到台首页：显示所有可签到的会议"""
    # 如果绑定了会议，直接跳转
    bound_meeting = app.config.get('KIOSK_MEETING')
    if bound_meeting:
        return redirect(f'/kiosk/{bound_meeting}')
    meetings = meeting.list_meetings()
    return render_template('kiosk_index.html', meetings=meetings)


@app.route('/kiosk/<name>')
def kiosk_page(name):
    """会议签到台（人脸识别模式）"""
    public_url = app.config.get('PUBLIC_URL', request.host_url.rstrip('/'))
    return render_template('kiosk_standalone.html', meeting_name=name,
                           public_url=public_url)


@app.route('/kiosk/<name>/code')
def kiosk_code_page(name):
    """签到码模式 — 大数字键盘"""
    public_url = app.config.get('PUBLIC_URL', request.host_url.rstrip('/'))
    return render_template('kiosk_code.html', meeting_name=name,
                           public_url=public_url)


@app.route('/checkin/<name>')
def checkin_phone_page(name):
    """手机扫码签到页 — 输入姓名或签到码"""
    info = meeting.load_meeting(name)
    return render_template('checkin_qr.html', meeting_name=name,
                           description=info.get('description', ''))


@app.route('/kiosk/<name>/dashboard')
def kiosk_dashboard(name):
    """大屏看板 — 会议现场实时签到进度"""
    info = meeting.load_meeting(name)
    return render_template('kiosk_dashboard.html', meeting_name=name,
                           description=info.get('description', ''))


@app.route('/api/meeting/<name>/department-stats')
def api_department_stats(name):
    """部门签到率统计"""
    try:
        groups = meeting.get_participants_by_department(name)
        from checkin import get_checked_in_names
        checked = get_checked_in_names(name)

        result = []
        total_people = 0
        total_checked = 0
        for dept, members in sorted(groups.items()):
            # members 是 dict 列表，提取 name 字段比较
            member_names = [m['name'] if isinstance(m, dict) else m for m in members]
            dept_checked = sum(1 for n in member_names if n in checked)
            total = len(member_names)
            rate = round(dept_checked / total * 100, 1) if total > 0 else 0
            result.append({
                "department": dept,
                "total": total,
                "checked": dept_checked,
                "rate": rate
            })
            total_people += total
            total_checked += dept_checked

        return jsonify({
            "departments": result,
            "total_people": total_people,
            "total_checked": total_checked,
            "overall_rate": round(total_checked / total_people * 100, 1) if total_people > 0 else 0
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/kiosk/<name>/codes')
def kiosk_print_codes(name):
    """打印签到码页面 — 展示所有参与者及其签到码"""
    codes_data = meeting.get_all_checkin_codes(name)
    participants = meeting.get_participants(name)
    # 组织数据：给每个有码的人加上信息
    items = []
    for p in participants:
        code = None
        for c, n in codes_data.items():
            if n == p['name']:
                code = c
                break
        items.append({'name': p['name'], 'code': code or '—'})
    return render_template('kiosk_print_codes.html', meeting_name=name, items=items)


# ─── API: 会议信息 ──────────────────────────────────

@app.route('/api/meetings')
def api_list_meetings():
    return jsonify(meeting.list_meetings())


@app.route('/api/meeting/<name>')
def api_get_meeting(name):
    try:
        info = meeting.load_meeting(name)
        participants = meeting.get_participants(name)
        info['participant_count'] = len(participants)
        info['checked_in'] = len(checkin_mod._load_attendance(name))
        return jsonify(info)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/meeting/<name>/expected')
def api_get_expected(name):
    try:
        expected = meeting.get_expected_participants(name)
        return jsonify({"expected": expected})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/meeting/<name>/checkin/deadline')
def api_get_deadline(name):
    try:
        dl = meeting.get_checkin_deadline(name)
        return jsonify({"deadline": dl})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ─── API: 签到码 ────────────────────────────────

@app.route('/api/meeting/<name>/checkin-codes', methods=['GET'])
def api_get_checkin_codes(name):
    """获取所有参与者的签到码"""
    try:
        codes = meeting.get_all_checkin_codes(name)
        # 同时报告哪些人已签到
        from checkin import get_checked_in_names
        checked = get_checked_in_names(name)
        result = []
        for code, person in sorted(codes.items(), key=lambda x: x[1]):
            result.append({
                "code": code,
                "name": person,
                "checked_in": person in checked
            })
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


@app.route('/api/meeting/<name>/checkin-by-code', methods=['POST'])
def api_checkin_by_code(name):
    """通过签到码签到"""
    data = request.get_json()
    code = str(data.get('code', '')).strip()
    if not code:
        return jsonify({"error": "请输入签到码"}), 400

    result = meeting.checkin_by_code(name, code)
    if result is None:
        return jsonify({"error": "签到码无效，请重试"}), 404
    if result is False:
        return jsonify({"error": "您已签到，无需重复签到"}), 409

    # 语音播报
    if _say_checkin:
        late = result.get('late', False)
        late_min = result.get('late_minutes', 0)
        _say_checkin(result['name'], late=late, late_minutes=late_min)

    return jsonify({"success": True, "record": result})


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


# ─── API: 签到（摄像头） ──────────────────────────

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


@app.route('/api/meeting/<name>/checkin/status')
def api_checkin_status(name):
    cam = get_camera_manager()
    if cam.is_active and cam.get_status().get('meeting') == name:
        status = cam.get_status()
    else:
        records = checkin_mod._load_attendance(name)
        checked_names = set(r['name'] for r in records)
        # 始终从参与者目录获取完整名单（facebank 可能不全）
        all_names = []
        try:
            participants = meeting.get_participants(name)
            all_names = [p['name'] for p in participants]
        except Exception:
            pass
        # 后备：从 facebank 获取
        if not all_names:
            try:
                names = report_mod._load_names(name)
                all_names = list(names[1:]) if names is not None and len(names) > 1 else []
            except Exception:
                pass
        status = {
            "active": False,
            "meeting": name,
            "total": len(all_names),
            "checked_in": len(checked_names),
            "checked_names": sorted(checked_names),
            "unchecked_names": [n for n in all_names if n not in checked_names],
            "records": records[-10:] if records else [],
            "deadline": meeting.get_checkin_deadline(name)
        }
    return jsonify(status)


@app.route('/api/meeting/<name>/report')
def api_kiosk_report(name):
    """签到报告数据（dashboard 使用）"""
    try:
        stats = report_mod.get_statistics(name)
        return jsonify(stats)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


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

def main():
    """启动签到台服务 — 供外部调用或直接运行"""
    import argparse
    parser = argparse.ArgumentParser(
        description='签到台独立服务 — 每个实例绑定一个摄像头')
    parser.add_argument('--host', type=str, default='127.0.0.1', help='监听地址')
    parser.add_argument('--port', type=int, default=5001, help='监听端口')
    parser.add_argument('--meeting', type=str, default=None,
                        help='绑定会议名称（可选）。指定后首页自动跳转到该会议的签到台')
    parser.add_argument('--auto-start', action='store_true',
                        help='启动后自动开始签到（需要同时指定 --meeting）')
    parser.add_argument('--data-dir', type=str, default=None,
                        help='数据目录（与其他服务共享），默认使用项目 data/')
    parser.add_argument('--label', type=str, default=None,
                        help='此签到台的显示名称（可选，默认使用会议名）')
    parser.add_argument('--public-url', type=str, default=None,
                        help='外网可访问的地址（用于生成二维码），如 http://192.168.1.100:5001')
    args = parser.parse_args()

    if args.data_dir:
        data_path = Path(args.data_dir).resolve()
        if data_path.exists():
            os.chdir(str(data_path.parent))

    # 如果指定了 --meeting，存入 app config
    app.config['KIOSK_MEETING'] = args.meeting
    app.config['KIOSK_LABEL'] = args.label or args.meeting or '签到台'
    if args.public_url:
        app.config['PUBLIC_URL'] = args.public_url.rstrip('/')

    meeting_label = f"会议: {args.meeting}" if args.meeting else "选择会议"

    print(f"\n{'='*50}")
    print(f"  📸 签到台独立服务")
    print(f"{'='*50}")
    print(f"  访问地址: http://{args.host}:{args.port}")
    print(f"  会议绑定: {args.meeting or '未绑定（首页选择）'} ")
    print(f"  自动签到: {'是' if args.auto_start and args.meeting else '否'}")
    print(f"  数据目录: {_PROJECT_ROOT}")
    print(f"{'='*50}")
    if args.meeting:
        print(f"  ➡  直接进入: http://{args.host}:{args.port}/kiosk/{args.meeting}")
    print(f"\n")

    # 使用 wsgiref 启动（Python 内置，无外部依赖）
    from wsgiref.simple_server import make_server
    from wsgiref.simple_server import WSGIServer
    import socketserver

    # 使用线程池处理请求（支持 MJPEG 视频流等长连接）
    class ThreadedWSGIServer(socketserver.ThreadingMixIn, WSGIServer):
        daemon_threads = True
        allow_reuse_address = True

    server = make_server(args.host, args.port, app.wsgi_app,
                         server_class=ThreadedWSGIServer)
    print(f"  ⏳ 服务已启动，按 Ctrl+C 停止\n")
    server.serve_forever()

if __name__ == '__main__':
    main()
