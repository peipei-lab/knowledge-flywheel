# Creator 个人知识库闭环：从自动化工厂到认知强化学习系统

## 核心判断

这套系统不应该只是“AI 自动抓取、总结、写文章”。那样很容易变成 Karpathy 知识库笔记里批评的高级收藏夹：内容越来越多，图谱越来越漂亮，但 Creator 的第一大脑没有真正变强。

更合理的目标是：

> AI 负责探索、整理、尝试和生成；Creator 负责选择、反馈、判断和修正。系统通过这些反馈逐渐学习 Creator 的偏好、风格、问题意识和判断标准，最后变成一个会和 Creator 一起进化的第二大脑。

这很像 reinforcement learning，但 reward 不是一个抽象分数，而是 Creator 的真实选择：

- 哪些材料值得进入 raw/
- 哪些总结是“有用但没击中我”
- 哪些洞察值得变成知识原子
- 哪些选题值得发布
- 哪些表达像 Creator，哪些只是 AI 腔
- 哪些内容发布后得到高质量反馈

## 新闭环

旧闭环：

```text
Input -> Summarize -> Draft -> Publish -> Archive
```

升级后：

```text
Explore -> Distill -> Propose -> Creator Feedback -> Preference Memory -> Regenerate -> Publish -> Outcome Feedback -> Update Taste Model
```

## 系统角色分工

### AI 的工作

- Search：搜索 podcast、文章、Huaren、小红书、电子书等候选素材
- Try：自动抓取、摘要、聚类、生成多个选题和多个表达版本
- Connect：把新材料连接到已有知识原子、问题库、长期母题
- Lint：定期检查知识库里的重复、矛盾、过时观点和空洞收藏
- Draft：生成小红书、长文、视频脚本、评论回复等候选输出

### Creator 的工作

- Curate：决定什么值得进入系统
- Ask：提出真正想追的问题
- Think：判断 AI 的提炼是否击中真实机制
- Reward：选择、打分、批注、删除、重写关键句
- Live：把科学家妈妈的真实经验、情绪和判断放进去

## 四类反馈信号

### 1. Material Feedback / 素材反馈

Creator 对输入材料做选择：

- `keep`: 值得进入知识库
- `skip`: 噪声、重复、低价值
- `maybe`: 先暂存，未来看是否反复出现
- `source_quality`: 信息源质量评分

系统学习：什么样的内容源、标题、问题、讨论场景更容易被 Creator 认为有价值。

### 2. Insight Feedback / 洞察反馈

Creator 对 AI 总结做反馈：

- `hit`: 击中了核心机制
- `miss`: 摘要正确但没有洞察
- `too_generic`: 太泛
- `too_technical`: 技术细节太多，没转成妈妈/女性视角
- `needs_emotion`: 缺 Creator 的真实感受
- `needs_evidence`: 判断太快，证据不足

系统学习：Creator 认可的“好洞察”不是信息压缩，而是能解释生活痛点的机制。

### 3. Voice Feedback / 风格反馈

Creator 对文案表达做反馈：

- `sounds_like_me`
- `too_ai`
- `too_marketing`
- `too_harsh`
- `too_soft`
- `more_scientist`
- `more_mother`
- `more_practical`

系统学习：Creator 的声音不是一个固定模板，而是在“硬核科学判断”和“真实妈妈经验”之间动态调节。

### 4. Outcome Feedback / 外部反馈

发布后的数据和评论进入系统：

- 收藏、评论、转发、私信问题
- 哪些评论代表真实痛点
- 哪些争论点值得发展成长青文章
- 哪些内容只带来流量但不建立信任

系统学习：不是所有高流量都等于高价值。真正要优化的是“吸引对的人”和“形成长期信任”。

## 新增知识库模块

建议在 `insight_vault` 中增加这些长期文件：

```text
30_Creator_Feedback/
  feedback_log.md
  rejected_ideas.md
  style_corrections.md

40_Preference_Model/
  taste_profile.md
  voice_profile.md
  topic_weights.md
  source_quality.md

50_Lint/
  weekly_lint.md
  stale_atoms.md
  contradiction_log.md
```

## Reward Record 格式

每次 Creator 只需要给非常轻量的反馈，不需要写长评：

```markdown
## Feedback

- Item:
- Decision: keep / skip / rewrite / publish
- Score: 1-5
- Why:
- Better angle:
- Voice correction:
- Next action:
```

这比“手动改整篇文章”更重要，因为它会变成系统的训练数据。

## Raw Feedback 是不可变训练数据

Creator 的原始反馈必须作为 raw event 长期保存，不能只保留总结后的偏好规则。总结会错，模型会漂移，但原始反馈可以被重新分析。

保存位置：

```text
insight_vault/30_Creator_Feedback/raw_feedback_events.jsonl
insight_vault/30_Creator_Feedback/feedback_event_schema.md
```

保存原则：

- 只追加，不覆盖。
- 保存 Creator 原始反馈文本。
- 保存候选内容上下文、source path、decision、score、tags、rewrite instruction。
- 对准备发布的文章，保存 draft review、revision round、blocking issues、before/after draft path 和 publish decision。
- 每轮 revision 都单独存档，不能覆盖旧稿；版本轨迹本身就是 Creator 发布标准的训练数据。
- 保存派生维度，但派生维度不能替代原始反馈。
- 具体事件留在 Obsidian；只有长期稳定偏好才适合进入 Codex memory。

这些 raw feedback 以后可以从不同维度分析：

- topic preference
- voice preference
- source quality
- rejection patterns
- publishability signals
- life reflection value
- draft revision patterns
- publish decision standards
- what should become memory

## Preference Model 应该长什么样

`taste_profile.md` 不应该是静态人设，而是不断更新的偏好模型：

```markdown
# Creator Taste Profile

## High Reward

- AI 技术变化能解释孩子未来学习方式的变化
- 能把抽象模型转成妈妈今天可做的判断
- 有科学机制，但不炫技
- 有真实个人感受，不装权威
- 能指出流行方法的误区，同时给出温和可执行替代方案
- 能从 AI、育儿或职业问题继续推进到人生选择、自我理解和长期成长

## Low Reward

- 只总结新闻，没有 Creator 判断
- 只讲工具教程，没有认知升级
- 只堆概念，没有生活落点
- 过度营销式标题
- 把 AI 当万能解法

## Current Topic Weights

- AI x 育儿判断: high
- AI x 女性职业发展: high
- AI x 人生思考: high
- AI x 知识管理/第二大脑: medium-high
- 纯模型架构新闻: low unless linked to education/work
```

## Lint / 健康检查

Karpathy 笔记里最重要但最容易被忽略的是 lint。对 Creator 系统来说，lint 不是代码检查，而是认知健康检查：

- 哪些知识原子只是漂亮收藏，没有被任何文章使用过？
- 哪些观点互相矛盾？
- 哪些 source 最近带来的都是低价值噪声？
- 哪些 topic 只是流量诱惑，不符合 Creator 长期定位？
- 哪些表达越来越像 AI，而不是 Creator？
- 哪些高频问题还没有形成清晰解法？

每周 lint 的输出应该直接给出三类建议：

- Delete：删掉或归档低价值收藏
- Merge：合并重复知识原子
- Deepen：值得 Creator 人工思考 10 分钟的问题

## 最小可行升级

下一步不需要立刻做复杂模型训练。先做一个轻量版本：

1. 每次生成候选内容时，同时生成 3 个不同角度。
2. Creator 选择其中一个，或标记全部不对。
3. 系统把选择和理由写入 `feedback_log.md`。
4. 每周根据反馈更新 `taste_profile.md` 和 `voice_profile.md`。
5. 下一次生成内容时，prompt 自动读取最新偏好文件。

这就是“人类反馈强化学习”的个人知识库版本。

## 判断标准

系统成功不是因为它自动生成了更多内容，而是因为：

- Creator 需要改的字越来越少
- AI 提出的选题越来越像 Creator 真会关心的问题
- 知识原子越来越能反复复用
- 发布内容越来越能吸引目标人群
- Creator 的第一大脑越来越清楚自己真正相信什么

最终目标：

> 第二大脑不是替代第一大脑，而是让第一大脑看见自己的判断如何形成、如何修正、如何进化。
