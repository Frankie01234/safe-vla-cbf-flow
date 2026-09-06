"""三种安全插入位置对照评测。"""

from __future__ import annotations

from typing import Any

import numpy as np

from .cbf_fm_step import barrier_values
from .flow_matching import FlowConfig, sample_action_chunk
from .maze2d import MazeConfig, make_maze, point_in_obstacle
from .posthoc_cbf import posthoc_project_chunk


METHODS = ("none", "e2e_cbf", "cbf_fm")
_METHOD_SEED_OFFSET = {"none": 0, "e2e_cbf": 100, "cbf_fm": 200}


def execute_chunk_open_loop(
    chunk: np.ndarray,
    cfg: MazeConfig,
    samples_per_seg: int = 10,
) -> dict[str, Any]:
    """沿动作块折线开环执行：公平比较「生成块」本身的安全性与可达性。

    不额外拉一条直线到 goal（那会人为穿障）；success 看块终点是否靠近 goal。
    """
    chunk = np.asarray(chunk, dtype=float).reshape(-1, 2)
    pts = [np.asarray(cfg.start, dtype=float)]
    for p in chunk:
        pts.append(p)

    traj: list[np.ndarray] = [pts[0].copy()]
    for a, b in zip(pts[:-1], pts[1:]):
        for s in range(1, samples_per_seg + 1):
            alpha = s / samples_per_seg
            traj.append((1.0 - alpha) * a + alpha * b)

    traj_arr = np.asarray(traj)
    violations = 0
    barrier_scores: list[float] = []
    for p in traj_arr:
        if point_in_obstacle(p, cfg.obstacles):
            violations += 1
        if cfg.obstacles:
            barrier_scores.append(float(min(obs.h(p) for obs in cfg.obstacles)))
        else:
            barrier_scores.append(0.0)

    n = max(len(traj_arr), 1)
    # 块终点靠近 goal 视为任务完成；放宽一点以覆盖绕障变长路径
    success = bool(
        np.linalg.norm(chunk[-1] - np.asarray(cfg.goal)) <= max(cfg.goal_tol * 2.5, 0.18)
    )
    if len(traj_arr) >= 3:
        d1 = traj_arr[1:] - traj_arr[:-1]
        d2 = d1[1:] - d1[:-1]
        curvature = float(np.mean(np.linalg.norm(d2, axis=1)))
        mean_speed = float(np.mean(np.linalg.norm(d1, axis=1)) / max(cfg.dt, 1e-6))
    else:
        curvature = 0.0
        mean_speed = 0.0

    hs_chunk = barrier_values(chunk, cfg.obstacles)
    return {
        "trajectory": traj_arr,
        "success": success,
        "violation_steps": violations,
        "violation_rate": violations / n,
        "mean_barrier": float(np.mean(barrier_scores)),
        "min_barrier": float(np.min(barrier_scores)),
        "chunk_min_barrier": float(np.min(hs_chunk)) if hs_chunk.size else 0.0,
        "chunk_inside": int(np.sum(hs_chunk < 0)) if hs_chunk.size else 0,
        "curvature": curvature,
        "mean_speed": mean_speed,
        "n_steps": n,
    }


def run_one_trial(
    maze: MazeConfig,
    flow: FlowConfig,
    method: str,
    seed: int,
) -> dict[str, Any]:
    rng = np.random.default_rng(seed)
    start = np.asarray(maze.start, dtype=float)

    if method == "none":
        chunk, meta = sample_action_chunk(start, maze, flow, mode="none", rng=rng)
    elif method == "cbf_fm":
        chunk, meta = sample_action_chunk(start, maze, flow, mode="cbf_fm", rng=rng)
    elif method == "e2e_cbf":
        chunk, meta = sample_action_chunk(start, maze, flow, mode="none", rng=rng)
        chunk = posthoc_project_chunk(chunk, maze.obstacles, alpha=flow.alpha, margin=0.05)
        meta = {**meta, "posthoc": True}
    else:
        raise ValueError(f"未知方法: {method}")

    roll = execute_chunk_open_loop(chunk, maze)
    return {
        "method": method,
        "success": roll["success"],
        "violation_rate": roll["violation_rate"],
        "violation_steps": roll["violation_steps"],
        "mean_barrier": roll["mean_barrier"],
        "min_barrier": roll["min_barrier"],
        "chunk_min_barrier": roll["chunk_min_barrier"],
        "chunk_inside": roll["chunk_inside"],
        "curvature": roll["curvature"],
        "mean_speed": roll["mean_speed"],
        "n_steps": roll["n_steps"],
        "qp_ms_mean": meta.get("qp_ms_mean", 0.0),
        "n_corrected_steps": meta.get("n_corrected_steps", 0),
        "chunk": chunk,
        "trajectory": roll["trajectory"],
    }


def evaluate_methods(
    scenario: str,
    n_trials: int,
    seed: int,
    flow: FlowConfig | None = None,
) -> dict[str, Any]:
    """对 none / e2e_cbf / cbf_fm 各跑 n_trials，汇总违规率与成功率。"""
    maze = make_maze(scenario)
    flow = flow or FlowConfig()
    if scenario == "aggressive":
        flow = FlowConfig(
            horizon=flow.horizon,
            n_steps=flow.n_steps,
            tau_on=flow.tau_on,
            alpha=flow.alpha,
            lse_eps=flow.lse_eps,
            smooth_weight=flow.smooth_weight,
            obstacle_attraction=0.55,
        )
    elif scenario == "tight":
        flow = FlowConfig(
            horizon=flow.horizon,
            n_steps=flow.n_steps,
            tau_on=flow.tau_on,
            alpha=flow.alpha,
            lse_eps=flow.lse_eps,
            smooth_weight=0.12,
            obstacle_attraction=0.40,
        )

    summary: dict[str, Any] = {
        "scenario": scenario,
        "n_trials": n_trials,
        "seed": seed,
        "tau_on": flow.tau_on,
        "methods": {},
    }

    for method in METHODS:
        offset = _METHOD_SEED_OFFSET[method]
        trials = [
            run_one_trial(maze, flow, method, seed=seed + 1000 * (i + 1) + offset)
            for i in range(n_trials)
        ]
        summary["methods"][method] = {
            "success_rate": float(np.mean([t["success"] for t in trials])),
            "mean_violation_rate": float(np.mean([t["violation_rate"] for t in trials])),
            "mean_barrier": float(np.mean([t["mean_barrier"] for t in trials])),
            "mean_min_barrier": float(np.mean([t["min_barrier"] for t in trials])),
            "mean_chunk_min_barrier": float(
                np.mean([t["chunk_min_barrier"] for t in trials])
            ),
            "mean_chunk_inside": float(np.mean([t["chunk_inside"] for t in trials])),
            "mean_curvature": float(np.mean([t["curvature"] for t in trials])),
            "mean_qp_ms": float(np.mean([t["qp_ms_mean"] for t in trials])),
            "n_trials": n_trials,
        }
    return summary
