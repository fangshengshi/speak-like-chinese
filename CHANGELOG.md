# Changelog

本项目遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/) 与 [Semantic Versioning](https://semver.org/lang/zh-CN/)。

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

[1.6.0]: ./CHANGELOG.md#160---2026-04-26
[1.5.0]: ./CHANGELOG.md#150---2026-04-26
[1.4.0]: ./CHANGELOG.md#140---2026-04-26
[1.3.0]: ./CHANGELOG.md#130---2026-04-26
[1.2.0]: ./CHANGELOG.md#120---2026-04-25
[1.1.0]: ./CHANGELOG.md#110---2026-04-25
[1.0.0]: ./CHANGELOG.md#100---2026-04-25
