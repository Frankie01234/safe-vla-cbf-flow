"""玩具 Flow Matching：生成朝向目标、但可能穿障的动作块，再沿块开环/半闭环执行。"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .cbf_fm_step import CircleObstacle, barrier_correct_velocity
from .maze2d import MazeConfig


@dataclass
class FlowConfig:
    """去噪积分超参。"""

    horizon: int = 12
    n_steps: int = 20
    tau_on: float = 0.6
    alpha: float = 2.0
    lse_eps: float = 0.15
    smooth_weight: float = 0.08
    # 名义场对障碍「吸引力」：模拟不安全 VLA 捷径
    obstacle_attraction: float = 0.35


def _straight_chunk(start: np.ndarray, goal: np.ndarray, horizon: int) -> np.ndarray:
    ts = np.linspace(0.0, 1.0, horizon)
    return (1.0 - ts)[:, None] * start[None, :] + ts[:, None] * goal[None, :]


def nominal_velocity_field(
    x: np.ndarray,
    tau: float,
    target_chunk: np.ndarray,
    obstacles: tuple[CircleObstacle, ...],
    attraction: float,
) -> np.ndarray:
    """名义 FM 速度：拉向目标轨迹 + 对障碍中心的错误吸引（制造违规）。

    在条件流匹配中，理想速度约为 (x1 - x) / (1-τ)；这里加障碍吸引制造不安全捷径。
    """
    x = np.asarray(x, dtype=float).reshape(-1, 2)
    remain = max(1.0 - tau, 1e-3)
    v = (target_chunk - x) / remain
    if attraction > 0 and obstacles:
        for obs in obstacles:
            c = np.asarray(obs.center, dtype=float)
            # 距离障碍越近，错误吸引越强（模拟危险捷径偏好）
            for i in range(x.shape[0]):
                d = c - x[i]
                dist = float(np.linalg.norm(d)) + 1e-6
                # 只在直线目标附近才吸引，避免全局塌缩
                pull = attraction * np.exp(-((dist - obs.radius) ** 2) / 0.08)
                v[i] = v[i] + pull * d / dist
    return v


def sample_action_chunk(
    start: np.ndarray,
    cfg: MazeConfig,
    flow: FlowConfig,
    mode: str,
    rng: np.random.Generator,
) -> tuple[np.ndarray, dict]:
    """从噪声积分到动作块。

    mode:
      - none: 无安全修正
      - cbf_fm: 去噪后段内嵌 CBF-QP
    """
    start = np.asarray(start, dtype=float)
    goal = np.asarray(cfg.goal, dtype=float)
    target = _straight_chunk(start, goal, flow.horizon)
    # 轻微扰动目标，形成不同「数据」样本
    target = target + rng.normal(0.0, 0.02, size=target.shape)

    x = rng.normal(0.0, 1.0, size=target.shape)  # τ=0 噪声
    dt = 1.0 / flow.n_steps
    n_corrected = 0
    qp_ms = 0.0

    for k in range(flow.n_steps):
        tau = k * dt
        v = nominal_velocity_field(
            x,
            tau,
            target,
            cfg.obstacles,
            flow.obstacle_attraction,
        )
        if mode == "cbf_fm":
            import time

            t0 = time.perf_counter()
            v = barrier_correct_velocity(
                v,
                x,
                tau=tau,
                tau_on=flow.tau_on,
                obstacles=cfg.obstacles,
                alpha=flow.alpha,
                lse_eps=flow.lse_eps,
                smooth_weight=flow.smooth_weight,
            )
            qp_ms += (time.perf_counter() - t0) * 1000.0
            if tau >= flow.tau_on:
                n_corrected += 1
        elif mode != "none":
            raise ValueError(f"未知采样模式: {mode}")
        x = x + dt * v

    meta = {
        "n_corrected_steps": n_corrected,
        "qp_ms_total": qp_ms,
        "qp_ms_mean": qp_ms / max(n_corrected, 1),
    }
    return x, meta


def chunk_to_velocity_policy(chunk: np.ndarray, cfg: MazeConfig):
    """把生成的位置块转成跟踪速度策略（开环索引 + 局部反馈）。"""
    chunk = np.asarray(chunk, dtype=float).reshape(-1, 2)

    def velocity_fn(p: np.ndarray, t: int) -> np.ndarray:
        # 按时间推进参考点，并加 P 控制
        idx = min(t, len(chunk) - 1)
        ref = chunk[idx]
        # 若已接近当前点，跳到更远的 waypoint
        while idx < len(chunk) - 1 and np.linalg.norm(p - chunk[idx]) < 0.05:
            idx += 1
            ref = chunk[idx]
        v = 2.5 * (ref - p)
        # 终点吸引，防止卡在中间 waypoint
        v = v + 1.2 * (np.asarray(cfg.goal) - p)
        return v

    return velocity_fn
