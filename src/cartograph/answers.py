import re

from cartograph.schemas import CodeAnswer, SourceFile

SOURCES_INSTRUCTION = (
    "Write the answer in plain text. Then, on a new line, write SOURCES: "
    "followed by one line per file you used, in the form "
    "'- path/to/file.py: what it contributed'. "
    "List a file only if a specific claim in your answer comes from it. "
    "Do not list files you only searched or skimmed. "
    "A question about one function or class usually needs one or two sources."
)

# Matches a line like "SOURCES:", "Sources", "**Sources:**" or "## Sources"
SOURCES_LINE = re.compile(r"^[#*\s]*sources[*\s]*:?[*\s]*$", re.IGNORECASE | re.MULTILINE)

def text_of(response) -> str:
    """Get plain text from a model reply (some providers return a list of parts)."""
    content = response.content
    if isinstance(content, str):
        return content
    return "".join(part.get("text", "") for part in content if isinstance(part, dict))


def parse_answer(text: str) -> CodeAnswer:
    """Split a plain-text reply into the answer and its list of sources."""
    matches = list(SOURCES_LINE.finditer(text))
    if not matches:
        return CodeAnswer(answer=text.strip(), sources=[])

    last = matches[-1]
    body = text[:last.start()].strip()
    sources = []
    for line in text[last.end():].splitlines():
        line = line.strip().lstrip("-*• ").strip()
        if not line:
            continue
        path, _, reason = line.partition(":")
        path = path.strip().strip("`*").strip()
        if path:
            sources.append(SourceFile(path=path, reason=reason.strip() or "Used in the answer"))
    return CodeAnswer(answer=body, sources=sources)