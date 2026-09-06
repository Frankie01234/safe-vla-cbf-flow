"""后置 E2E-CBF：动作生成完成后再做 QP 投影（对照 Acc-CBF / 项目页 E2E-CBF）。"""

from __future__ import annotations

from typing import Sequence

import cvxpy as cp
import numpy as np

from .cbf_fm_step import CircleObstacle, _as_chunk


def posthoc_project_chunk(
    chunk: np.ndarray,
    obstacles: Sequence[CircleObstacle],
    alpha: float = 2.0,
    margin: float = 0.02,
) -> np.ndarray:
    """对已生成动作块做后置安全投影。

    对每个 waypoint 独立求解：若在障碍内或过近，沿径向推到安全边界外；
    同时用轻量 QP 最小化相对原 chunk 的位移（模拟「生成后再投影」）。
    """
    chunk = _as_chunk(chunk)
    H = chunk.shape[0]
    y = cp.Variable((H, 2))
    cost = cp.sum_squares(y - chunk)
    constraints = []
    for i in range(H):
        p = chunk[i]
        for obs in obstacles:
            c = np.asarray(obs.center, dtype=float)
            r = obs.radius + margin
            d = p - c
            dist = float(np.linalg.norm(d))
            if dist < 1e-8:
                n = np.array([1.0, 0.0])
            else:
                n = d / dist
            # 线性化：n·(y_i - c) ≥ r
            constraints.append(n @ (y[i] - c) >= r)
            # CBF 风格松弛：若已安全，仍保持 n·(y-c) ≥ min(dist, r) 的弱约束已由上式覆盖
            _ = alpha  # 保留接口对称性
    problem = cp.Problem(cp.Minimize(cost), constraints)
    try:
        problem.solve(solver=cp.OSQP, warm_start=True, verbose=False)
    except Exception:
        problem.solve(solver=cp.SCS, verbose=False)

    if y.value is None:
        # 回退：逐点径向推出
        out = chunk.copy()
        for i in range(H):
            for obs in obstacles:
                c = np.asarray(obs.center, dtype=float)
                r = obs.radius + margin
                d = out[i] - c
                dist = float(np.linalg.norm(d))
                if dist < r:
                    if dist < 1e-8:
                        out[i] = c + np.array([r, 0.0])
                    else:
                        out[i] = c + d / dist * r
        return out
    return np.asarray(y.value, dtype=float)
