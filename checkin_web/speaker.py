"""语音播报模块 — 签到成功时语音播报姓名

使用 Windows SAPI (TTS) 实现，无需额外依赖。
在 Linux/macOS 上静默跳过。
"""

import threading
import time

_SPEAKER = None
_SPEAKER_LOCK = threading.Lock()
_SPEAKER_QUEUE = []  # 播报队列
_QUEUE_THREAD = None
_STOP_EVENT = threading.Event()


def _get_speaker():
    """延迟初始化 SAPI 语音引擎"""
    global _SPEAKER
    if _SPEAKER is not None:
        return _SPEAKER
    try:
        import win32com.client
        _SPEAKER = win32com.client.Dispatch("SAPI.SpVoice")
        _SPEAKER.Rate = 0       # 语速（-10 ~ 10）
        _SPEAKER.Volume = 100   # 音量（0 ~ 100）
        return _SPEAKER
    except Exception:
        return None


def _queue_worker():
    """后台队列线程：依次播报，避免并发混乱"""
    while not _STOP_EVENT.is_set():
        if _SPEAKER_QUEUE:
            text = _SPEAKER_QUEUE.pop(0)
            speaker = _get_speaker()
            if speaker is not None:
                try:
                    speaker.Speak(text, 1)  # 1 = SVSFlagsAsync
                except Exception:
                    pass
        else:
            time.sleep(0.1)


def _ensure_queue_thread():
    """确保后台播报线程已启动"""
    global _QUEUE_THREAD
    if _QUEUE_THREAD is None or not _QUEUE_THREAD.is_alive():
        _STOP_EVENT.clear()
        _QUEUE_THREAD = threading.Thread(target=_queue_worker, daemon=True)
        _QUEUE_THREAD.start()


def say(text):
    """播报文本（异步，不阻塞）

    Args:
        text: 要播报的文本
    """
    if not text:
        return
    _SPEAKER_QUEUE.append(text)
    _ensure_queue_thread()


def say_checkin(name, late=False, late_minutes=0):
    """播报签到信息

    Args:
        name: 参与者姓名
        late: 是否迟到
        late_minutes: 迟到分钟数
    """
    if late and late_minutes > 0:
        say(f"{name}签到成功，迟到{late_minutes}分钟")
    elif late:
        say(f"{name}签到成功，已迟到")
    else:
        say(f"{name}签到成功")


def is_available():
    """检查语音引擎是否可用"""
    return _get_speaker() is not None


def stop():
    """停止语音播报线程"""
    _STOP_EVENT.set()
