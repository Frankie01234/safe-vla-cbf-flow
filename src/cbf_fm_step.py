"""Flow Matching 去噪步内的 CBF-QP 速度场修正。

对应审查卡口径：滤波只在去噪后段 τ ≥ tau_on（默认 0.6）启动；
用 Log-Sum-Exponential 聚合 action chunk 上多个障碍 barrier，
对名义速度场 v 求最小扰动 δ，使修正后速度满足 CBF 不等式。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import cvxpy as cp
import numpy as np


ArrayLike = np.ndarray


@dataclass(frozen=True)
class CircleObstacle:
    """圆形障碍：安全集为圆外，h(p)=||p-c||^2 - r^2 ≥ 0。"""

    center: tuple[float, float]
    radius: float

    def h(self, p: ArrayLike) -> float:
        d = p - np.asarray(self.center, dtype=float)
        return float(np.dot(d, d) - self.radius**2)

    def grad_h(self, p: ArrayLike) -> ArrayLike:
        return 2.0 * (p - np.asarray(self.center, dtype=float))


@dataclass
class CBFFMConfig:
    """CBF-FM 单步修正超参。"""

    tau_on: float = 0.6
    alpha: float = 2.0
    lse_eps: float = 0.15
    smooth_weight: float = 0.05
    solver_prefer: tuple[str, ...] = ("OSQP", "SCS")


def _as_chunk(x: ArrayLike) -> ArrayLike:
    """将扁平或 (H,2) 动作块统一成 (H, 2)。"""
    arr = np.asarray(x, dtype=float)
    if arr.ndim == 1:
        if arr.size % 2 != 0:
            raise ValueError("动作块维度必须为偶数（H×2）")
        return arr.reshape(-1, 2)
    if arr.ndim == 2 and arr.shape[1] == 2:
        return arr
    raise ValueError(f"不支持的动作块形状: {arr.shape}")


def barrier_values(
    chunk: ArrayLike,
    obstacles: Sequence[CircleObstacle],
) -> ArrayLike:
    """返回形状 (H, n_obs) 的 barrier 值。"""
    chunk = _as_chunk(chunk)
    vals = np.zeros((chunk.shape[0], len(obstacles)), dtype=float)
    for j, obs in enumerate(obstacles):
        for i, p in enumerate(chunk):
            vals[i, j] = obs.h(p)
    return vals


def lse_aggregate_barrier(
    chunk: ArrayLike,
    obstacles: Sequence[CircleObstacle],
    eps: float,
) -> float:
    """对 chunk×障碍 的 barrier 做 soft-min（LSE 聚合）。

    H_LSE = -ε log Σ exp(-h_k / ε)
    当任一 h_k 很负时，H_LSE 也偏负（更不安全）。
    """
    hs = barrier_values(chunk, obstacles).ravel()
    if hs.size == 0:
        return 0.0
    # 数值稳定 soft-min
    scaled = -hs / max(eps, 1e-8)
    m = float(np.max(scaled))
    return float(-eps * (m + np.log(np.sum(np.exp(scaled - m)))))


def _lse_grad_wrt_chunk(
    chunk: ArrayLike,
    obstacles: Sequence[CircleObstacle],
    eps: float,
) -> ArrayLike:
    """∂H_LSE / ∂chunk，形状 (H, 2)。

    soft-min 权重 w_k ∝ exp(-h_k/ε)，∇H = Σ w_k ∇h_k。
    """
    chunk = _as_chunk(chunk)
    H, n_obs = chunk.shape[0], len(obstacles)
    if n_obs == 0:
        return np.zeros_like(chunk)

    hs = barrier_values(chunk, obstacles).ravel()
    scaled = -hs / max(eps, 1e-8)
    m = float(np.max(scaled))
    w = np.exp(scaled - m)
    w = w / np.sum(w)

    grad = np.zeros_like(chunk)
    idx = 0
    for i in range(H):
        for obs in obstacles:
            grad[i] += w[idx] * obs.grad_h(chunk[i])
            idx += 1
    return grad


def barrier_correct_velocity(
    v: ArrayLike,
    x: ArrayLike,
    tau: float,
    tau_on: float = 0.6,
    obstacles: Sequence[CircleObstacle] | None = None,
    alpha: float = 2.0,
    lse_eps: float = 0.15,
    smooth_weight: float = 0.05,
    margin: float = 0.04,
) -> ArrayLike:
    """对 Flow Matching 速度场做 CBF-QP 最小扰动。

    Parameters
    ----------
    v :
        名义速度场，与 x 同形（扁平 2H 或 (H,2)）。
    x :
        当前去噪中间动作块（位置序列）。
    tau :
        去噪时间 ∈ [0, 1]；仅当 tau ≥ tau_on 时修正。
    tau_on :
        审查卡默认 0.6：前段几何语义不可靠，不做滤波。
    obstacles :
        圆形障碍列表；为空则原样返回。
    alpha :
        CBF 类增益，约束 ∇H·(v+δ) + α H ≥ 0。
    lse_eps :
        Log-Sum-Exp 温度。
    smooth_weight :
        相邻时间步速度差惩罚，鼓励平滑 chunk。
    margin :
        障碍膨胀半径，减轻折线弦切穿障。

    Returns
    -------
    修正后的速度场，形状与输入 v 一致。
    """
    v_arr = np.asarray(v, dtype=float)
    x_arr = np.asarray(x, dtype=float)
    out_shape = v_arr.shape

    if tau < tau_on or not obstacles:
        return v_arr.copy()

    # 膨胀障碍，给折线弦留间隙
    fat = tuple(
        CircleObstacle(obs.center, obs.radius + margin) for obs in obstacles
    )

    chunk = _as_chunk(x_arr)
    v_chunk = _as_chunk(v_arr)
    H = chunk.shape[0]
    dim = H * 2

    H_lse = lse_aggregate_barrier(chunk, fat, lse_eps)
    g = _lse_grad_wrt_chunk(chunk, fat, lse_eps).ravel()  # (2H,)

    v0 = v_chunk.ravel()
    delta = cp.Variable(dim)
    # 最小扰动 + 可选平滑：惩罚相邻 waypoint 速度差
    cost = cp.sum_squares(delta)
    if H >= 2 and smooth_weight > 0:
        v_safe = v0 + delta
        v_mat = cp.reshape(v_safe, (H, 2), order="C")
        cost = cost + smooth_weight * cp.sum_squares(v_mat[1:] - v_mat[:-1])

    constraints = [g @ (v0 + delta) >= -alpha * H_lse]
    # 逐点 CBF：每个 waypoint×障碍 单独约束，增强 chunk 内前瞻
    for i in range(H):
        p = chunk[i]
        for obs in fat:
            gh = obs.grad_h(p)
            hi = obs.h(p)
            # ∇h · v_i + α h ≥ 0
            idx = slice(2 * i, 2 * i + 2)
            constraints.append(gh @ (v0[idx] + delta[idx]) >= -alpha * hi)

    problem = cp.Problem(cp.Minimize(cost), constraints)

    status = _solve_qp(problem)
    if status not in (cp.OPTIMAL, cp.OPTIMAL_INACCURATE) or delta.value is None:
        # 不可行时沿 -∇H 做保守回退，避免静默返回不安全速度
        g_norm = float(np.linalg.norm(g)) + 1e-8
        need = max(0.0, -alpha * H_lse - float(g @ v0))
        v_fb = v0 - (need / g_norm**2) * g
        # 额外：对仍在膨胀障碍内的点施加径向逃逸速度
        v_mat = v_fb.reshape(H, 2).copy()
        for i in range(H):
            for obs in fat:
                if obs.h(chunk[i]) < 0:
                    c = np.asarray(obs.center, dtype=float)
                    d = chunk[i] - c
                    dist = float(np.linalg.norm(d)) + 1e-8
                    v_mat[i] = v_mat[i] + (2.0 * alpha) * d / dist
        return v_mat.reshape(out_shape)

    v_corr = (v0 + np.asarray(delta.value, dtype=float)).reshape(out_shape)
    return v_corr


def _solve_qp(problem: cp.Problem) -> str:
    import warnings

    for name in ("OSQP", "SCS"):
        try:
            solver = getattr(cp, name)
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                problem.solve(solver=solver, warm_start=True, verbose=False)
            if problem.status in (cp.OPTIMAL, cp.OPTIMAL_INACCURATE):
                return str(problem.status)
        except Exception:
            continue
    return str(problem.status)


def cbf_holds(
    v: ArrayLike,
    x: ArrayLike,
    obstacles: Sequence[CircleObstacle],
    alpha: float = 2.0,
    lse_eps: float = 0.15,
    tol: float = 1e-5,
) -> bool:
    """检查 ∇H·v + α H ≥ -tol。"""
    chunk = _as_chunk(x)
    v_chunk = _as_chunk(v)
    H_lse = lse_aggregate_barrier(chunk, obstacles, lse_eps)
    g = _lse_grad_wrt_chunk(chunk, obstacles, lse_eps).ravel()
    return float(g @ v_chunk.ravel() + alpha * H_lse) >= -tol
