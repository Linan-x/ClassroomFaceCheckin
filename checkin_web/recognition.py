"""Lazy, process-local face recognition model lifecycle."""

from __future__ import annotations

import threading

from checkin_web.runtime import PATHS


class RecognitionService:
    """Load inference models once, only when a recognition endpoint requires them."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._conf = None
        self._mtcnn = None
        self._learner = None

    @property
    def models_loaded(self) -> bool:
        return self._mtcnn is not None and self._learner is not None

    def get_config(self):
        if self._conf is None:
            from config import get_config

            self._conf = get_config(False)
            self._conf.data_path = PATHS.data_root
            self._conf.work_path = PATHS.workspace_root
            self._conf.model_path = PATHS.workspace_root / "models"
            self._conf.save_path = PATHS.workspace_root / "save"
            self._conf.face_limit = 50
            self._conf.min_face_size = 20
            self._conf.threshold = 1.0
        return self._conf

    def load_models(self):
        if self.models_loaded:
            return self._mtcnn, self._learner

        with self._lock:
            if self.models_loaded:
                return self._mtcnn, self._learner

            from Learner import face_learner
            from mtcnn import MTCNN

            conf = self.get_config()
            print("正在加载 MTCNN...")
            mtcnn = MTCNN()
            print("正在加载人脸识别模型...")
            learner = face_learner(conf, inference=True)
            learner.threshold = conf.threshold
            learner.load_state(conf, "mobilefacenet.pth", True, True)
            learner.model.eval()
            self._mtcnn = mtcnn
            self._learner = learner
            print("模型加载完成")
            return self._mtcnn, self._learner
