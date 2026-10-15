"""Focused regression tests for phase-one runtime stabilization."""

import os
import unittest
from unittest.mock import patch

from checkin_web.runtime import PATHS, configure_runtime


class RuntimePathsTests(unittest.TestCase):
    def test_runtime_setup_preserves_current_directory(self):
        original_cwd = os.getcwd()

        paths = configure_runtime()

        self.assertEqual(original_cwd, os.getcwd())
        self.assertEqual(paths.project_root, PATHS.project_root)
        self.assertTrue(paths.core_root.is_dir())
        self.assertTrue(paths.data_root.is_dir())


class HealthEndpointTests(unittest.TestCase):
    def test_recognition_config_uses_project_paths(self):
        from checkin_web.app import _get_conf

        config = _get_conf()

        self.assertEqual(config.data_path, PATHS.data_root)
        self.assertEqual(config.work_path, PATHS.workspace_root)
        self.assertEqual(config.model_path, PATHS.workspace_root / "models")

    def test_health_does_not_load_recognition_models(self):
        from checkin_web.app import app, recognition

        with patch.object(recognition, "load_models") as load_models:
            response = app.test_client().get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["status"], "ok")
        self.assertFalse(load_models.called)

    def test_invalid_json_receives_safe_api_error(self):
        from checkin_web.app import app

        response = app.test_client().post(
            "/api/meetings",
            data="{not valid json",
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json(), {"error": "请求格式错误"})
