from pathlib import Path
import shutil
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.paths import data_uploads_dir, ensure_storage_dirs
from app.services.document_loader import load_document
from app.services.text_splitter import split_documents
from app.services.vector_store import VectorStore


DEMO_DOC_PATH = Path("examples/energy_demo/docs/boiler_efficiency.md")
DEMO_DATA_PATH = Path("examples/energy_demo/data/plant_daily.csv")
DEMO_DATASET_ID = "energy_demo_plant_daily.csv"


def main() -> None:
    ensure_storage_dirs()

    store = VectorStore()
    removed = store.delete_source(DEMO_DOC_PATH.name)
    documents = load_document(DEMO_DOC_PATH, source_name=DEMO_DOC_PATH.name)
    chunks = split_documents(documents)
    added = store.add_chunks(chunks)

    target_data_path = data_uploads_dir() / DEMO_DATASET_ID
    shutil.copyfile(DEMO_DATA_PATH, target_data_path)

    print("Energy Demo 已导入完成。")
    print(f"- 文档来源：{DEMO_DOC_PATH}")
    print(f"- 删除旧文档片段：{removed}")
    print(f"- 新增文档片段：{added}")
    print(f"- 数据集路径：{target_data_path}")
    print(f"- dataset_id：{DEMO_DATASET_ID}")
    print("")
    print("可以在 /ask 中尝试这些问题：")
    print("1. 根据文档，影响锅炉效率的因素有哪些？")
    print("2. 上传数据中 boiler_efficiency_pct 的平均值是多少？")
    print("3. 画出 load_mw 和 boiler_efficiency_pct 的趋势图。")
    print("4. 生成一份简短的运行分析报告。")


if __name__ == "__main__":
    main()
