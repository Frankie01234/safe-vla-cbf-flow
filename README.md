# safe-vla-cbf-flow

Safe VLA：在 Flow Matching 内嵌 CBF 安全约束（仿真机制复现，等级 **C→B**）。

- **项目页：** https://safe-vla-fmcbf.netlify.app/
- **匿名仓（硬件）：** https://anonymous.4open.science/r/diffusion_cbf-1B55/README.md
- **匿名仓（Maze）：** https://anonymous.4open.science/r/maze2d_safe_fm-AA6C/README.md
- **审查卡：** `Safe VLA：在 Flow Matching 内嵌 CBF 安全约束_26.08.04_卡.md`
- **复现方案：** [复现方案.md](./复现方案.md)
- **对照笔记：** [notes/vs-acc-cbf.md](./notes/vs-acc-cbf.md)

## 本仓库做了什么

1. 实现 `barrier_correct_velocity`：仅在去噪后段 \(\tau \ge 0.6\) 对速度场做 CBF-QP 最小扰动。
2. 用 Log-Sum-Exp 聚合 action chunk × 圆形障碍的 barrier。
3. 在自造 2D Maze 单积分器上对照三种插入位置：无过滤 / 后置 E2E-CBF / CBF-FM。
4. 三组不同数据（default / tight / aggressive）各跑完整日志与 JSON。
5. 文字对比 Acc-CBF：**生成内修正 vs 动作后置投影**（只读引用，不复制真机主张）。

## 快速复现

```powershell
pip install -r requirements.txt
python -m pytest tests/ -q
python scripts/run_experiments.py
```

输出：

- `logs/run0*.log`、`logs/MASTER_RUN.md`
- `results/run0*.json`、`results/summary_three_runs.json`

## 指标口径（诚实声明）

| 项目页 / 论文主张 | 本仓库 |
|------------------|--------|
| π₀ + SO-101 / QArm 真机 | 不做真机、不微调 π₀ |
| 匿名 Maze2D 官方代码 | Cloudflare 挡匿名仓，按审查卡机制自实现 |
| 真机 100% 安全率 | **禁止**写入本机结果表 |
| E2E-CBF 后置滤波 | 本仓库用动作块后置 QP 投影近似 |

## 明确未做

- SO-101 / QArm 真机与 LeRobot 微调
- 官方匿名仓库完整 clone（访问被拦时降级为机制自实现）
- 把项目页硬件表数字当作本机复现结果
