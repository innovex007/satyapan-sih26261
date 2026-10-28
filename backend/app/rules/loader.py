from functools import lru_cache
from pathlib import Path

import yaml

DEFAULT = Path(__file__).with_name("aph_2026_27.yaml")


@lru_cache(maxsize=1)
def load_rules(path: str | None = None) -> dict:
    """Active APH rule set. (Later phases read the active row of the RuleSet table first, falling back to this file.)"""
    return yaml.safe_load(Path(path or DEFAULT).read_text(encoding="utf-8"))
