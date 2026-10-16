import os
from dotenv import load_dotenv

load_dotenv(override=True)

for key in ["GROQ_API_KEY", "GOOGLE_API_KEY", "OPENROUTER_API_KEY"]:
    print(key, "loaded:", os.getenv(key) is not None)


from cartograph.llm import get_all_models

for name, model in get_all_models().items():
    try:
        reply = model.invoke("Reply with just the word: OK")
        profile = model.profile or {}
        print(f"{name}: {reply.text} | tool_calling: {profile.get('tool_calling')}")
    except Exception as e:
        print(f"{name} FAILED: {type(e).__name__}: {str(e)[:150]}")