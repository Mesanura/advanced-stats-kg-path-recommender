import argparse
import json
from pathlib import Path

from app.db import SessionLocal
from app.enums import MasteryAlgorithm
from app.services.diagnosis import recompute_bkt_mastery, recompute_rule_mastery
from app.services.simulation import DEFAULT_EXPORT_DIR, DEFAULT_SEED, seed_demo_data, summary_dict


def main() -> None:
    parser = argparse.ArgumentParser(description="高级统计课程系统管理命令")
    subparsers = parser.add_subparsers(dest="command", required=True)
    seed_parser = subparsers.add_parser("seed", help="生成演示用户和学习行为数据")
    seed_parser.add_argument("--reset", action="store_true", help="清空现有领域数据后重建")
    seed_parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    seed_parser.add_argument("--export-dir", type=Path, default=DEFAULT_EXPORT_DIR)
    diagnose_parser = subparsers.add_parser("diagnose", help="重新计算知识掌握度")
    diagnose_parser.add_argument(
        "--algorithm", choices=[item.value for item in MasteryAlgorithm], default="rule"
    )
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
    elif args.command == "diagnose":
        with SessionLocal() as db:
            updated = (
                recompute_rule_mastery(db)
                if args.algorithm == MasteryAlgorithm.RULE.value
                else recompute_bkt_mastery(db)
            )
        print(json.dumps({"algorithm": args.algorithm, "results_updated": updated}, ensure_ascii=False))


if __name__ == "__main__":
    main()
