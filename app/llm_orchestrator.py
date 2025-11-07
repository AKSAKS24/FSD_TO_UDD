from typing import List, Tuple
from langchain_openai import ChatOpenAI
from langchain.schema import SystemMessage, HumanMessage
from .config import LLM_MODEL
from .rag_loader import RagSection
from .section_extractor import extract_relevant_fsd_slice
from .section_mapper import SectionMapper

SYSTEM_PROMPT = (
    "You are a senior SAP documentation specialist.\n"
    "You generate precise, client-ready text for a Unified Design Document (UDD) based on:\n"
    "1) a Functional Specification (FSD) excerpt,\n"
    "2) a UDD section definition (RAG).\n\n"
    "Rules:\n"
    "- Produce polished, formal, professional language fit for client deliverables.\n"
    "- Follow the section's 'type' and 'fields' instructions strictly (table vs. text).\n"
    "- Do not hallucinate. If something is missing, write [To Be Filled].\n"
    "- Keep each answer self-contained to be pasted directly into the UDD.\n"
    "- Use concise, well-structured prose. Avoid filler."
)

def build_user_prompt(section: RagSection, fs_slice: str) -> str:
    fields_hint = f"\nFields (if table): {section.fields}" if section.fields else ""
    return (
        f"Target UDD Section: {section.name}\n"
        f"Type: {section.type}\n"
        f"Description: {section.description}{fields_hint}\n\n"
        "Authoring Instructions:\n"
        f"{section.prompt}\n\n"
        "Functional Spec Excerpt (FSD):\n"
        f'\"\"\"{fs_slice}\"\"\"\n\n'
        "Now produce only the content for the UDD section above. "
        "If type is 'table', return a clean markdown table with exactly the columns requested. "
        "If a field's value is unknown, use [To Be Filled]."
    )

def ensure_order(rag_sections: List[RagSection]) -> List[RagSection]:
    return rag_sections

def make_llm() -> ChatOpenAI:
    return ChatOpenAI(model=LLM_MODEL, streaming=False)

def generate_udd_sections(fsd_text: str, rag_sections: List[RagSection], mapper: SectionMapper) -> List[Tuple[str,str]]:
    llm = make_llm()
    results: List[Tuple[str,str]] = []
    context_snippets: List[str] = []
    ordered = ensure_order(rag_sections)

    for sec in ordered:
        fs_slice = extract_relevant_fsd_slice(fsd_text, sec.name, mapper)
        prior = "\n\n".join(context_snippets[-3:])
        messages = [SystemMessage(content=SYSTEM_PROMPT)]
        human = (f"Context (previous sections, if any):\n{prior}\n\n" if prior else "") + build_user_prompt(sec, fs_slice)
        messages.append(HumanMessage(content=human))
        resp = llm.invoke(messages)
        content = resp.content.strip() if hasattr(resp, "content") else str(resp)
        results.append((sec.name, content))
        context_snippets.append(f"[{sec.name}] {content[:1200]}")
    return results
