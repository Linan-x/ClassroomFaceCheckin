"""
向后兼容 — 实际实现在 core/course.py
保留此文件避免旧代码 import meeting 报错
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'core'))
from course import *  # noqa: F403
