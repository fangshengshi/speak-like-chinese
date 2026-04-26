"""run_static_checks v1.6 · 跑 scan.py 验证 evals 里可机器判定的 expectations。

CI 门禁：所有 lambda check 失败时 sys.exit(1)；eval 6 改为可机器断言。
"""
import io
import json
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "scripts"))
from scan import scan, load_blacklist  # noqa


def assert_zsss_dedupe(r):
    """eval 6: 「综上所述」一处只应在 1 个类别的 hits 里出现（v1.5 全局 dedup 保证）。"""
    target = "综上所述"
    cats_containing = []
    for cat in ("jargon_academic", "formal_connectors", "closer_banned"):
        bucket = r["findings"].get(cat, {})
        for sev in ("high", "mid", "low"):
            sb = bucket.get(sev, {})
            for h in sb.get("hits", []):
                if h.get("word") == target:
                    cats_containing.append(f"{cat}.{sev}")
    return len(cats_containing) == 1


def assert_xcm_present(r):
    """eval 6 副断言：findings 应含 _cross_category_matches，证明跨类别去重逻辑触发。"""
    xcm = r["findings"].get("_cross_category_matches")
    return xcm is not None and xcm.get("count", 0) >= 1


def assert_zsss_deduction_cap(r):
    """eval 6 副断言：含「研究表明」时，总扣分不因「综上所述」重复而超过 6。"""
    return sum(
        d["points"] for d in r["deductions"]
        if any(c in d.get("reason", "") for c in (
            "formal_connectors", "jargon_academic", "closer_banned"
        ))
    ) <= 6


cases = [
    {
        "id": "6",
        "name": "eval 6 跨类别重复扣分（v1.5 同时验证子串去重）",
        "text": "研究表明，AI 对生产力影响很大。综上所述，必须重视。",
        "checks": [
            ("'综上所述'只出现在 1 个相关类别 hits 中", assert_zsss_dedupe),
            ("findings 含 _cross_category_matches 字段", assert_xcm_present),
            ("相关三类合计扣分 ≤ 6（研究表明 2 分 + 综上所述 high 一次 4 分）", assert_zsss_deduction_cap),
        ],
    },
    {
        "id": "9",
        "name": "eval 9 单段单处否定排比",
        "text": "真正打动我的，不是那场雨，而是雨后她回头看我的那一眼。",
        "checks": [
            ("negation_parallel.high_density_hits == 0",
             lambda r: r["findings"].get("negation_parallel", {}).get("high_density_hits", 0) == 0),
            ("negation_parallel.low_density_hits >= 1",
             lambda r: r["findings"].get("negation_parallel", {}).get("low_density_hits", 0) >= 1),
            ("整体 score >= 90",
             lambda r: r["score"] >= 90),
        ],
    },
    {
        "id": "12",
        "name": "eval 12 中文弯引号弱信号（v1.5 起 report_only 不扣分）",
        # v1.5 起测试文本与 prompt 一致：含全角弯引号，验证 report_only 行为
        "text": "他说 “项目进展顺利”，但其他人不同意。",
        "checks": [
            ("findings 含 curly_quotes 且 report_only=True",
             lambda r: r["findings"].get("curly_quotes", {}).get("report_only") is True),
            ("弯引号扣分 == 0",
             lambda r: not [d for d in r["deductions"]
                            if "弯引号" in d.get("reason", "") and d.get("points", 0) > 0]),
        ],
    },
    {
        "id": "v1.5-substr",
        "name": "v1.5 新增：同类内子串重叠去重（『击穿心智』+『心智』）",
        "text": "他们想击穿心智。",
        "checks": [
            ("jargon_internet.high.count == 1",
             lambda r: r["findings"].get("jargon_internet", {}).get("high", {}).get("count", 0) == 1),
            ("jargon_internet 总扣分 ≤ 4（不重复扣『心智』）",
             lambda r: sum(d["points"] for d in r["deductions"]
                           if "jargon_internet" in d.get("reason", "")) <= 4),
        ],
    },
    {
        "id": "v1.5-mixed",
        "name": "v1.5 新增：跨类别+子串组合（『不断演变的格局』+ 子串『格局』）",
        "text": "这反映了不断演变的格局。",
        "checks": [
            ("ai_translation_artifact.high.count == 1",
             lambda r: r["findings"].get("ai_translation_artifact", {}).get("high", {}).get("count", 0) == 1),
            ("ai_translation_artifact.mid.count == 0（子串『格局』被压制）",
             lambda r: r["findings"].get("ai_translation_artifact", {}).get("mid", {}).get("count", 0) == 0),
        ],
    },
    {
        "id": "v1.6-flat-overlap",
        "name": "v1.6 新增：leveled 类与 flat 类统一去重（『在一定程度上』+『一定』）",
        "text": "这事在一定程度上影响了他。",
        "checks": [
            ("absolute/vague/jargon 相关扣分只发生 1 次",
             lambda r: len([
                 d for d in r["deductions"]
                 if any(key in d.get("reason", "") for key in (
                     "absolute_words", "vague_qualifiers_delete", "jargon_academic"
                 ))
                 and d.get("points", 0) > 0
             ]) == 1),
            ("findings 含 _cross_category_matches 字段",
             assert_xcm_present),
        ],
    },
    {
        "id": "v1.6-decorative-emoji",
        "name": "v1.6 新增：装饰 emoji 覆盖 Markdown 标题、列表和无空格标题",
        "text": "# 🚀 标题\n- ✅ 条目\n🛠️修复说明",
        "checks": [
            ("decorative_emojis.count >= 3",
             lambda r: r["findings"].get("decorative_emojis", {}).get("count", 0) >= 3),
        ],
    },
]


def main() -> int:
    print("=" * 60)
    print("speak-like-chinese v1.6 · 静态 eval 验证")
    print("=" * 60)

    bl = load_blacklist()
    failed_count = 0
    total_checks = 0

    for case in cases:
        print(f"\n--- eval {case['id']}: {case['name']} ---")
        print(f"Text: {case['text']}")
        r = scan(case["text"], bl)
        print(f"Score: {r['score']} ({r['grade']})")
        if r["deductions"]:
            for d in r["deductions"]:
                note = f" [{d.get('note','')}]" if d.get("note") else ""
                print(f"  Deduction: {d['reason']}: -{d['points']}{note}")
        if r["findings"]:
            print(f"Findings categories: {sorted(r['findings'].keys())}")

        for check in case["checks"]:
            total_checks += 1
            ok = check[1](r)
            if not ok:
                failed_count += 1
            print(f"  [{'PASS' if ok else 'FAIL'}] {check[0]}")

    print("\n" + "=" * 60)
    print(f"总计 {total_checks} 项 check：通过 {total_checks - failed_count}，失败 {failed_count}")
    if failed_count:
        print("FAILED — 至少一项 check 未通过；CI 应当退出非零")
        return 1
    print("ALL PASS ✓")
    return 0


if __name__ == "__main__":
    sys.exit(main())
