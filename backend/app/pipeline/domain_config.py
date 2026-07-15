from functools import lru_cache
from typing import Any

import yaml

from app.config import get_settings
from app.llm.registry import resolve_config_path


@lru_cache
def load_domain_config() -> dict[str, Any]:
    path = resolve_config_path(get_settings().domain_config_path)
    return yaml.safe_load(path.read_text(encoding="utf-8"))  # type: ignore[no-any-return]
