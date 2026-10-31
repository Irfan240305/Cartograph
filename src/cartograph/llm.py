import os
from dotenv import load_dotenv
from langchain_core.language_models import BaseChatModel
from langchain_groq import ChatGroq
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI

from langchain_google_genai import GoogleGenerativeAIEmbeddings

from langchain_huggingface import HuggingFaceEmbeddings
from functools import lru_cache

load_dotenv(override=True)

OPENROUTER_URL = "https://openrouter.ai/api/v1"

def groq_model() -> BaseChatModel:
  """Create a groq chat model using setting from .env"""
  return ChatGroq(
    model=os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"),
    temperature=0,
    timeout=40,
    max_retries=2,
    max_tokens=8192,
    reasoning_effort="none",
  )
def gemini_model() -> BaseChatModel:
  """Create a gemini chat model using setting from .env"""
  return ChatGoogleGenerativeAI(
    model=os.getenv("GEMINI_MODEL", "gemini-3.8-flash"),
    timeout=20,
    max_retries=2
  )

def openrouter_model() -> BaseChatModel:
  """Create an OpenRouter chat model using setting from .env"""
  return ChatOpenAI(
    model=os.environ["OPENROUTER_MODEL"],
    base_url=OPENROUTER_URL,
    max_retries=2,
    timeout=20,
    api_key=os.environ["OPENROUTER_API_KEY"]
  )

def get_primary_model() -> BaseChatModel:
  """The main model cartograph uses first"""
  return groq_model()



def get_fallback_models() -> list[BaseChatModel]:
    """The fallback models cartograph uses if the primary model fails"""
    return [
        gemini_model(),
        openrouter_model()
    ]

def get_all_models() -> dict[str, BaseChatModel]:
    """All models cartograph can use"""
    return {
        "groq": groq_model(),
        "gemini": gemini_model(),
        "openrouter": openrouter_model()
    }
@lru_cache(maxsize=1)
def get_embedder():
  """The model that turns text into meaning-numbers. Runs locally — no API, no quota."""
  return HuggingFaceEmbeddings(model_name=os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"))

def structured_model(form):
  """A model that fills `form`, with backup models if the main one fails."""
  primary = get_primary_model().with_structured_output(form)
  backups = [m.with_structured_output(form) for m in get_fallback_models()]
  return primary.with_fallbacks(backups)


