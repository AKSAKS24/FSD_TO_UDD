import re
from typing import Dict, List
from .section_mapper import SectionMapper

# Matches:
# SECTION 3: Purpose
# SECTION 6.5: Selection Screen
SECTION_HEADER_REGEX = re.compile(
    r"(?m)^\s*SECTION\s+(\d+(?:\.\d+)*)\s*[:\-]\s*(.*)$",
    re.IGNORECASE
)

def parse_fsd_sections(fsd_text: str) -> Dict[str, str]:
    sections = {}
    matches = list(SECTION_HEADER_REGEX.finditer(fsd_text))
    
    for i, match in enumerate(matches):
        section_number = match.group(1).strip()  # "3", "6.5"
        start = match.end()
        end = matches[i+1].start() if i + 1 < len(matches) else len(fsd_text)
        content = fsd_text[start:end].strip()
        sections[section_number] = content

    return sections

def extract_relevant_fsd_slice(fsd_text: str, udd_section: str, mapper: SectionMapper) -> str:
    fs_sections = parse_fsd_sections(fsd_text)
    mapped_keys: List[str] = mapper.keywords_for(udd_section)

    combined = []
    for key in mapped_keys:
        key = key.strip()
        if key in fs_sections:
            combined.append(fs_sections[key])

    # return combined or fallback to entire fsd
    return "\n\n".join(combined) if combined else fsd_text
