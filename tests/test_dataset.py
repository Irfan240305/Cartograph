import json

import pytest
pytestmark = pytest.mark.unit

data = json.loads(open("evals/dataset.json", encoding="utf-8").read())
print("Questions:", len(data))
for q in data:
  print(f"  [{q['type']}] {q['question']}")