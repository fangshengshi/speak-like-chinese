# speak-like-chinese · evals

本目录用 [Anthropic skill-creator](https://github.com/anthropics/skills/tree/main/skills/skill-creator) 框架对 speak-like-chinese 做量化评估。

## 文件

- **evals.json** — 12 个 test prompts + 41 条可验证 expectations，覆盖外部第四方评审的 9 项问题 + 之前蜂群审查涌现的 3 项关键风险
- **grading-v1.3.json / grading-v1.4.json / grading-v1.5.json** — 历史评估存档；v1.5 已被 v1.6 后续审计更正，不作为当前发布依据
- **grading-v1.6.json** — 当前 v1.6 验收记录
- **run_static_checks.py** — 跑 scan.py 对几个 eval 做机器可验证的静态测试（当前 15 项 check）

## 当前状态（v1.6）

- v1.3 pass_rate: 80.5%（33/41）
- v1.4 pass_rate: 估约 95%+（v1.3 残留 6 项必修全部修复，selftest 9 条断言全过）
- v1.5 pass_rate: 估约 99%，但后续审计发现 flat 类未进入全局去重、文档口径和致谢链接仍有发布阻塞
- v1.6 static checks: `selftest.py` 14 条编号回归断言全过，`run_static_checks.py` 15 项 CI 门禁全过
- approved_for_release: **true**（以 v1.6 当前状态为准）

## v1.6 修复的 v1.5 残留问题

1. ✅ `scan.py` 全部可定位 span 统一去重，修复「在一定程度上」重复扣分
2. ✅ 去重复杂度从 kept 两两扫描改为位置 owner 表，避免高密度输入退化
3. ✅ `--stdin` 改为按原始字节限制 2MB
4. ✅ 装饰 emoji 覆盖 Markdown 标题、列表项和无空格标题
5. ✅ `SKILL.md` 补触发边界、负向场景、验收标准和 entry / exit criteria
6. ✅ README 致谢段移除未核验链接，eval 12 改为真实全角弯引号 prompt

## 怎么跑

### 静态部分（机器可验证）

```bash
python evals/run_static_checks.py
```

输出会显示：scan.py 对几个 prompt 的实际反应、否定排比密度规则、全局 span 去重和装饰 emoji 覆盖情况。

### 完整部分（需要 skill-creator 装机 + Claude API）

如果你装了 skill-creator：

```bash
git clone https://github.com/anthropics/skills ~/skills-anthropic
~/skills-anthropic/skills/skill-creator/scripts/run_eval.py \
  --skill /path/to/speak-like-chinese \
  --evals /path/to/speak-like-chinese/evals/evals.json
```

## 怎么用 grading 结果迭代

按 skill-creator 的 Improve mode：
1. 读 grading-v1.3.json 看 fail 的 expectation
2. 修对应 SKILL.md / blacklist.json / scan.py
3. 重跑 evals 出新的 grading 文件
4. 对照历史 grading 看 pass_rate 变化（这是 history.json 的功能）

## 与已有蜂群审查的关系

- 蜂群审查（lf-deep-researcher / lf-reality-checker / lf-logic-reviewer）= 定性评审
- skill-creator evals = 定量 + 可验证

两者互补：蜂群发现 v1.0 → v1.1 → v1.2 → v1.3 的设计漏洞，evals 把审查结论转成可机器/人工验证的 test cases，未来每次改动都可以回归运行。
