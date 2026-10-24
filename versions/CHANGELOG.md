# Vflow 版本记录

> 每个版本一个文件，记录改了什么、为什么、影响面。技能里 `version:` 必须和 `VERSION` 一致，
> 跑 `python3 scripts/version.py check` 校验。改了技能没升版本会被判错——防止"改了没记"。

## 版本索引

- [v1.0.0](v1.0.0.md) 2026-10-24 — 首个版本：七阶段流水线，补齐复盘闭环、状态机、最后一公里质检、内容设计层、日历系列化与发布队列

## 版本号怎么用

- **MAJOR**：不兼容的数据/目录结构变化，旧项目需要迁移
- **MINOR**：新增能力或阶段行为变化，旧项目仍能跑
- **PATCH**：修 bug、改文案、补测试

发版流程：`python3 scripts/version.py bump 1.1.0 --note "..."` → 改 `skills/*/SKILL.md` 的 `version`
→ 写 `versions/v1.1.0.md` → `version.py check` → `bash tests/run_regression.sh`。
