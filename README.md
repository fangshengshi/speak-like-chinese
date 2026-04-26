# speak-like-chinese

> 让中文写作"听起来像人话"

一个用于检测和去除中文 AI 写作痕迹的 [Claude Code Skill](https://docs.claude.com/en/docs/claude-code/skills)。

中文 AI 生成文本有它独特的"AI 味"——除了通用 AI 模式（破折号过度、三段式、否定排比），还有中文场景特有的互联网黑话（赋能/抓手/闭环）、学术八股（具有重要意义/综上所述）、过度正式连接词、英文学术语硬翻成中文的痕迹（织锦/格局/不可磨灭/深深植根于）。

speak-like-chinese 在 [humanizer-zh](https://github.com/blader/humanizer)（来自 Wikipedia AI Cleanup）的基础上，加入了**中文场景特化检测词库**、**11 个文本场景 + 1 个技术工件豁免场景的差异化适配**、**专业语境豁免**、**结构性 AI 写作惯例**（编号回引、英文术语裸用、changelog 风格混入正文）、以及**反幻觉护栏**（占位符不许填值、不编造原文未提供的细节）。

humanizer-zh 24 个模式中，speak-like-chinese 完整覆盖 8 项、部分覆盖 6 项、未覆盖 9 项、不适用中文 1 项（合计 24 项，约 58% 覆盖）——详见 [references/coverage.md](references/coverage.md)。

---

## 它做什么

- **检测**：扫描中文文本，命中 AI 模式按 high/mid/low 分级输出
- **改写引导**：给 LLM 提供按 severity 排序的改写规则、12 场景化策略、专业语境豁免清单
- **评分**：0-100 静态评分（含句长 burstiness、段落均匀度、否定排比密度）
- **不做幻觉**：明确禁止改写时编造数字、来源、人名、个人经历——这是 AI 改写最常见也最严重的错误，本 skill 把它当成第一红线
- **结构性自审**：让 LLM 改完后自查自己输出有没有"用 AI 风格说人话"

## 它不做什么

- ❌ 不替你做最终决定——LLM 在 skill 引导下改写，最终需要人审
- ❌ 不自动重写——评分和指引是核心，重写交给 Claude
- ❌ 不依赖任何第三方库——纯 Python stdlib
- ❌ 不消费 style-mapping.json（那个文件供 LLM 改写参考；scan.py 只读 blacklist.json）
- ❌ 不处理结构性 AI 痕迹的静态扫描（regex 抓不准会大量误判，由 LLM 凭语义自判）

---

## 使用

### 作为 Claude Code Skill

把整个目录复制到 `~/.claude/skills/speak-like-chinese/`：

```bash
git clone https://github.com/<your-org>/speak-like-chinese ~/.claude/skills/speak-like-chinese
```

之后向 Claude Code 提供中文文稿，说「帮我去掉 AI 味」或「按小红书风格润色」即可。

如果只想检测不想改写，问「这段是 AI 写的吗」就行——skill 会进入仅检测模式，只跑 scan.py 给报告。

### 作为命令行工具

```bash
# 扫描文件
python scripts/scan.py path/to/article.md --pretty

# 从标准输入
cat draft.md | python scripts/scan.py --stdin --pretty

# 直接传文本
python scripts/scan.py --text "在当今社会，人工智能..."
```

输出 JSON 报告，含 `score`、`grade`、`raw_deductions_total`、`raw_deductions_exceed_score`、`deductions`、`findings`、`sentence_stats`、`paragraph_stats`、`warning` 字段。详细字段说明见 scan.py 顶部 docstring。

输入大小上限为 2MB。文件模式按文件字节数限制，`--stdin` 按读取到的原始字节数限制，`--text` 按 UTF-8 编码后的字节数限制；超限时会退出并提示分段扫描。

---

## 与同类项目对比

| 项目 | 来源 | 中文场景 | 词库分级 | 专业语境豁免 | 否定排比密度判断 | 反幻觉护栏 | 结构性 AI 痕迹 | 场景适配 |
|---|---|---|---|---|---|---|---|---|
| [humanizer-zh](https://github.com/blader/humanizer) | Wikipedia AI Cleanup | 通用 | ❌ | ❌ | ❌ | ⚠️（部分） | ❌ | ❌ |
| **speak-like-chinese** | 多源整合 | ✅ 中文特化 | ✅ high/mid/low | ✅ context_safe_when | ✅ 同段密度 | ✅ 占位符红线 | ✅ 6 类（编号回引等） | ✅ 12 场景 |

speak-like-chinese 在 humanizer-zh 适用于中文的核心模式上做超集扩展，但**不是 humanizer-zh 的 24 模式全集**——见 [coverage.md](references/coverage.md) 看具体哪些覆盖、哪些未覆盖。如果你的需求侧重在 humanizer-zh 已覆盖但本项目未覆盖的模式（如「夸大象征意义」「媒体报道堆砌」），建议两个 skill 并存使用。

---

## 目录结构

```
speak-like-chinese/
├── SKILL.md                       # Claude Skill 主文件
├── README.md                      # 本文件
├── LICENSE                        # MIT
├── CHANGELOG.md                   # 版本变更记录（v1.0 → v1.6）
├── .gitignore
├── pyproject.toml                 # Python 项目元数据（无第三方依赖）
├── references/
│   ├── blacklist.json             # 词库（按 high/mid/low 分级 + context_safe_when 专业语境豁免）
│   ├── style-mapping.json         # 替换表（供 LLM 改写参考；scan.py 不消费）
│   ├── scenario-rules.md          # 12 场景适配规则（11 文本场景 + 1 技术工件豁免场景）
│   └── coverage.md                # humanizer-zh 24 模式覆盖状态
├── scripts/
│   ├── scan.py                    # 静态扫描器（纯 stdlib）
│   └── selftest.py                # 14 条回归断言
└── evals/                         # skill-creator 标准评估框架
    ├── evals.json                 # 12 test cases / 44 expectations
    ├── grading-v1.3.json          # v1.3 评估存档
    ├── grading-v1.4.json          # v1.4 评估存档
    ├── grading-v1.5.json          # v1.5 评估存档
    ├── grading-v1.6.json          # v1.6 评估（当前）
    ├── run_static_checks.py       # 15 条 CI 门禁断言（失败 sys.exit 1）
    └── README.md
```

---

## 设计原则

1. **保真优先**——宁可保留模糊表述，绝不编造细节。「模糊但诚实」永远胜过「具体但伪造」
2. **场景驱动**——同一文本在不同场景下规则差异巨大；公文不能口语化，法律不能软化绝对值
3. **专业豁免**——「闭环」在控制论是术语，「对齐」在 AI 安全是术语，命中前先看 `context_safe_when`
4. **可解释评分**——每次扣分都有明确理由；评分仅参考，不是优化目标
5. **零依赖**——scan.py 只用 Python stdlib
6. **数据与逻辑分离**——词库走 JSON，逻辑走代码，便于贡献和迭代
7. **模型自审**——使用本 skill 的模型自己输出也要自审，不能"用 AI 风格说人话"

---

## 贡献

欢迎补充词库。新增黑话或八股词时，请提供：

1. 词条本身
2. 至少 3 个真实 AI 文本中出现的例子
3. 建议的 severity（high / mid / low）
4. 建议的替换表达
5. **若该词在某些专业语境下是术语，提供 `context_safe_when` 字段**——这点比新增词条本身更重要，缺了会让 LLM 误删合法术语

修改 `references/blacklist.json` 或 `references/style-mapping.json` 后，跑 `python scripts/selftest.py` 确认 scan 仍正常工作；跑 `python -m json.tool < references/blacklist.json` 确认 JSON 仍合法。

正则表达式约束：所有 `patterns` 必须用有界量化（`{1,15}` 而非 `+`），避免 ReDoS 灾难性回溯。

---

## 附录 · 协作场景的额外建议（不在 SKILL.md 主流程中）

如果你在团队协作中频繁做多人评审、决策汇总、PR review 等场景，speak-like-chinese 维度 D 主条不覆盖一类痕迹叫**评审编号串接**：

> ❌ reality F1 + deep §3 + logic B1+B2+I5+I6

> ✅ 对抗审查报告里的第一个致命漏洞、研究员报告第三章第三条、代码审查里的两个必修 bug 加两个改进项。

**规则**：多人评审编号回引时复述出处和内容性质，不要只串编号。这条**没放进 SKILL.md 维度 D 主条**，因为它属于团队内部协作场景，不是 AI 写作的普遍痕迹。如果你的工作流确实涉及这类输出，可以参考此条手动检查。

---

## License

MIT — 见 [LICENSE](LICENSE)。

---

## 致谢

speak-like-chinese 的设计与词库基于多个公开开源项目和资料的综合整理。向以下来源致敬：

### 检测模式与改写规范

- [Wikipedia:Signs of AI writing](https://en.wikipedia.org/wiki/Wikipedia:Signs_of_AI_writing) — WikiProject AI Cleanup（Wikipedia 社区维护，CC BY-SA 4.0）。本项目维度 B 「通用 AI 痕迹」 + coverage.md 24 项原始模式表的核心来源
- [blader/humanizer](https://github.com/blader/humanizer) — Andrew Bladon 的 humanizer skill。本项目继承其核心检测理念，并在中文场景做超集扩展
- [hardikpandya/stop-slop](https://github.com/hardikpandya/stop-slop) — 反 AI 写作风格的英文规则参考
- 中文 AI 写作特征社区资料与人工整理词表 — 本项目只列已核验来源链接；无法确认到具体仓库的资料不写成项目引用

### 评估框架

- [Anthropic skill-creator](https://github.com/anthropics/skills/tree/main/skills/skill-creator) — Anthropic 官方 skill 创建与评估框架。本项目 `evals/evals.json` 与 `grading-*.json` 严格遵循其 `references/schemas.md` 定义的 schema

### 词库整理

- 中文互联网黑话词库 — 综合自多份社区贡献的整理（赋能/抓手/闭环/颗粒度等）
- 学术八股词库 — 综合自中文论文写作规范文献与公开评论
- 国家政策文本对照样本 — 用于场景 7「公文 / 政府报告」与场景 8「法律文书」的禁忌规则推导

### 设计与方法论

- Andrej Karpathy 关于 LLM 写作风格的公开讨论 — 启发本项目对「中庸表达」的反向操作设计
- nashsu/llm_wiki 项目（基于 Karpathy llm-wiki.md 模式）— 启发知识库与 skill 评审框架的关系思考

如有遗漏未列出的来源、或词库条目可追溯到具体项目，欢迎 issue / PR 补充致谢清单。本项目所有原创内容（场景规则、护栏体系、scan.py 实现、coverage.md 表格）均以 MIT 协议开放。
