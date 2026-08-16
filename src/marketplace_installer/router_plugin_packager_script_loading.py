"""Load a sibling script when the tools run directly from a source checkout."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType


def load_sibling_module(script_name: str) -> ModuleType:
    path = Path(__file__).resolve().with_name(script_name)
    module_name = path.stem
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module
