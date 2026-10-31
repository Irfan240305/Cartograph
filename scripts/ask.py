from cartograph.agent import ask

answer = ask("Where are the AI models created, and which providers are used?", ".")

print("ANSWER:")
print(answer.answer)

print("\nSOURCES:")
for source in answer.sources:
    print("-", source.path, "→", source.reason)