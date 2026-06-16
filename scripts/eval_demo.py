import json
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.graph.workflow import run_agent


def main() -> None:
    questions_path = Path("examples/energy_demo/questions.json")
    questions = json.loads(questions_path.read_text(encoding="utf-8"))
    for item in questions:
        state = run_agent(item["question"], dataset_id="energy_demo_plant_daily.csv")
        print("-" * 80)
        print(f"问题：{item['question']}")
        print(f"预期路由：{item['expected_route']}")
        print(f"实际路由：{state.get('route')}")
        print(f"答案预览：{state.get('answer', '')[:300]}")


if __name__ == "__main__":
    main()
