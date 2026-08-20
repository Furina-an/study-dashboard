"""测试共享夹具：data_root 指向项目内临时目录（沙箱不允许写系统 Temp）。"""

from __future__ import annotations

import shutil
import time
from pathlib import Path

import pytest

_TMP_ROOT = Path(__file__).resolve().parent / ".tmp_test"


def _rmtree(path: Path) -> None:
    for _ in range(5):
        try:
            if path.exists():
                shutil.rmtree(path)
            return
        except OSError:
            time.sleep(0.1)


@pytest.fixture
def data_root():
    root = _TMP_ROOT / "run"
    _rmtree(root)
    root.mkdir(parents=True, exist_ok=True)
    yield root
    _rmtree(root)