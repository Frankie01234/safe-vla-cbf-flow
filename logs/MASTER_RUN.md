# Safe VLA CBF-FM — 三组实验主日志

- 工作目录: `F:\Git_Projects\safe-vla-cbf-flow`
- 平台: `Windows-11-10.0.26200-SP0`
- Python: `3.13.14`
- 开始时间: `2026-09-07 00:53:10`

## run01_default_seed7

- scenario=`default` seed=`7` trials=`24`
- 中等障碍迷宫；名义场带障碍吸引，制造无过滤违规。
-   - none: success=1.000, viol=0.234, chunk_inside=2.50, chunk_min_h=-0.026, mean_h=0.162, curv=0.0006, qp_ms=0.00
-   - e2e_cbf: success=1.000, viol=0.036, chunk_inside=0.00, chunk_min_h=0.020, mean_h=0.177, curv=0.0014, qp_ms=0.00
-   - cbf_fm: success=0.792, viol=0.033, chunk_inside=0.00, chunk_min_h=0.162, mean_h=0.349, curv=0.0073, qp_ms=15.33
- 结论: 违规率 none=0.234 / e2e=0.036 / cbf_fm=0.033。口径：CBF-FM=生成内修正；E2E=动作块后置投影（类 Acc-CBF 后置叙事）；禁止把本机玩具迷宫数字写成项目页真机 100% 安全率。
- 结果文件: `run01_default_seed7.json` 耗时 3.5s

## run02_tight_seed42

- scenario=`tight` seed=`42` trials=`24`
- 更挤三障场景，检验 LSE 聚合与后置投影差异。
-   - none: success=1.000, viol=0.355, chunk_inside=6.17, chunk_min_h=-0.042, mean_h=0.083, curv=0.0007, qp_ms=0.00
-   - e2e_cbf: success=1.000, viol=0.070, chunk_inside=0.12, chunk_min_h=0.006, mean_h=0.097, curv=0.0016, qp_ms=0.00
-   - cbf_fm: success=0.833, viol=0.100, chunk_inside=1.04, chunk_min_h=0.079, mean_h=1.974, curv=0.0089, qp_ms=51.87
- 结论: 违规率 none=0.355 / e2e=0.070 / cbf_fm=0.100。口径：CBF-FM=生成内修正；E2E=动作块后置投影（类 Acc-CBF 后置叙事）；禁止把本机玩具迷宫数字写成项目页真机 100% 安全率。
- 结果文件: `run02_tight_seed42.json` 耗时 10.8s

## run03_aggressive_seed123

- scenario=`aggressive` seed=`123` trials=`24`
- 更高速度与更强障碍吸引，压力测试去噪后段 CBF-FM。
-   - none: success=1.000, viol=0.306, chunk_inside=3.96, chunk_min_h=-0.038, mean_h=0.140, curv=0.0006, qp_ms=0.00
-   - e2e_cbf: success=1.000, viol=0.056, chunk_inside=0.00, chunk_min_h=0.022, mean_h=0.162, curv=0.0017, qp_ms=0.00
-   - cbf_fm: success=0.792, viol=0.058, chunk_inside=0.00, chunk_min_h=0.139, mean_h=0.348, curv=0.0078, qp_ms=29.51
- 结论: 违规率 none=0.306 / e2e=0.056 / cbf_fm=0.058。口径：CBF-FM=生成内修正；E2E=动作块后置投影（类 Acc-CBF 后置叙事）；禁止把本机玩具迷宫数字写成项目页真机 100% 安全率。
- 结果文件: `run03_aggressive_seed123.json` 耗时 7.3s

## 汇总

- `summary.json` / `summary_three_runs.json` 已写入
- 结束时间: `2026-09-07 00:53:31`
