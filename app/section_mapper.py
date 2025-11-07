import json, os
from typing import Dict, List, Optional
from .config import DEFAULT_MAPPING_PATH

class SectionMapper:
    def __init__(self, path: Optional[str] = None):
        self.path = path or DEFAULT_MAPPING_PATH
        if not os.path.exists(self.path):
            raise FileNotFoundError(f"Mapping file not found at: {self.path}")
        with open(self.path, "r", encoding="utf-8") as f:
            self.map: Dict[str, List[str]] = json.load(f)

    def keywords_for(self, udd_section: str) -> List[str]:
        return self.map.get(udd_section, [])
