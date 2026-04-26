# Changelog

本项目遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/) 与 [Semantic Versioning](https://semver.org/lang/zh-CN/)。

---

## [1.7.1] — 2026-04-26

来自 4 位中文语言专家 + Codex 跨模型会审，针对用户对 3 类问题的零容忍反馈做硬阻升级。

### Added

- **scan.py 4 个新检测器**：
  - `detect_meta_discourse`：AI 助手对话腔元话语硬阻黑名单（一句话总结 / 划重点 / 敲黑板 / TL;DR / 简言之 / 要点 / 精华 / 重点是）。high severity，命中即扣分。
  - `detect_hedge_with_claim`：hedge 词 + 具体数字/年份/作者共现模式。命中输出 `hedge_with_unverified_claim` finding，强制核实出处或加 `[TODO: 待核实]` 至脚注（不进正文）。
  - `detect_omissions(raw, rewritten)`：自动 diff 三类硬事实（列表项/文件路径/数字常量）。采用「完全消失」判定（raw 中存在但 rewritten 中作为子串完全不存在），合并改写不触发误报。
  - `classify_paragraphs`：段类型自动分类（code_block / table / field_def / heading / list / summary / metadata / narrative），让段级豁免有自动依据。
- **scan.py 新增 `--compare-with` 参数**：`python scan.py rewritten.md --compare-with raw.md` 自动 omission-check。`total_omissions > 0` 时输出 ⚠️ warning 到 `report.warnings`。
- **blacklist.json 新增 2 类**：
  - `meta_discourse_markers`：元话语黑名单（high severity）
  - `hedge_with_claim_patterns`：hedge + claim 正则
- **blacklist.json `ai_writing_structural` 新增 3 项**：元话语标记（v1.7.1）/ 汉语经典连贯排比保护（一是/二是/三是 不改成 First/Second 分段）。

### Changed

- **护栏 8 升级为硬阻自动 diff**：必须显式说明每处删除（list / path / number），「没解释的删除等于错误改写」。
- **护栏 9 升级**：加 Part B「hedge + 具体出处 = 必须核实」。带具体数字/出处的 hedge 也可能是幻觉，必须三选一处理（验证真伪 / 加 TODO 至脚注 / 改为模糊但诚实表述）。**不豁免**。
- **护栏 10 升级为静态黑名单硬阻**：拆分为 Part A（元话语黑名单）/ Part B（汉语经典排比保护）/ Part C（声音指纹仍是规则描述，未量化）。
- frontmatter `metadata.version`: 1.7.0 → 1.7.1

### Verified

集成测试在 v1.6 改写稿上抓到的问题（**v1.6 同模型 reality-checker 全部漏报**）：

- 元话语硬阻命中：3 处（38KB 研究报告 改写稿 中：一句话总结/要点/重点是）
- omission 自动 diff 总计：164 处事实条目静默删除（覆盖 13 个文档）
  - 调研报告改写稿：抓到文件清单条目（含具体路径）静默删除
  - 商业评估稿改写稿：抓到 8 处时间/金额数字消失
  - 38KB 研究报告改写稿：抓到 30 处列表项消失
- 段分类成功：架构文档 18 code_block + 2 table + 28 narrative（混合体精准识别）

---

## [1.7.0] — 2026-04-26

来自 5 路跨模型会审（4 中文语言专家 + Codex GPT-5）的 4 个 P0 + 多项 P1 修复。

### Fixed (P0)

- **护栏 7 (新增): U+E000-U+F8FF (PUA) + ZWSP/BOM 元数据穿透保护**
  阻止改写过程剥离 agent 留下的引用占位符（如 ChatGPT Deep Research 类 citeturn）。来自学术编辑会审反馈：38KB 研究报告 472 处 PUA 全部被剥离的事故。
  - scan.py 新增 `detect_metadata_chars` + `detect_double_hedging`
  - 实测：raw PUA 472 → v1.6 改写稿 PUA 0（剥离）+ citeturn 102（泄漏）
- **护栏 8 (新增): omission-check 反幻觉升级为双向（既查新增也查删除）**
  禁止静默删除文件清单/列表项/差异化依据/关键限定语。来自散文编辑 + 跨模型审反馈：调研报告中文件清单条目 + 关键限定语静默删除。
- **护栏 9 (新增): hedge 词保护（attributed claim → necessary condition 越权检测）**
  「被认为...重要」不能改成「是必要条件」。来自学术编辑反馈：文献综述中软主张升硬论断事故。
  - blacklist.json 新增 `hedge_protected` 类
- **护栏 1 升级：从词级到段落位置识别**
  spec/架构文档段全段豁免 `formal_to_colloquial`，无论义务性还是描述性 cannot。来自技术编辑反馈：架构文档「不能预设/无法应对」误改。

### Fixed (P1)

- **护栏 10 (新增)**：声音守恒 + 元话语禁忌（'一句话总结：'/'划重点：' 跨声轨切换禁用）。
- **护栏 3 强化**：[TODO] 占位符不入正文（放脚注/批注）。
- **段级豁免**：从文档级判定升级到段落级。
- **blacklist.json 新增 4 类**：
  - `technical_writing_localized`：是否/负责/扫描/无法/进行/实施 等 OpenAPI/RFC 翻译惯例
  - `hedge_protected`：受保护软主张词
  - `business_colloquial_banned`：商业体裁禁用口语词（吃力/做个对比/先说一句）
  - `metadata_passthrough_chars`：PUA/隐形字符必须穿透
- **scenario-rules.md 新增场景 13**：工程估算文档默认豁免（避免「计算→算法」「应对→用于应对」类反向负优化）。

### Verified

- 38KB 研究报告原文：PUA 472 + citeturn 212 ✓ 检测器抓到
- 同文档 v1.6 改写稿：PUA 0（被剥离）+ citeturn 102（泄漏）✓ 实锤 P0 bug
- 商业评估稿 v1.6 改写：新引入 1 处 double_hedging ✓ 验证商业编辑诊断
- 其他 18 文档：detector 无误报

### Changed

- frontmatter `metadata.version`: 1.6.0 → 1.7.0
- 6 条强制护栏 → 10 条强制护栏

---

## [1.6.0] — 2026-04-26

### Fixed

- **所有可定位 span 统一去重**：v1.5 只覆盖 leveled 类，`vague_qualifiers_delete`、`filler_phrases`、`vapid_ing_analysis`、`decorative_emojis` 等 flat 类仍会与 leveled 类重复扣分。v1.6 把这些类别纳入同一个候选池，修复「在一定程度上」同时命中「一定」和「一定程度上」导致重复扣分的问题。
- **span 去重复杂度**：去重逻辑从遍历所有 kept span 改为按文本位置记录 owner，避免高密度命中文本下退化为 O(C^2)。
- **stdin 字节上限**：`--stdin` 改为 `sys.stdin.buffer.read(MAX_FILE_BYTES + 1)`，按原始字节限制 2MB，避免中文多字节输入绕过上限。
- **装饰 emoji 覆盖**：正则支持 Markdown 标题、列表项、无空格标题和 U+FE0F 变体。
- **场景与文档口径**：新增医疗文书 / 医嘱 / 病历场景；SKILL.md 补 `When to Use`、`When NOT to Use`、`Reference Index`、`Success Criteria` 和带 entry / exit criteria 的 Phase 流程。
- **致谢链接可信度**：README 移除未核验或不存在的仓库 / topic 链接，只保留已核验来源和概念性社区资料说明。

### Changed

- `scan.py`、`blacklist.json`、`style-mapping.json`、`evals.json` 的当前版本口径升级到 v1.6。
- `run_static_checks.py` 从 11 项门禁扩展到 15 项，新增 flat/leveled 重叠去重和 Markdown emoji 回归。
- `selftest.py` 从 11 条编号回归断言扩展到 14 条，新增「在一定程度上」、装饰 emoji 和 `stats([0,0,0])` 边界断言。
- `allowed-tools` 收窄为 `Read` 和 `Bash`；默认通过对话交付改写结果，不把写文件作为必经动作。
- 新增 `pyproject.toml` 记录项目元数据和 Python 版本要求；项目仍保持零第三方依赖。
- 输出字段 `clamped_to_zero` 改名为 `raw_deductions_exceed_score`，避免把「扣分超过 100」误读成一定发生了截断到 0。

---

## [1.5.0] — 2026-04-26

### Fixed（关键 bug 修复，本版的核心目标）

- **scan.py 同类内子串重叠扣分**（外部审查 Codex 实证报 P1 阻断级）
  - v1.4 之前 `span_owner` 仅按 `(word, pos)` 去重，无法处理「击穿心智」+「心智」、「不断演变的格局」+「格局」这类同词族子串重叠
  - v1.5 改为 leveled 类 span 级去重：候选命中按 `(severity, 长度, 类别顺序, start)` 排序，一次性遍历保留最优 span，被重叠覆盖的进入 `_cross_category_matches.suppressed` 字段。v1.6 才扩展到所有可定位 flat 类
  - 实证：「击穿心智」一处 v1.4 扣 8 → v1.5 扣 4；「不断演变的格局」一处 v1.4 扣 6 → v1.5 扣 4
- **style-mapping.json 否定排比示例的幻觉残留**（外部审查 GLM P1-1 / Kimi O4 共识）
  - v1.4 在 SKILL.md 改写示例 3 删除了「批处理 / 键盘快捷键 / 离线模式」编造，但 style-mapping.json 同名示例未同步
  - v1.5 同步：`negation_parallel_density.rewrite_examples_when_dense[0].after` 改为 `这次软件更新 [TODO: 补具体更新内容]`
- **stdin / --text 缺少大小限制**（外部审查 GLM P0-2 / Kimi S5 / Claude S1 共识）
  - v1.4 仅 file 模式有 `MAX_FILE_BYTES = 2_000_000` 上限；stdin 与 --text 走 `sys.stdin.read()` 无界
  - v1.5 在 stdin / --text 路径上对齐限制，超限即 `ap.error` 退出
- **run_static_checks.py 不能作 CI 门禁**（外部审查 Codex P1 / Claude L4 / Kimi M6 共识）
  - v1.4 仅 print PASS/FAIL，eval 6 写「看上面 deductions」要人工判断，整脚本退出码恒为 0
  - v1.5 改为完全自动化：eval 6 用 `assert_zsss_dedupe` 检查「综上所述」字面只出现在 1 个类别 hits 中；总计 11 项 check 任一 fail → `sys.exit(1)`
- **`不是.{1,15}是` 正则误报**（外部审查 Claude H2）
  - v1.4 该 pattern 命中「他不是张三是李四」「我不是说他坏是说他懒」等普通陈述句
  - v1.5 删除该 pattern；其他 8 条 negation_parallel pattern 已足够覆盖典型 AI 排比
- **装饰 emoji 字符类对带 U+FE0F 变体选择符的 emoji 漏检**（外部审查 Claude H3）
  - v1.4 字符类 `[🚀💡✅🔥📊💯⭐️✨🎯📈🛠️]\s` 把 `⭐️ = ⭐ + U+FE0F` 解析为两个独立码点导致漏匹配
  - v1.5 改为 alternation：`(?:🚀|💡|✅|🔥|📊|💯|⭐️?|✨|🎯|📈|🛠️?)\s`
- **scan.py:141 stats() 死代码**（四方共识）
  - 删除 `var = ... if n > 0 else 0` 三元表达式（函数入口已 early return 保证 n>=1）
- **coverage.md / SKILL.md / README.md 数学不自洽**（外部审查 Claude H4）
  - v1.4 三处文档使用「7 完整 + 6 部分 + 9 未覆盖 + 1 不适用 = 23」少 1 项
  - v1.5 统一为 humanizer-zh 原 24 项口径：「8 完整 + 6 部分 + 9 未覆盖 + 1 不适用 = 24」；coverage.md 单独说明合并实现项数为 7

### Added

- **「复用 / 落地 / 沉淀」三个 high 词条加 context_safe_when 豁免**（外部审查 Claude H1）
  - 「复用」豁免软件工程 / 硬件工程
  - 「落地」豁免产品 / 项目管理
  - 「沉淀」豁免数据工程 / 运营术语
- selftest 新增 v1.5 断言 10、11：覆盖同类内子串去重和跨类别+子串组合
- run_static_checks 新增 2 个 case（v1.5-substr / v1.5-mixed）覆盖 v1.5 子串去重逻辑
- `.gitignore` — 排除 __pycache__ / .DS_Store / IDE 临时文件
- `CHANGELOG.md` — 本文件，记录 v1.0 → v1.5 完整变更链

### Removed

- `scripts/__pycache__/` 不再纳入版本控制（GLM+Kimi 共识）
- `scripts/check_v12.py`（v1.2 时期临时验证脚本）

### Changed

- frontmatter `metadata.version`: 1.4.0 → 1.5.0
- scan.py docstring: v1.4 → v1.5
- selftest.py docstring: v1.4 → v1.5
- blacklist.json `$schema`: v1.3 → v1.5
- style-mapping.json `$schema`: v1.2 → v1.5
- evals.json `version_under_test`: v1.3 → v1.5
- README 致谢段大幅扩充，列出 8 个开源项目来源 + Wikipedia 维基项目 + Anthropic skill-creator 评估框架

---

## [1.4.0] — 2026-04-26

### Fixed（修 v1.3 grading-v1.3.json 列出的 6 项必修）

- SKILL.md 改写示例 2 「问卷方法」幻觉 → 改回「定量分析方法」+ TODO 提示
- SKILL.md 改写示例 3 「批处理/键盘快捷键」编造 → 改为 `[TODO: 补具体更新内容]`
- scan.py 跨类别重复扣分 → 新增 `span_owner` + `_cross_category_matches`；「综上所述」一处由 v1.3 -8 改为 v1.4 -4（注：v1.4 仅处理跨类别，v1.5 才处理同类内子串重叠）
- SKILL.md description 仅检测模式 → 加「让模型按 `context_safe_when` 标注疑似误报」步骤
- blacklist.json curly_quotes_english 加 `report_only: true`；scan.py 检测到 report_only 时仅记录不扣分
- frontmatter version 升至 1.4.0；scan.py 与 selftest docstring 同步

### Added

- evals/grading-v1.4.json — 量化评估存档

---

## [1.3.0] — 2026-04-26

### Fixed（修 v1.2 蜂群审查列出的若干 backlog）

- coverage.md 三处统计数字对齐
- SKILL.md 护栏 3 加「TODO 仅用于关键事实位」边界
- SKILL.md 护栏 6 改硬约束「自审最多两轮」
- SKILL.md 维度 D 加技术体裁豁免（commit / changelog / PR description / 工作周报 / API doc / 代码注释）
- 删除 D5「评审编号串接」从 SKILL.md 维度 D 主条，挪到 README 附录
- scenario-rules.md 新增场景 11「技术工件 / changelog / 工作周报 / commit message」豁免维度 D
- scan.py `_dedupe_overlapping` 改为扫描所有已 kept 项检查重叠（修三方重叠拓扑漏判）
- scan.py `load_blacklist` 加 OSError + UnicodeDecodeError 单独捕获
- scan.py 新增 `DEFAULT_WEIGHTS` + `get_weights()` 支持 blacklist.json 外置权重
- scan.py `vague_qualifiers_soften` 改为按文本长度归一化扣分（每 200 字允许 1 次）

### Added

- blacklist.json `_scoring_weights_doc` + `_scoring_weights_example` 演示权重外置
- evals/ 目录引入 skill-creator 标准评估框架（evals.json + grading-v1.3.json + run_static_checks.py + README）

---

## [1.2.0] — 2026-04-25

### Added（v1.0 → v1.2 主线扩展）

- 6 条强制护栏（受规约文本 / 专业语境豁免 / 占位符 / 反向特征确认 / 评分非目标 / 模型自审）
- 维度 D「结构性 AI 写作惯例」（编号回引 / 英文术语裸用 / 表格化压缩 / 工时估算模板 / 无主语并列）
- 词库扩充：互联网黑话补 12 词（层面 / 语境 / 深耕 / 打通 / 赋活 / 解构 / 共情 / 范式 / 心智 / 势能 / 锚定 / 高质量发展）
- ai_translation_artifact 独立类别（织锦 / 格局 / 不可磨灭 / 深深植根于）
- 30+ 词条加 context_safe_when 专业语境豁免字段
- 否定排比同段密度判断（≥2 处才视为模板）
- 7 场景扩到 10 场景（新增商业 PR / 教育课件 / 法律文书）
- coverage.md 诚实记录 humanizer-zh 24 模式覆盖状态

### Fixed

- 修 v1.0 875 行原版的 frontmatter name 不匹配目录、词库重复、severity 体系不统一、被动句章节自相矛盾、改写示例编造数字等问题

---

## [1.1.0] — 2026-04-25

- 拆分单文件 SKILL.md 为 references/ + scripts/ 模块化结构
- 引入 blacklist.json 词库 + scan.py 静态扫描器
- 7 场景适配规则
- 反幻觉红线（占位符不许填值）

---

## [1.0.0] — 2026-04-25

- 初始版本：单文件 875 行 SKILL.md（基于 Hermes 团队的 de-ai-humanizer 草稿）
- 中文场景特化：互联网黑话 / 学术八股 / 过度正式连接词

---

[1.7.1]: ./CHANGELOG.md#171---2026-04-26
[1.7.0]: ./CHANGELOG.md#170---2026-04-26
[1.6.0]: ./CHANGELOG.md#160---2026-04-26
[1.5.0]: ./CHANGELOG.md#150---2026-04-26
[1.4.0]: ./CHANGELOG.md#140---2026-04-26
[1.3.0]: ./CHANGELOG.md#130---2026-04-26
[1.2.0]: ./CHANGELOG.md#120---2026-04-25
[1.1.0]: ./CHANGELOG.md#110---2026-04-25
[1.0.0]: ./CHANGELOG.md#100---2026-04-25
