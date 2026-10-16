from pydantic import BaseModel, Field
from typing import Literal

class SourceFile(BaseModel):
  """One file the answer relies on."""
  path: str = Field(description = "File path inside the project, like 'src/main/java/.../OwnerController.java'" )
  reason: str = Field(description = "What this file contributed to the answer")

class CodeAnswer(BaseModel):
  """Answer to the question about the codebase"""
  answer: str = Field(description = "Clear explanation based only on the code that was read")
  sources: list[SourceFile]= Field(description = "Every file the answer is based on, with why it was used")

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
    description="2 to 4 focused sub-questions that together answer the big question",
    max_length=4,
  )

class Note(BaseModel):
  """what one sub-agent found for one sub-questions."""
  summary: str = Field(description="Short answer to the sub-question, based only on code that was read")
  files_read: list[str] = Field(description="Every file path that was read with read_file to find this")

  