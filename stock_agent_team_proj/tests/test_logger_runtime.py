import logging
import sys
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import utils.logger as logger_module


class TestLoggerRuntime(unittest.TestCase):
    def test_get_logger_creates_missing_log_directory(self):
        logger_name = f"test.logger.{uuid.uuid4().hex}"

        with tempfile.TemporaryDirectory() as tmpdir:
            logs_dir = Path(tmpdir) / "logs"

            with patch.object(logger_module, "LOGS_DIR", str(logs_dir)):
                logger = logger_module.get_logger(logger_name)
                logger.info("logger directory creation test")

                self.assertTrue(logs_dir.exists())
                self.assertEqual(len(list(logs_dir.glob("agent_team_*.log"))), 1)

            self._cleanup_logger(logger_name)

    @staticmethod
    def _cleanup_logger(logger_name: str):
        logger = logging.getLogger(logger_name)
        for handler in list(logger.handlers):
            logger.removeHandler(handler)
            handler.close()

