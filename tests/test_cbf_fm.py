"""合同与机制单元测试。"""

from __future__ import annotations

import numpy as np
import pytest

from src.cbf_fm_step import (
    CircleObstacle,
    barrier_correct_velocity,
    cbf_holds,
    lse_aggregate_barrier,
)
from src.evaluate import evaluate_methods
from src.flow_matching import FlowConfig


def test_tau_below_on_returns_identity():
    obs = [CircleObstacle((0.0, 0.0), 0.3)]
    x = np.array([[0.1, 0.0], [0.2, 0.0], [0.3, 0.0]])
    # 指向障碍中心的不安全速度
    v = np.array([[-1.0, 0.0], [-1.0, 0.0], [-1.0, 0.0]])
    out = barrier_correct_velocity(v, x, tau=0.3, tau_on=0.6, obstacles=obs)
    assert np.allclose(out, v)


def test_tau_on_makes_barrier_nondecreasing_condition():
    obs = [CircleObstacle((0.0, 0.0), 0.25)]
    # 点在障碍外但速度冲向中心
    x = np.array([[0.40, 0.0], [0.42, 0.0], [0.44, 0.0]])
    v = np.array([[-2.0, 0.0], [-2.0, 0.0], [-2.0, 0.0]])
    assert not cbf_holds(v, x, obs, alpha=2.0)

    v2 = barrier_correct_velocity(v, x, tau=0.7, tau_on=0.6, obstacles=obs, alpha=2.0)
    assert cbf_holds(v2, x, obs, alpha=2.0, tol=1e-4)
    # 扰动应相对最小：不应完全反向到离谱
    assert float(np.linalg.norm(v2 - v)) < float(np.linalg.norm(v)) * 2.5


def test_lse_negative_inside_obstacle():
    obs = [CircleObstacle((0.5, 0.5), 0.2)]
    inside = np.array([[0.5, 0.5], [0.52, 0.5]])
    outside = np.array([[0.0, 0.0], [1.0, 1.0]])
    assert lse_aggregate_barrier(inside, obs, eps=0.1) < 0
    assert lse_aggregate_barrier(outside, obs, eps=0.1) > 0


def test_evaluate_cbf_fm_reduces_violations():
    flow = FlowConfig(horizon=10, n_steps=16, obstacle_attraction=0.45)
    summary = evaluate_methods("default", n_trials=8, seed=7, flow=flow)
    none_v = summary["methods"]["none"]["mean_violation_rate"]
    fm_v = summary["methods"]["cbf_fm"]["mean_violation_rate"]
    none_inside = summary["methods"]["none"]["mean_chunk_inside"]
    fm_inside = summary["methods"]["cbf_fm"]["mean_chunk_inside"]
    assert fm_inside <= none_inside + 1e-9
    assert fm_v < none_v - 0.02
    assert summary["methods"]["cbf_fm"]["mean_chunk_min_barrier"] > summary["methods"]["none"][
        "mean_chunk_min_barrier"
    ] - 1e-6
