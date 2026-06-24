# HITL + Preference Learning Implementation Plan

## 目标

把当前 Brand Factory 从“自动抓取/总结/输出”升级为：

> AI 自动探索和生成候选，Creator 用很轻量的方式选择、打分、批注；系统记录反馈并更新偏好模型，让下一轮内容越来越贴近 Creator 的判断、风格和长期定位。

## Phase 1: Review Inbox MVP

### 要实现什么

创建一个本地 Review Inbox，把 AI 生成的候选内容集中给 Creator 审阅。

候选来源：

- Huaren 搜索/评论分析
- 小红书手动导入分析
- RSS/podcast/blog 周报
- 电子书章节分析
- NotebookLM 输出

每个候选卡片包含：

- 标题
- 来源
- AI 推荐理由
- 一句话核心洞察
- 可能发展成的小红书/长文/视频角度
- 当前 ranking score
- 原始材料和分析文件链接

### 文件结构

```text
insight_vault/
  60_Review_Inbox/
    candidates.jsonl
    reviewed/
    archived/
```

### 先做的脚本

```text
scripts/build_review_inbox.py
```

职责：

- 扫描 `insight_vault/10_Analyses`
- 从分析文件中提取候选 insight
- 计算初始 ranking score
- 写入 `60_Review_Inbox/candidates.jsonl`

## Phase 2: Scoring / Ranking

### 初始 ranking 公式

```text
score =
  0.22 * creator_fit
+ 0.20 * mechanism_value
+ 0.15 * emotional_density
+ 0.15 * reusability
+ 0.10 * novelty
+ 0.10 * contradiction_value
+ 0.05 * life_reflection_value
+ 0.03 * source_quality
```

### 信号解释

- `creator_fit`: 是否连接 AI x 育儿 x 女性职业 x 人生思考
- `mechanism_value`: 是否能提炼底层机制
- `emotional_density`: 是否来自真实痛点/评论区争论
- `reusability`: 是否能变成知识原子或长青选题
- `novelty`: 是否不是重复观点
- `contradiction_value`: 是否挑战已有观点
- `life_reflection_value`: 是否能引出关于选择、不确定性、自我理解、长期成长的人生思考
- `source_quality`: 来源历史质量

第一版可以先用规则和关键词打分；之后再结合 Creator 反馈调整权重。

## Phase 3: Feedback UI

### 推荐技术

第一版用 Streamlit 或本地静态 HTML + Flask/FastAPI。

我建议先用 Streamlit：

- 实现快
- 本地运行
- 适合卡片、按钮、评分、文本框
- 不需要复杂前端工程

### 页面

```text
1. Review Inbox
2. Candidate Detail
3. Feedback Panel
4. Preference Dashboard
```

### Feedback Panel 字段

```text
Decision:
  keep / skip / rewrite / publish / deepen

Scores:
  relevance: 1-5
  insight: 1-5
  voice_match: 1-5
  publishability: 1-5

Tags:
  too_generic
  too_technical
  too_ai
  too_marketing
  lacks_life_angle
  strong_mechanism
  sounds_like_creator
  worth_deepening

Free note:
  Creator 为什么喜欢/不喜欢？
```

### Draft Review Mode

除了候选卡片快速反馈，还需要支持文章级 review。Creator 经常会 review AI 写的、准备发到 Pages 或其他渠道的文章，给出结构、论证、标题、声音、发布风险等详细建议。这类反馈比简单打分更接近真实 human alignment 数据。

Draft Review 需要保存：

- draft path before
- draft path after
- publish target
- revision round
- blocking issues
- raw detailed feedback
- rewrite instruction
- publish decision
- every draft version and feedback version

模板见：

```text
insight_vault/30_Creator_Feedback/draft_review_template.md
```

每轮修改归档到：

```text
insight_vault/70_Draft_Revisions/{article_slug}/
  v01-draft.md
  v01-feedback.md
  v02-draft.md
  v02-feedback.md
  v03-approved.md
  revision_summary.md
```

实现时禁止覆盖旧版本。每次 AI 根据 Creator 反馈修改文章，都创建新版本文件，并追加一条 raw feedback event。

### 输出文件

```text
insight_vault/30_Creator_Feedback/feedback_log.md
insight_vault/30_Creator_Feedback/raw_feedback_events.jsonl
insight_vault/30_Creator_Feedback/feedback_event_schema.md
```

`raw_feedback_events.jsonl` 是最重要的 RL / preference learning 原始数据，必须只追加，不覆盖。`feedback_log.md` 给 Obsidian 阅读，所有 taste/voice/source profile 都只是从 raw feedback 派生出来的模型。

### Raw Feedback 保存原则

- 保存 Creator 的原始反馈文本，不只保存摘要。
- 保存选择、拒绝、打分、标签、文章级修改建议、改写指令和上下文 source path。
- 保存派生维度，但不能用派生维度替代原始反馈。
- 未来如果偏好模型总结错了，必须能从 raw feedback 重新分析。
- 只有长期稳定偏好才考虑进入 Codex memory；具体事件仍然留在 Obsidian。

## Phase 4: Preference Update

### 要实现什么

根据 Creator 的反馈，定期更新：

```text
insight_vault/40_Preference_Model/taste_profile.md
insight_vault/40_Preference_Model/voice_profile.md
insight_vault/40_Preference_Model/source_quality.md
```

### 脚本

```text
scripts/update_preference_model.py
```

职责：

- 读取 `raw_feedback_events.jsonl`
- 聚合高分/低分模式
- 提炼偏好规则
- 更新 taste/voice/source profiles

### 第一版策略

先不做真正神经网络训练，而做可解释 alignment：

- 高分内容总结成 `High Reward`
- 低分内容总结成 `Low Reward`
- 反复出现的批注变成 generation rules
- source 的平均分进入 `source_quality.md`

## Phase 5: Generation Uses Preference

### 要实现什么

所有生成类脚本在输出前读取：

```text
40_Preference_Model/taste_profile.md
40_Preference_Model/voice_profile.md
30_Creator_Feedback/rejected_ideas.md
```

然后生成：

- 3 个不同角度候选
- 每个候选说明为什么适合 Creator
- 每个候选标注使用了哪些偏好规则

### 需要改的脚本

```text
scripts/build_brief.py
scripts/make_social.py
scripts/analyze_capture_file.py
scripts/analyze_ebook.py
```

## Phase 6: Cognitive Lint

### 脚本

```text
scripts/cognitive_lint.py
```

### 检查内容

- 哪些知识原子从未被复用
- 哪些候选反复被拒绝
- 哪些 source 低质量
- 哪些内容越来越像 AI 腔
- 哪些长期问题反复出现但没有形成 Creator 解法
- 哪些观点互相矛盾

输出：

```text
insight_vault/50_Lint/YYYY-MM-DD-cognitive-lint.md
```

## 统一入口需要新增的菜单

当前 `brand_factory.py` 可以新增：

```text
11. 构建 Review Inbox
12. 打开 HITL Review UI
13. 更新 Creator 偏好模型
14. 运行认知健康检查
```

维护项仍然保留在 90+。

## MVP 顺序

最小可行版本建议按这个顺序做：

1. `build_review_inbox.py`
2. `feedback_events.jsonl` + `feedback_log.md`
3. Streamlit Review UI
4. `update_preference_model.py`
5. 让 `make_social.py` 读取 preference model
6. `cognitive_lint.py`

## 成功标准

不是“生成更多内容”，而是：

- Creator 每次只需要审 5-8 个候选
- Creator 反馈时间控制在 10-15 分钟
- AI 生成内容被拒绝的原因越来越少重复
- `taste_profile.md` 和 `voice_profile.md` 越来越具体
- 小红书/长文/视频草稿越来越少需要大改
- 知识库不再只是收藏，而是在记录 Creator 判断如何进化
