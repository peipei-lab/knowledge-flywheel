# Creator 自动化内容加工厂：执行手册

## 核心定位

你不是做「AI 新闻搬运」，而是做：

> 用硬核 AI 科学家妈妈的视角，把全球 AI 变化翻译成中文女性、妈妈、职业女性能用的判断，并延伸到 AI 时代如何生活、选择和成长的人生思考。

每篇内容都要过三层滤镜：

1. 硬核层：原文真正说了什么？技术或产业逻辑是什么？
2. 应用层：这对育儿、孩子学习、女性职业发展和人生选择意味着什么？
3. 情感层：Creator 作为科学家妈妈，真实想说什么？

## 每周 1-2 小时节奏

### 周一：热点周报

1. 跑 `bash scripts/weekly_run.sh`
2. 打开 `content/briefs/YYYY-MM-DD-weekly-brief.md`
3. 从素材里只保留 1-3 个最有 Creator 观点的话题
4. 在 `Creator 人工补充区` 写 3-6 句真实感慨
5. 打开 `content/knowledge/atoms/YYYY-MM-DD-knowledge-atoms.md`，确认哪些观点值得进入第二大脑
6. 打开 `content/knowledge/reflections/YYYY-MM-DD-cognitive-reflection.md`，看本周观点如何更新你的认知
7. 发小红书/朋友圈/X
8. 按 `content/social/*-video-outline.md` 录 3-5 分钟短视频

### 每两周：长青思考

从两周 weekly brief 里挑一个反复出现的母题，例如：

- AI 会不会让孩子更不会思考？
- 未来妈妈该不该教孩子编程？
- 职业女性如何把 AI 变成专业杠杆，而不是焦虑来源？
- AI 时代，什么能力仍然值得慢慢培养？
- AI 时代，普通人如何保持判断力、主体性和长期主义？

长青文不追求快，目标是建立你的思想护城河。

## 选题降维公式

不要说：

> 这个 AI 模型架构更新了。

要说：

> 这个模型背后的逻辑变了，意味着孩子未来学编程，可能不再是背语法，而是学会描述问题、拆解问题、验证答案。

每个选题都用这个句式检查：

> 这个 AI 变化，会如何改变一个妈妈今天的育儿判断、一个女性明年的职业选择、一个孩子十年后需要的能力？

## Creator 观点模板

可以直接填空：

> 我不觉得这件事最重要的是「___」。真正重要的是「___」。
>
> 作为 AI 科学家，我看到的是「___」；但作为妈妈，我更关心的是「___」。
>
> 所以这周我给自己的提醒是：不要急着让孩子追工具，而是先陪他/她练习「___」。

## 发布矩阵

### 小红书

重点：标题和封面要把技术翻译成生活问题。

格式：

- 1 个清晰标题
- 1 张封面：一句人话问题
- 3 个 AI 变化
- 每个变化都配 Creator 观点
- 结尾问一个和妈妈/女性生活相关的问题

### X/Twitter

重点：建立专业判断。

格式：

- 第一条：这周的总判断
- 中间：3 个观点，每个都连回「孩子/妈妈/女性工作」
- 最后：一个可执行的小行动

### YouTube / Shorts

重点：真人 IP。

不要追求完美脚本。只讲：

1. 这周我看到一个 AI 变化
2. 它表面上是技术，实际上和我们的孩子/工作有关
3. 我的判断是什么
4. 这周你可以做的一件小事

## 成功标准

不是每周发很多篇，而是半年后你拥有：

- 20-30 份 AI 热点周报
- 10-15 篇长青思考
- 一套属于 Creator 的「AI x 育儿 x 女性职业 x 人生思考」思想数据库
- 一个中文互联网稀缺的专业女性导师形象

## 知识回流闭环

这套系统不能只负责“发出去”，还要负责“长回来”。

更进一步，它不应该只是自动化内容工厂，而应该是一个带反馈回路的认知强化学习系统：

> AI 负责搜索、尝试、总结、连接和生成；Creator 负责选择、反馈、判断和修正。系统通过这些反馈逐渐学习 Creator 的偏好、风格、问题意识和判断标准。

这意味着每次“不是我想要的”都不是失败，而是一条训练信号。你挑选、删除、打分、改写、补一句真实感受，都会帮助第二大脑更接近你的第一大脑。

详细架构见 `COGNITIVE_RL_ARCHITECTURE.md`。

每周发布前后，都要把内容拆成三类资产：

- Knowledge Atom：一个可复用的认知模块，例如“迭代优化可以迁移到育儿习惯培养”
- Problem Block：一个长期问题，例如“如何把论坛里的高频焦虑转化成长青选题”
- Reflection：本周 Creator 的观点发生了强化、补充，还是修正

这样半年后积累的不是一堆孤立文章，而是一套能被检索、重组、继续进化的第二大脑。

## 论坛洞察管线

论坛不是随便刷的信息流，而是真实生活痛点数据库。

Huaren 论坛抓取采用“按需启动”原则：

- 你提供关键词，系统搜索公开列表页候选帖子
- 你提供一段提示词，系统先本地抽取关键词，再搜索候选帖子
- 系统默认只保存标题、链接、板块、匹配关键词等元数据
- 不默认保存完整帖子正文，不复制网友个人经历

判断一个论坛话题是否值得进入选题库，看三个指标：

- 高频率：类似问题是否反复出现
- 高情绪密度：回复里是否有大量真实经历和强烈情绪
- 低解法成熟度：大家是否都在抱怨，但缺少系统解法

遇到高价值帖子时，不要只保存链接，要把它转成 Problem Block：

```markdown
## 问题
大家反复在问什么？

## 情绪
背后最强的焦虑是什么？

## 机制
这个问题背后是沟通问题、反馈回路问题、认知负荷问题，还是资源分配问题？

## Creator 解法
能否用 AI/科学家妈妈视角给出一个可执行方法？
```

启动示例：

```bash
python3 scripts/search_huaren.py --keywords "孩子,AI,教育,职场" --no-ai
python3 scripts/search_huaren.py --prompt "我想找北美华人妈妈关于孩子AI时代学习、编程、升学焦虑的真实讨论" --no-ai
python3 scripts/sync_obsidian.py
```

当你从候选列表里挑出一个值得看的帖子，可以继续抓公开帖子页和评论区短摘录：

```bash
python3 scripts/fetch_huaren_thread.py "https://huaren.us/showtopic.html?topicid=3194904&fid=333" --pages 1 --no-ai
python3 scripts/sync_obsidian.py
```

评论区处理原则：

- 评论常常比原帖更有洞察，但只能作为“需求信号”
- 不把网友个人经历直接写进你的内容
- 不保存用户名作为分析对象
- 只提炼共识、分歧、底层机制和可复用问题

## 小红书洞察

小红书同样重要，但不建议做自动登录抓取或绕过反爬。当前采用“手动导入”：

```bash
python3 scripts/import_xiaohongshu.py path/to/xiaohongshu-notes.json
python3 scripts/sync_obsidian.py
```

你可以把小红书帖子正文和评论保存成 JSON、CSV、Markdown 或文本。系统会把它们转成社区洞察，进入 Obsidian 的 `60_Community_Insights`。

## Raw Capture Vault / Insight Vault

为了避免原始评论把知识图谱弄乱，系统现在拆成两个 vault：

- `raw_capture_vault`：只放原始抓取/导入结果
- `insight_vault`：只放分析结果、知识原子、问题库、认知回流

本地监控命令：

```bash
python3 scripts/monitor_capture_vault.py --interval 30 --no-ai
```

当新文件写入 raw vault 的 inbox、Huaren raw 或小红书 raw 文件夹时，monitor 会自动生成分析笔记，写入 `insight_vault/10_Analyses`。

## 电子书分析管线

电子书管线只处理三类内容：

- 公版书 / 开放授权书 / 开放获取资料
- 你自己拥有并手动导入的电子书
- 你自己整理的读书笔记

不做盗版电子书搜索或下载。

分析方法不是单纯摘要，而是三层：

- 知识原子：这章有哪些可复用认知模块？
- 苏格拉底式追问：作者的假设、证据、反例、迁移问题是什么？
- Creator 视角：这章如何连接 AI、育儿、职业女性、人生思考和个人品牌？

命令示例：

```bash
python3 scripts/search_public_ebooks.py --query "education children thinking" --limit 10
python3 scripts/analyze_ebook.py content/books/raw/book-file.txt --max-chapters 8 --no-ai
python3 scripts/sync_book_vault.py
```

### 可选：NotebookLM 适配器

`teng-lin/notebooklm-py` 可以作为实验性加速器，但它不是 Google 官方 API，而是 unofficial client。适合个人研究原型，不适合作为系统默认依赖。

使用原则：

- 只作为可选 adapter
- 不把 Google 登录 cookie 写进仓库
- 不依赖它作为唯一分析路径
- 输出结果仍然要落回本地 Obsidian vault

命令示例：

```bash
python3 scripts/notebooklm_adapter.py \
  --create-title "Creator Book Analysis" \
  --source content/books/raw/book-file.pdf \
  --prompt-file prompts/book_chapter_analysis.md
python3 scripts/sync_book_vault.py
```

## SEO / 未来网站原则

SEO 不是认证，而是让搜索引擎和 AI 更容易理解你的内容。

每篇长青文章都应该有：

- 清晰问题型标题
- 100 字内说明这篇文章解决什么问题
- H2/H3 层级结构
- 作者身份和真实经验
- 指向相关知识原子的内部链接
- Markdown frontmatter，方便以后发布到 GitHub Pages
