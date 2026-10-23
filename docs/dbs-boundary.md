# Vflow 与 dbs-* 的边界定义（2026-10-23）

目的：**Vflow 独立自足，不依赖 dbs 也能跑；装了 dbs 的同学可以在指定节点做二次深检。** 两者不抢触发、不重复造轮子。

## 一、核心区分：三条硬标准

| | Vflow | dbs-* |
|---|---|---|
| **产物** | **必须落文件**到 `projects/<slug>/NN-xx.md`。不落文件等于没做完 | 只出分析和建议，**不落项目文件** |
| **语境** | 只在"做一条内容"时触发（选题→复盘七阶段内） | 通用思考工具：商业诊断、概念拆解、决策跟踪、学习、知识库……内容只是其中一块 |
| **深度** | 够用即可的**闸口**——过关就往下走 | 可调用的**深挖**——想要逐句、想要多角度时用 |

一句话：**Vflow 是流水线，dbs 是外脑。** 流水线自己能跑通；遇到需要深挖的单个点，临时请外脑。

## 二、重叠对照表

### ⚠️ 重叠度极高（必须切干净）

**vflow-package ↔ dbs-title-cover-intro** —— 几乎同一件事

- Vflow 版：文字标题 + 封面标题 + 开头 3 秒三件套，按平台各出一版，检查正文兑现开头承诺，**落 `04-package.md`**
- dbs 版：还能"角度未定时开发并确认主线"、多平台适配更细
- **切法**：流水线内一律用 Vflow 版。只有一种情况转 dbs——**角度还没定、要开发主线时**

**vflow-check ↔ dbs-content-risk-check + dbs-ai-check** —— Vflow 版是这两者的合体简化版

- Vflow 版：三层过（机器风险 / 内容实质 / AI 味），是**发布前必过的一道闸**
- dbs-risk-check 版：**逐句**检查，覆盖标题、正文、图片文字、字幕、口播、评论、账号资料、视频画面
- **切法**：每条都过 Vflow 版。下面两种情况转 dbs：① 内容涉及高风险领域（功效、数据承诺、同行提及）要逐句过；② 平台提示异常需要复查

### 中等重叠（说明清楚就行）

| Vflow | dbs 对应 | 怎么分 |
|---|---|---|
| vflow-topic | dbs-benchmark / dbs-jtbd / dbs-content-value | Vflow 版自带"对标三层筛 + 三问"，产出选题卡。**只想找对标、不想开项目**时用 dbs-benchmark；要深挖观众动机用 dbs-jtbd |
| vflow-script | dbs-script-flow / dbs-resonate | Vflow 版 = 写稿 + 流畅度五项自检。要**逐句找共鸣断点**时用 dbs-resonate |
| vflow-outline | dbs-content / dbs-standard-answer / dbs-theory-grounding | Vflow 版只管结构（每页一个点、一个角色）。需要**理论依据或历史同构比较**时转 dbs |
| vflow-review | dbs-spread | Vflow 版归因"下一条改什么"。**要解释这条为什么爆了**（传播机制）时用 dbs-spread |

### 不重叠（各管各的）

vflow-produce（成片）在 dbs 里没有对等物——dbs 那边的 `srt-whiteboard-animation`（白板动画）、`dbs-video-navigation`（章节导航）是**可选的成片增强**，可作为 produce 阶段的路线补充，不属于 dbs 方法论。

## 三、要落到 SKILL 里的三处改动

### 1. vflow 主入口加一节「与 dbs-* 的分工」

```
## 与其他能力的关系

Vflow **自足**：不装任何 dbs-* 也能跑完整条流水线。开源分发时请保持这个前提。

如果你同时装了 dbs-*，下面四个节点可以做二次深检（可选，不是必须）：
| 节点 | 转用什么 | 什么时候值得转 |
|---|---|---|
| 选题 | dbs-benchmark / dbs-jtbd | 只对标不开项目、或要深挖观众动机 |
| 剧本 | dbs-resonate | 逐句找共鸣断点 |
| 包装 | dbs-title-cover-intro | 角度还没定，要开发主线 |
| 检查 | dbs-content-risk-check | 高风险内容要逐句过 |

反过来：**不要**用 dbs-* 替代 Vflow 的阶段。dbs 不落文件，跑了等于没跑。
```

### 2. vflow-* 的 description 统一加前缀

现在 vflow-check 的 description 是"发布前检查阶段……查敏感词"，和 dbs-content-risk-check 高度撞车。全部改成带流水线语境的前缀：

- vflow-topic → `内容流水线第 1 阶段·选题。……`
- vflow-check → `内容流水线第 5 阶段·发布前检查。……`
- 以此类推

这样 Agent 在"我要发布前检查"时能靠语境区分：带项目、要落文件 → Vflow；只是想让 AI 看看这段文案 → dbs。

### 3. vflow-check 和 vflow-package 里各加一句边界声明

vflow-check：
```
> 这是流水线内的闸口，够用即可。需要逐句深检（含图片文字、字幕、评论、账号资料、视频画面）时，转 dbs-content-risk-check。
```

vflow-package：
```
> 角度已定时用这里。角度还没定、要开发并确认主线时，转 dbs-title-cover-intro。
```

## 四、一条原则

**Vflow 永远保持"零依赖可跑"。** dbs 只作为可选增强存在，不能变成前置条件。这是 Vflow 能开源分发的底线——装了 dbs 的人多一层能力，没装的人一个字都不缺。
