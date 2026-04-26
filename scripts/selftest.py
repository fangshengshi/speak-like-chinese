"""自检 v1.6：JSON 合法、selftest 跑通、v1.3-v1.6 新规则均有效。"""
import io
import json
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

print("=== JSON 合法性 ===")
for fname in ("blacklist.json", "style-mapping.json"):
    p = HERE.parent / "references" / fname
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
        print(f"  {fname}: OK, top keys = {list(d.keys())[:5]}...")
    except Exception as e:
        print(f"  {fname}: FAIL - {e}")
        sys.exit(1)

print()
print("=== blacklist 关键字段抽检 ===")
bl = json.loads((HERE.parent / "references" / "blacklist.json").read_text(encoding="utf-8"))

assert "深耕" in bl["jargon_internet"]["high"], "深耕 应在 jargon_internet.high"
assert "层面" in bl["jargon_internet"]["mid"], "层面 应在 jargon_internet.mid"
assert "差异化" in bl["jargon_internet"]["mid"], "差异化 应在 jargon_internet.mid（升级）"
assert "总之" in bl["closer_banned"]["high"], "总之 应在 closer_banned.high（升级）"
assert "ai_translation_artifact" in bl, "应有 ai_translation_artifact 类别"
assert "织锦" in bl["ai_translation_artifact"]["high"], "织锦 应在 ai_translation_artifact.high"
assert "格局" in bl["ai_translation_artifact"]["mid"], "格局 应在 ai_translation_artifact.mid"
assert "生态化" in bl["jargon_internet"]["high"], "生态化 应在 jargon_internet.high"
assert "生态化反" not in bl["jargon_internet"]["high"], "生态化反 是错字，不应保留"
assert "context_safe_when" in bl["jargon_internet"], "jargon_internet 应有 context_safe_when"
assert "对齐" in bl["jargon_internet"]["context_safe_when"], "对齐 应有豁免"
assert "ai_writing_structural" in bl, "应有 ai_writing_structural 类别（结构性 AI 痕迹）"
assert "不是.{1,15}而是" in bl["negation_parallel"]["patterns"], "应包含 不是X而是Y 模式"
assert "density_rule" in bl["negation_parallel"], "negation_parallel 应有 density_rule"
print("  blacklist 关键字段全部就绪")

print()
print("=== scan.py 自测 ===")
from scan import scan, load_blacklist  # noqa

bl = load_blacklist()

# AI 味样本 1：黑话 + 八股 + 开场白 + 结尾
ai_text = (
    "在当今社会，人工智能技术的快速发展正在深刻改变我们的生活方式。"
    "通过构建智能化的技术生态，我们能够实现对传统行业的深度赋能，"
    "从而形成新的价值闭环。这一趋势在多个垂直领域都有广泛应用，"
    "具有重要的实践意义。综上所述，AI 必然会深刻影响每一个行业。"
)

# 人写改写版
human_text = (
    "AI 这几年发展得很快，正在改变生活方式。"
    "它把传统行业用新技术重做了一遍，效率上去了，玩法也变了——在好几个行业都能看到。"
    "至于会怎么影响每个行业，没人说得准。"
)

# 否定排比·单段单处合法递进（不应高密度扣分）
single_neg = "真正打动我的，不是那场雨，而是雨后她回头看我的那一眼。"

# 否定排比·同段≥2处（应高密度扣分）
dense_neg = (
    "这不仅仅是一次软件更新，而是我们思考生产力方式的革命。"
    "它不只是工具，更是生产力伙伴。"
)

# 英文翻译腔
trans_artifact = "这部作品是一幅织锦，深深植根于演变史上的关键时刻，反映了更广泛的格局。"

samples = [
    ("AI 味样本（黑话+八股）", ai_text),
    ("人写改写版", human_text),
    ("否定排比·单处合法递进", single_neg),
    ("否定排比·同段高密度", dense_neg),
    ("英文翻译腔", trans_artifact),
]

for label, text in samples:
    r = scan(text, bl)
    print(f"\n[{label}]")
    print(f"  score: {r['score']} ({r['grade']})")
    print(f"  raw_total: {r['raw_deductions_total']}, exceed_score={r['raw_deductions_exceed_score']}")
    if r["deductions"]:
        for d in r["deductions"][:6]:
            note = f" [{d.get('note','')}]" if "note" in d else ""
            print(f"    - {d['reason']}: -{d['points']}{note}")
    print(f"  hit categories: {sorted(r['findings'].keys())}")

print()
print("=== 关键回归断言 ===")

# 断言 1：单处否定排比不应触发高密度扣分
r_single = scan(single_neg, bl)
neg_finding = r_single["findings"].get("negation_parallel", {})
assert neg_finding.get("high_density_hits", 0) == 0, "单处递进不应被算作高密度"
assert neg_finding.get("low_density_hits", 0) >= 1, "单处递进应被识别为低密度（合法递进）"
high_density_deducts = [d for d in r_single["deductions"] if "高密度" in d["reason"]]
assert not high_density_deducts, f"单处递进不应触发高密度扣分，但有：{high_density_deducts}"
print("  ✓ 单段单处否定排比保留为合法递进，不扣分")

# 断言 2：同段≥2处否定排比应触发高密度扣分
r_dense = scan(dense_neg, bl)
neg_finding = r_dense["findings"].get("negation_parallel", {})
assert neg_finding.get("high_density_hits", 0) >= 2, "同段≥2处应被识别为高密度"
high_density_deducts = [d for d in r_dense["deductions"] if "高密度" in d["reason"]]
assert high_density_deducts, "同段高密度否定排比应触发扣分"
print(f"  ✓ 同段高密度否定排比触发扣分: {high_density_deducts[0]['reason']}")

# 断言 3：英文翻译腔类别命中
r_trans = scan(trans_artifact, bl)
assert "ai_translation_artifact" in r_trans["findings"], "应识别英文翻译腔"
print(f"  ✓ 英文翻译腔类别正确触发: {r_trans['findings']['ai_translation_artifact']}")

# 断言 4：清白文本满分
r_human = scan(human_text, bl)
assert r_human["score"] >= 90, f"人写文本应高分，实得 {r_human['score']}"
print(f"  ✓ 人写文本得分 {r_human['score']}")

# 断言 5：warning 字段存在
assert "warning" in r_human, "返回应含 warning 字段"
print(f"  ✓ warning 字段已注入")

# 断言 6（v1.3）：模糊词密度归一化——长文里少量"可能"不应扣分
# 600 字以上文本 allowance = max(1, 600//200) = 3，命中 2 处低于 allowance，应被识别为"未超标"
long_low_density_vague = "今天阳光很好。" * 60 + "可能会下雨。" + "明天似乎也好。"  # 约 540+ 字，2 处模糊
r_long = scan(long_low_density_vague, bl)
soft_deducts = [d for d in r_long["deductions"] if "vague_qualifiers_soften" in d["reason"] and d["points"] > 0]
assert not soft_deducts, f"长文低密度模糊词不应扣分（密度归一化），实际：{soft_deducts}"
# 应该有"未超标"的 0 分记录
zero_records = [d for d in r_long["deductions"] if "vague_qualifiers_soften" in d["reason"] and d["points"] == 0]
assert zero_records, f"低密度命中应有未超标记录，实际无"
print(f"  ✓ 长文低密度模糊词按密度归一化未扣分: {zero_records[0]['reason']}")

# 断言 7（v1.3）：三方重叠 dedupe 不漏判
from scan import _dedupe_overlapping  # noqa
test_hits = [
    {"pos": 0, "match": "AB"},      # A: 0-2
    {"pos": 5, "match": "CD"},      # B: 5-7（独立）
    {"pos": 1, "match": "BC"},      # C: 1-3（与 A 重叠）
]
deduped = _dedupe_overlapping(test_hits)
positions = sorted([h["pos"] for h in deduped])
assert positions == [0, 5], f"三方重叠应保留 A(0) 和 B(5)，去掉 C(1)；实际 positions={positions}"
print("  ✓ _dedupe_overlapping 三方重叠去重正确")

# 断言 8（v1.4）：跨类别去重—— '综上所述' 一处不应被算多次
cross_cat_text = "综上所述，AI 影响很大。"
r_cross = scan(cross_cat_text, bl)
xcm = r_cross["findings"].get("_cross_category_matches")
assert xcm is not None and xcm["count"] >= 2, "应记录至少 2 处跨类别 suppress（jargon_academic.mid 和 closer_banned.mid 让位给 formal_connectors.high）"
print(f"  ✓ 跨类别匹配被记录: {xcm['count']} 处（仅按最高 severity 计分）")
# 一处'综上所述'最多扣 high 一次（4 分），不应是 8 分
total_deduct_for_zsss = sum(
    d["points"] for d in r_cross["deductions"]
    if "综上所述" in str(d) or any(c in d["reason"] for c in ("formal_connectors", "jargon_academic", "closer_banned"))
)
assert total_deduct_for_zsss <= 5, f"'综上所述'一处出现扣分应 ≤5（按 high 一次），实得 {total_deduct_for_zsss}"
print(f"  ✓ '综上所述'一处出现扣分 {total_deduct_for_zsss}（不再三类重复）")

# 断言 9（v1.4）：弯引号 report_only 不扣分
curly_text = "他说" + "“" + "项目顺利" + "”" + "。" * 5  # 含全角弯引号
r_curly = scan(curly_text, bl)
curly_deducts_with_points = [d for d in r_curly["deductions"] if "弯引号" in d["reason"] and d["points"] > 0]
assert not curly_deducts_with_points, f"弯引号 report_only 不应扣分，实得 {curly_deducts_with_points}"
print(f"  ✓ 全角弯引号 report_only 标记生效，未扣分")

# 断言 10（v1.5）：同类内子串重叠去重 —— '击穿心智' + '心智' 一处只应扣 high 一次
substr_text = "他们想击穿心智。"
r_sub = scan(substr_text, bl)
ji = r_sub["findings"].get("jargon_internet", {})
ji_high = ji.get("high", {})
ji_high_count = ji_high.get("count", 0)
assert ji_high_count == 1, f"'击穿心智' 一处应只算一次 high，实得 {ji_high_count} 处。findings={ji}"
sub_total_deduct = sum(d["points"] for d in r_sub["deductions"] if "jargon_internet" in d["reason"])
assert sub_total_deduct <= 4, f"'击穿心智' 一处应只扣 high 一次（≤4），实得 {sub_total_deduct}"
print(f"  ✓ 同类内子串重叠去重：'击穿心智' 一处只扣 {sub_total_deduct} 分（不重复扣『心智』）")

# 断言 11（v1.5）：跨类别 + 子串组合 —— '不断演变的格局' 一处只应扣 high 一次
mixed_text = "这反映了不断演变的格局。"
r_mix = scan(mixed_text, bl)
ata = r_mix["findings"].get("ai_translation_artifact", {})
ata_high_count = ata.get("high", {}).get("count", 0)
ata_mid_count = ata.get("mid", {}).get("count", 0)
assert ata_high_count == 1, f"'不断演变的格局' 应算一次 high，实得 {ata_high_count}"
assert ata_mid_count == 0, f"'格局' 子串应被压制不再算 mid，实得 mid count={ata_mid_count}"
print(f"  ✓ 跨类别+子串去重：'不断演变的格局' high=1, '格局' 子串 mid=0（被压制）")

# 断言 12（v1.6）：leveled 类与 flat 类统一去重 —— '在一定程度上' 不应重复扣分
vague_overlap_text = "这事在一定程度上影响了他。"
r_vague_overlap = scan(vague_overlap_text, bl)
overlap_deduct = [
    d for d in r_vague_overlap["deductions"]
    if any(key in d["reason"] for key in (
        "absolute_words", "vague_qualifiers_delete", "jargon_academic"
    ))
    and d["points"] > 0
]
assert len(overlap_deduct) == 1, f"'在一定程度上' 应只触发一次扣分，实际：{overlap_deduct}"
assert r_vague_overlap["findings"].get("_cross_category_matches"), "应记录 flat/leved 重叠 suppress"
print(f"  ✓ flat/leveled 统一去重：'在一定程度上' 只扣一次（{overlap_deduct[0]['points']} 分）")

# 断言 13（v1.6）：装饰 emoji 覆盖 Markdown 标题、列表和无空格标题
emoji_cases = ["🚀标题", "# 🚀 标题", "- ✅ 条目", "🛠️修复说明"]
for emoji_text in emoji_cases:
    r_emoji = scan(emoji_text, bl)
    assert "decorative_emojis" in r_emoji["findings"], f"应命中装饰 emoji：{emoji_text}"
print("  ✓ 装饰 emoji 覆盖 Markdown 标题、列表和无空格标题")

# 断言 14（v1.6）：stats 全 0 明确标记，避免退化输入被当成正常 cv=0
from scan import stats  # noqa
zero_stats = stats([0, 0, 0])
assert zero_stats["all_zero"] is True, f"全 0 统计应标记 all_zero，实际：{zero_stats}"
empty_stats = stats([])
assert empty_stats["all_zero"] is False and empty_stats["n"] == 0, f"空统计不是全 0 异常，实际：{empty_stats}"
print("  ✓ stats 全 0 退化输入有显式 all_zero 标记")

print()
print("自检全部通过 ✓")
