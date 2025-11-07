import os, re
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from .config import DEFAULT_RAG_PATH

@dataclass
class RagSection:
    name: str
    type: str
    description: str
    prompt: str
    fields: Optional[List[str]] = None

def _parse_rag_block(block: str) -> RagSection:
    lines = [l.strip() for l in block.strip().splitlines() if l.strip()]
    if not lines or not lines[0].startswith("#"):
        raise ValueError("RAG section must start with '#Section Name'")
    name = lines[0][1:].strip()

    keyvals: Dict[str, Any] = {}
    current_key = None
    current_val_lines: List[str] = []

    def flush_key():
        nonlocal current_key, current_val_lines
        if current_key is not None:
            keyvals[current_key] = " ".join(current_val_lines).strip()

            current_key = None
            current_val_lines = []

    for ln in lines[1:]:
        if re.match(r"^[a-zA-Z_]+:\s*", ln):
            flush_key()
            k, v = ln.split(":", 1)
            current_key = k.strip()
            current_val_lines = [v.strip()]
        else:
            current_val_lines.append(ln.strip())
    flush_key()

    type_ = keyvals.get("type", "text")
    description = keyvals.get("description", "")
    prompt = keyvals.get("prompt", "")
    fields = None
    if "fields" in keyvals:
        raw = keyvals["fields"]
        m = re.match(r"^\[(.*)\]$", raw)
        if m:
            parts = [p.strip() for p in m.group(1).split(",")]
            fields = [p for p in parts if p]
        else:
            fields = [f.strip() for f in raw.split(",") if f.strip()]

    return RagSection(name=name, type=type_, description=description, prompt=prompt, fields=fields)

def load_rag_sections(rag_path: Optional[str]) -> List[RagSection]:
    path = rag_path or DEFAULT_RAG_PATH
    if not os.path.exists(path):
        raise FileNotFoundError(f"RAG file not found at: {path}")
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    blocks = re.split(r"\n(?=#)", text.strip())
    sections = [_parse_rag_block(b) for b in blocks if b.strip()]
    return sections
