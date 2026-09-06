"""三组不同数据场景实验入口，写出完整日志与 JSON。"""

from __future__ import annotations

import json
import platform
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.evaluate import evaluate_methods  # noqa: E402
from src.flow_matching import FlowConfig  # noqa: E402


RUNS = [
    {
        "id": "run01_default_seed7",
        "scenario": "default",
        "seed": 7,
        "n_trials": 24,
        "note": "中等障碍迷宫；名义场带障碍吸引，制造无过滤违规。",
    },
    {
        "id": "run02_tight_seed42",
        "scenario": "tight",
        "seed": 42,
        "n_trials": 24,
        "note": "更挤三障场景，检验 LSE 聚合与后置投影差异。",
    },
    {
        "id": "run03_aggressive_seed123",
        "scenario": "aggressive",
        "seed": 123,
        "n_trials": 24,
        "note": "更高速度与更强障碍吸引，压力测试去噪后段 CBF-FM。",
    },
]


def _fmt_methods(methods: dict) -> str:
    lines = []
    for name in ("none", "e2e_cbf", "cbf_fm"):
        m = methods[name]
        lines.append(
            f"  - {name}: success={m['success_rate']:.3f}, "
            f"viol={m['mean_violation_rate']:.3f}, "
            f"chunk_inside={m.get('mean_chunk_inside', 0):.2f}, "
            f"chunk_min_h={m.get('mean_chunk_min_barrier', 0):.3f}, "
            f"mean_h={m['mean_barrier']:.3f}, "
            f"curv={m['mean_curvature']:.4f}, "
            f"qp_ms={m['mean_qp_ms']:.2f}"
        )
    return "\n".join(lines)


def main() -> int:
    results_dir = ROOT / "results"
    logs_dir = ROOT / "logs"
    results_dir.mkdir(exist_ok=True)
    logs_dir.mkdir(exist_ok=True)

    started = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    master_lines = [
        "# Safe VLA CBF-FM — 三组实验主日志",
        "",
        f"- 工作目录: `{ROOT}`",
        f"- 平台: `{platform.platform()}`",
        f"- Python: `{platform.python_version()}`",
        f"- 开始时间: `{started}`",
        "",
    ]

    all_runs = []
    flow = FlowConfig(horizon=12, n_steps=20, tau_on=0.6)

    for run in RUNS:
        t0 = time.perf_counter()
        summary = evaluate_methods(
            scenario=run["scenario"],
            n_trials=run["n_trials"],
            seed=run["seed"],
            flow=flow,
        )
        elapsed = time.perf_counter() - t0
        payload = {
            "run_id": run["id"],
            "note": run["note"],
            "elapsed_sec": elapsed,
            "platform": platform.platform(),
            "python": platform.python_version(),
            **summary,
        }
        out_json = results_dir / f"{run['id']}.json"
        out_json.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        log_path = logs_dir / f"{run['id']}.log"
        log_body = (
            f"run_id={run['id']}\n"
            f"scenario={run['scenario']} seed={run['seed']} n_trials={run['n_trials']}\n"
            f"note={run['note']}\n"
            f"tau_on={summary['tau_on']}\n"
            f"elapsed_sec={elapsed:.2f}\n"
            f"methods:\n{_fmt_methods(summary['methods'])}\n"
        )
        log_path.write_text(log_body, encoding="utf-8")

        none_v = summary["methods"]["none"]["mean_violation_rate"]
        e2e_v = summary["methods"]["e2e_cbf"]["mean_violation_rate"]
        fm_v = summary["methods"]["cbf_fm"]["mean_violation_rate"]
        conclusion = (
            f"违规率 none={none_v:.3f} / e2e={e2e_v:.3f} / cbf_fm={fm_v:.3f}。"
            "口径：CBF-FM=生成内修正；E2E=动作块后置投影（类 Acc-CBF 后置叙事）；"
            "禁止把本机玩具迷宫数字写成项目页真机 100% 安全率。"
        )
        master_lines.extend(
            [
                f"## {run['id']}",
                "",
                f"- scenario=`{run['scenario']}` seed=`{run['seed']}` trials=`{run['n_trials']}`",
                f"- {run['note']}",
                f"- {_fmt_methods(summary['methods']).replace(chr(10), chr(10) + '- ')}",
                f"- 结论: {conclusion}",
                f"- 结果文件: `{out_json.name}` 耗时 {elapsed:.1f}s",
                "",
            ]
        )
        all_runs.append(payload)
        print(log_body)

    summary_all = {
        "started": started,
        "finished": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "platform": platform.platform(),
        "python": platform.python_version(),
        "tau_on": 0.6,
        "runs": all_runs,
    }
    (results_dir / "summary_three_runs.json").write_text(
        json.dumps(summary_all, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (results_dir / "summary.json").write_text(
        json.dumps(
            {
                "tau_on": 0.6,
                "runs": [
                    {
                        "id": r["run_id"],
                        "scenario": r["scenario"],
                        "methods": r["methods"],
                    }
                    for r in all_runs
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    master_lines.extend(
        [
            "## 汇总",
            "",
            "- `summary.json` / `summary_three_runs.json` 已写入",
            f"- 结束时间: `{summary_all['finished']}`",
            "",
        ]
    )
    (logs_dir / "MASTER_RUN.md").write_text("\n".join(master_lines), encoding="utf-8")
    print("MASTER_RUN written")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
