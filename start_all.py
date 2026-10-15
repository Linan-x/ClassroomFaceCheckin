"""一键启动 — 单服务（8090端口，包含管理后台+签到台）"""

import threading
import time

from checkin_web.runtime import configure_runtime

configure_runtime()

PORT = 8090

# ─── WSGI 服务器 ──────────────────────────────
from wsgiref.simple_server import make_server, WSGIServer
import socketserver

class ThreadedWSGI(socketserver.ThreadingMixIn, WSGIServer):
    daemon_threads = True
    allow_reuse_address = True

# ─── 启动统一服务（包含管理后台 + 签到台所有功能）──
from checkin_web import app as admin_app
srv = make_server('0.0.0.0', PORT, admin_app.app.wsgi_app,
                  server_class=ThreadedWSGI)
threading.Thread(target=srv.serve_forever, daemon=True).start()

print(f'  [OK] 统一服务已启动: http://localhost:{PORT}')
print()
print(f'  [WEB] 管理后台:     http://localhost:{PORT}/')
print(f'  [KIO] 签到台:       http://localhost:{PORT}/kiosk/课程名')
print(f'        ├ 人脸签到:   http://localhost:{PORT}/kiosk/课程名')
print(f'        ├ 签到码:     http://localhost:{PORT}/kiosk/课程名/code')
print(f'        ├ 大屏看板:   http://localhost:{PORT}/kiosk/课程名/dashboard')
print(f'        └ 打印码表:   http://localhost:{PORT}/kiosk/课程名/codes')
print(f'  [REG] 自助注册:     http://localhost:{PORT}/registration')
print(f'  [SCR] 实时大屏:     http://localhost:{PORT}/dashboard/课程名')
print()

try:
    while True:
        time.sleep(60)
except KeyboardInterrupt:
    print('\n正在停止服务...')
    srv.shutdown()
    print('已停止')
