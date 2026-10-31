from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field


class SourceFile(BaseModel):
  """One file the answer relies on."""
  path: str = Field(description="File path inside the project, like 'src/main/java/.../OwnerController.java'")
  reason: str = Field(description="What this file contributed to the answer")


class CodeAnswer(BaseModel):
  """Answer to the question about the codebase."""
  answer: str = Field(description="Clear explanation based only on the code that was read")
  sources: list[SourceFile] = Field(description="Every file the answer is based on, with why it was used")


class Route(BaseModel):
  """Decide how to handle the user's question."""
  kind: Literal["small", "big", "off_topic"] = Field(
    description="small = find or explain one specific thing in the code; "
                "big = explain the whole project or how parts fit together; "
                "off_topic = not about this codebase at all (general knowledge, chit-chat, other tasks)"
  )


class Plan(BaseModel):
  """A short to-do list that breaks a big question into smaller ones."""
  todos: list[str] = Field(
    description="Exactly 2 focused sub-questions that together answer the big question",
    min_length=2,
    max_length=2,
  )


class Note(BaseModel):
  """What one sub-agent found for one sub-question."""
  summary: str = Field(description="Detailed answer to the sub-question as 5 to 10 bullet points: exact function and class names, the file each is in, and the steps in order. Based only on code that was read.")
  files_read: list[str] = Field(description="Every file path that was read with read_file to find this")
  
MAPS_DIR = Path("data/maps")


def map_file(repo_id: str) -> Path:
  """'psf/requests' -> data/maps/psf__requests.json"""
  return MAPS_DIR / f"{repo_id.replace('/', '__')}.json"