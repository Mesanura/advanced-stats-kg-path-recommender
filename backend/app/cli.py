import argparse
import json
from pathlib import Path

from app.db import SessionLocal
from app.services.simulation import DEFAULT_EXPORT_DIR, DEFAULT_SEED, seed_demo_data, summary_dict


def main() -> None:
    parser = argparse.ArgumentParser(description="高级统计课程系统管理命令")
    subparsers = parser.add_subparsers(dest="command", required=True)
    seed_parser = subparsers.add_parser("seed", help="生成演示用户和学习行为数据")
    seed_parser.add_argument("--reset", action="store_true", help="清空现有领域数据后重建")
    seed_parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    seed_parser.add_argument("--export-dir", type=Path, default=DEFAULT_EXPORT_DIR)
    args = parser.parse_args()

    if args.command == "seed":
        with SessionLocal() as db:
            summary = seed_demo_data(
                db,
                reset=args.reset,
                seed=args.seed,
                export_dir=args.export_dir,
            )
        print(json.dumps(summary_dict(summary), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

