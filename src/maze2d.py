"""2D Maze / 积分器环境：起点→终点，圆形障碍。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

import numpy as np

from .cbf_fm_step import CircleObstacle


@dataclass
class MazeConfig:
    """迷宫几何与任务参数。"""

    start: tuple[float, float] = (0.0, 0.0)
    goal: tuple[float, float] = (1.0, 1.0)
    goal_tol: float = 0.08
    bounds: tuple[float, float, float, float] = (-0.15, 1.15, -0.15, 1.15)
    obstacles: tuple[CircleObstacle, ...] = field(default_factory=tuple)
    dt: float = 0.05
    max_steps: int = 80
    max_speed: float = 0.35


def make_maze(scenario: str) -> MazeConfig:
    """三组不同数据场景。"""
    if scenario == "default":
        # 中等障碍，名义路径易擦边
        obs = (
            CircleObstacle((0.45, 0.55), 0.18),
            CircleObstacle((0.70, 0.35), 0.14),
        )
        return MazeConfig(obstacles=obs, max_speed=0.32)
    if scenario == "tight":
        # 更挤、更大障碍
        obs = (
            CircleObstacle((0.40, 0.50), 0.22),
            CircleObstacle((0.65, 0.45), 0.20),
            CircleObstacle((0.55, 0.75), 0.12),
        )
        return MazeConfig(obstacles=obs, max_speed=0.30, goal_tol=0.09)
    if scenario == "aggressive":
        # 名义策略更猛、障碍挡直线
        obs = (
            CircleObstacle((0.50, 0.50), 0.20),
            CircleObstacle((0.30, 0.70), 0.14),
            CircleObstacle((0.75, 0.30), 0.14),
        )
        return MazeConfig(obstacles=obs, max_speed=0.45, dt=0.04, max_steps=100)
    raise ValueError(f"未知场景: {scenario}")


def point_in_obstacle(p: np.ndarray, obstacles: Sequence[CircleObstacle]) -> bool:
    for obs in obstacles:
        if obs.h(p) < 0.0:
            return True
    return False


def min_barrier(p: np.ndarray, obstacles: Sequence[CircleObstacle]) -> float:
    if not obstacles:
        return 0.0
    return float(min(obs.h(p) for obs in obstacles))


def integrate_rollout(
    velocity_fn,
    cfg: MazeConfig,
    seed: int = 0,
) -> dict:
    """单积分器滚动：p_{t+1} = p_t + dt * clip(v)。

    velocity_fn(p, t) -> (2,) 速度。
    """
    rng = np.random.default_rng(seed)
    p = np.asarray(cfg.start, dtype=float).copy()
    traj = [p.copy()]
    violations = 0
    barrier_scores: list[float] = []
    speeds: list[float] = []

    for t in range(cfg.max_steps):
        if point_in_obstacle(p, cfg.obstacles):
            violations += 1
        barrier_scores.append(min_barrier(p, cfg.obstacles))

        v = np.asarray(velocity_fn(p, t), dtype=float).reshape(2)
        # 轻微过程噪声，区分不同 seed 数据
        v = v + rng.normal(0.0, 0.01, size=2)
        speed = float(np.linalg.norm(v))
        if speed > cfg.max_speed:
            v = v * (cfg.max_speed / speed)
        speeds.append(float(np.linalg.norm(v)))
        p = p + cfg.dt * v
        # 边界裁剪
        xmin, xmax, ymin, ymax = cfg.bounds
        p[0] = float(np.clip(p[0], xmin, xmax))
        p[1] = float(np.clip(p[1], ymin, ymax))
        traj.append(p.copy())
        if np.linalg.norm(p - np.asarray(cfg.goal)) <= cfg.goal_tol:
            break

    traj_arr = np.asarray(traj)
    success = bool(np.linalg.norm(traj_arr[-1] - np.asarray(cfg.goal)) <= cfg.goal_tol)
    n_steps = max(len(traj_arr) - 1, 1)
    # 曲率代理：相邻速度方向变化
    if len(traj_arr) >= 3:
        d1 = traj_arr[1:] - traj_arr[:-1]
        d2 = d1[1:] - d1[:-1]
        curvature = float(np.mean(np.linalg.norm(d2, axis=1)))
    else:
        curvature = 0.0

    return {
        "trajectory": traj_arr,
        "success": success,
        "violation_steps": violations,
        "violation_rate": violations / n_steps,
        "mean_barrier": float(np.mean(barrier_scores)) if barrier_scores else 0.0,
        "min_barrier": float(np.min(barrier_scores)) if barrier_scores else 0.0,
        "mean_speed": float(np.mean(speeds)) if speeds else 0.0,
        "curvature": curvature,
        "n_steps": n_steps,
    }
