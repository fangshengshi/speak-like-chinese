#!/usr/bin/env python3
"""
speak-like-chinese · 静态扫描器 v1.6

用法:
    python scan.py <text-file>
    python scan.py --stdin < text.md
    python scan.py --text "你的文本"

输出 JSON 报告，包含:
- 命中的 AI 模式（按 severity 分组）
- 句子长度统计（burstiness 指标）
- 段落长度统计
- 综合评分（0-100）
- warning 字段（提示分数仅参考，不要作为优化目标）

不读取 style-mapping.json（该文件供 LLM 改写参考，scan.py 不消费）。
不处理 blacklist 的 ai_writing_structural（该类是结构性惯例，regex 抓不准，由 LLM 凭语义自判）。
不处理 blacklist 的 context_safe_when（专业语境豁免由 LLM 在改写时凭语境判断；scan.py 仅做命中提示）。

纯 stdlib，无依赖。
"""
from __future__ import annotations
import argparse
import io
import json
import math
import re
import sys
from pathlib import Path
from typing import Any

try:
    if (sys.stdout.encoding or "").lower().replace("-", "") != "utf8":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    if (sys.stderr.encoding or "").lower().replace("-", "") != "utf8":
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")
except AttributeError:
    # Some capture environments replace stdio with objects that do not expose .buffer.
    pass

MAX_FILE_BYTES = 2_000_000  # 2MB 上限，防 DoS


def load_blacklist() -> dict[str, Any]:
    """从 references/blacklist.json 加载词库。"""
    here = Path(__file__).resolve().parent
    bl_path = here.parent / "references" / "blacklist.json"
    try:
        raw = bl_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        sys.stderr.write(f"错误：找不到词库文件 {bl_path}\n")
        sys.exit(2)
    except OSError as e:
        sys.stderr.write(f"错误：读取词库文件失败 {bl_path} - {e}\n")
        sys.exit(2)
    except UnicodeDecodeError as e:
        sys.stderr.write(f"错误：词库文件不是 UTF-8 - {e}\n")
        sys.exit(2)
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        sys.stderr.write(f"错误：词库文件 JSON 解析失败 - {e}\n")
        sys.exit(2)


# 默认评分权重——若 blacklist.json 提供 _scoring_weights 则会覆盖。
DEFAULT_WEIGHTS = {
    "high_per_hit": 4,
    "high_cap": 20,
    "mid_per_hit": 2,
    "mid_cap": 12,
    "low_per_hit": 1,
    "low_cap": 6,
    "flat_high4_categories": ["vapid_ing_analysis"],
    "flat_low1_categories": [
        "filler_phrases",
        "vague_qualifiers_delete",
        "decorative_emojis",
    ],
    "vague_soften_density_per_chars": 200,  # 模糊词每 200 字命中 1 次以上才算扣
    "vague_soften_cap": 6,
    "curly_quotes_per_hit": 1,
    "curly_quotes_cap": 5,
    "negation_high_per_hit": 4,
    "negation_high_cap": 20,
    "sentence_cv_threshold": 0.4,
    "sentence_uniform_penalty": 8,
    "sentence_min_n": 5,
    "paragraph_std_threshold": 1.0,
    "paragraph_uniform_penalty": 5,
    "paragraph_min_n": 3,
}


def get_weights(bl: dict[str, Any]) -> dict[str, Any]:
    """合并 blacklist._scoring_weights 与 DEFAULT_WEIGHTS（前者优先）。"""
    user = bl.get("_scoring_weights") or {}
    merged = dict(DEFAULT_WEIGHTS)
    if isinstance(user, dict):
        merged.update(user)
    return merged


def find_keywords(text: str, words: list[str]) -> list[dict[str, Any]]:
    """精确子串匹配，返回每个命中的位置和 word。"""
    hits = []
    for w in words:
        if not w:
            continue
        start = 0
        while True:
            idx = text.find(w, start)
            if idx < 0:
                break
            hits.append({"word": w, "pos": idx})
            start = idx + len(w)
    return hits


def find_regex(text: str, pattern: str) -> list[dict[str, Any]]:
    try:
        return [
            {"match": m.group(0), "pos": m.start()}
            for m in re.finditer(pattern, text)
        ]
    except re.error as e:
        sys.stderr.write(f"warning: 正则编译失败，跳过 '{pattern}' - {e}\n")
        return []


def split_sentences_zh(text: str) -> list[str]:
    """
    中文句子粗分。按 。！？ 切，过滤空。
    引号内的句号会被错误切分（如 "他说：'我好。'"），是已知粗略行为，
    若需要精确分句应替换为带状态的解析器。
    """
    parts = re.split(r"[。！？!?]+", text)
    return [p.strip() for p in parts if p.strip()]


def split_paragraph_spans(text: str) -> list[tuple[str, int]]:
    """返回非空段落及其在原文中的起点。"""
    spans: list[tuple[str, int]] = []
    for m in re.finditer(r"\S(?:.*?)(?=\n\s*\n+|\Z)", text, re.DOTALL):
        raw = m.group(0)
        para = raw.strip()
        if para:
            spans.append((para, m.start()))
    return spans


def split_paragraphs(text: str) -> list[str]:
    return [p for p, _ in split_paragraph_spans(text)]


def stats(values: list[int]) -> dict[str, Any]:
    if not values:
        return {"n": 0, "mean": 0.0, "std": 0.0, "cv": 0.0, "all_zero": False}
    n = len(values)
    mean = sum(values) / n
    var = sum((v - mean) ** 2 for v in values) / n
    std = math.sqrt(var)
    all_zero = all(v == 0 for v in values)
    cv = std / mean if mean > 0 else 0
    return {
        "n": n,
        "mean": round(mean, 2),
        "std": round(std, 2),
        "cv": round(cv, 3),
        "all_zero": all_zero,
    }


def _dedupe_candidates(
    candidates: list[dict[str, Any]],
    text_len: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """
    按已排序的候选优先级做 span 去重。

    owner_by_pos 用文本位置直接定位已保留 span，避免对 kept 做 O(C^2)
    两两重叠检查。复杂度约为 O(C log C + 命中 span 总长度)。
    """
    kept: list[dict[str, Any]] = []
    suppressed: list[dict[str, Any]] = []
    owner_by_pos = [-1] * max(text_len, 0)

    for cand in candidates:
        start = max(0, int(cand["start"]))
        end = min(text_len, int(cand["end"]))
        if end <= start:
            continue

        overlap_idx = -1
        for pos in range(start, end):
            if owner_by_pos[pos] != -1:
                overlap_idx = owner_by_pos[pos]
                break

        if overlap_idx == -1:
            kept_idx = len(kept)
            kept.append(cand)
            for pos in range(start, end):
                owner_by_pos[pos] = kept_idx
        else:
            overlap_with = kept[overlap_idx]
            suppressed.append({
                "suppressed": {
                    "word": cand.get("word") or cand.get("match"),
                    "start": cand["start"],
                    "cat": cand["cat"],
                    "sev": cand["sev"],
                },
                "kept": {
                    "word": overlap_with.get("word") or overlap_with.get("match"),
                    "start": overlap_with["start"],
                    "cat": overlap_with["cat"],
                    "sev": overlap_with["sev"],
                },
                "reason": (
                    "cross_category_same_span" if (
                        cand["start"] == overlap_with["start"]
                        and cand["end"] == overlap_with["end"]
                    ) else "substring_or_overlap"
                ),
            })

    return sorted(kept, key=lambda c: (c["start"], c["end"], c["cat"])), suppressed


def _dedupe_overlapping(hits: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    多个 pattern 命中同一段文本时去重：重叠区间只保留最长匹配。
    例：'不是X而是Y' 同时被 '不是.{1,15}而是' 和 '不是.{1,15}是' 命中——去重后算 1 处。

    与 v1.2 早期版本相比：扫描所有已 kept 项检查重叠（不仅 kept[-1]），
    避免"A 和 C 重叠但 A 和 B 不重叠"的三方拓扑漏判。
    """
    if not hits:
        return []
    # 按长度降序、pos 升序优先：长的先保留，短的后来若与已保留 span 重叠则跳过。
    sorted_hits = sorted(hits, key=lambda h: (-len(h.get("match", "")), h["pos"]))
    max_end = max(h["pos"] + len(h.get("match", "")) for h in sorted_hits)
    candidates = [
        {
            "start": h["pos"],
            "end": h["pos"] + len(h.get("match", "")),
            "match": h.get("match", ""),
            "cat": "_local",
            "sev": "high",
            "hit": h,
        }
        for h in sorted_hits
    ]
    kept, _ = _dedupe_candidates(candidates, max_end)
    return sorted([k["hit"] for k in kept], key=lambda h: h["pos"])


def negation_density_check(text: str, patterns: list[str]) -> dict[str, Any]:
    """
    否定排比的密度判断。
    同段命中 ≥2 处 → high；同段单处 → 视为合法递进，跳过。
    多 pattern 重叠命中同一区间时去重，避免单处被算成多处。
    """
    paras = split_paragraphs(text)
    para_hits: list[dict[str, Any]] = []
    total = 0
    high_density_count = 0
    for pi, p in enumerate(paras):
        raw_local: list[dict[str, Any]] = []
        for pat in patterns:
            raw_local.extend(find_regex(p, pat))
        local = _dedupe_overlapping(raw_local)
        if not local:
            continue
        para_hits.append({"para_idx": pi, "count": len(local), "hits": local[:10]})
        total += len(local)
        if len(local) >= 2:
            high_density_count += len(local)
    return {
        "total_hits": total,
        "high_density_hits": high_density_count,  # 仅这部分按 high 扣分
        "low_density_hits": total - high_density_count,  # 单段单处保留
        "per_paragraph": para_hits[:10],
    }


def scan(text: str, bl: dict[str, Any]) -> dict[str, Any]:
    findings: dict[str, Any] = {}
    sev_rank = {"high": 3, "mid": 2, "low": 1}

    # ── 1. 可定位 span 类：统一收集候选，再做全局去重 ──
    leveled_categories = [
        "jargon_internet",
        "jargon_academic",
        "formal_connectors",
        "opener_banned",
        "closer_banned",
        "ai_vocab_universal",
        "ai_translation_artifact",
        "absolute_words",
        "sycophancy",
    ]
    flat_categories = [
        "negation_parallel",
        "vapid_ing_analysis",
        "decorative_emojis",
        "filler_phrases",
        "vague_qualifiers_delete",
        "vague_qualifiers_soften",
    ]
    category_order = leveled_categories + flat_categories
    cat_rank = {c: i for i, c in enumerate(category_order)}

    # 第一遍：收集所有候选 span (start, end, word, cat, sev)
    candidates: list[dict[str, Any]] = []
    for cat_key in leveled_categories:
        cat = bl.get(cat_key, {})
        for sev in ("high", "mid", "low"):
            words = cat.get(sev) or []
            if not isinstance(words, list):
                continue
            for h in find_keywords(text, words):
                candidates.append({
                    "start": h["pos"],
                    "end": h["pos"] + len(h["word"]),
                    "word": h["word"],
                    "cat": cat_key,
                    "sev": sev,
                })
    # 「化」后缀低密度示例也进 candidates 走统一去重，归入 jargon_internet.low
    ji = bl.get("jargon_internet", {})
    suffix = ji.get("low_template")
    if suffix:
        for h in find_keywords(text, ji.get("low_examples") or []):
            candidates.append({
                "start": h["pos"],
                "end": h["pos"] + len(h["word"]),
                "word": h["word"],
                "cat": "jargon_internet",
                "sev": "low",
            })

    # 否定排比先按段内去重，再进入全局候选池。最终是否扣 high 仍由 kept 后的段内密度决定。
    neg = bl.get("negation_parallel", {})
    if neg.get("patterns"):
        for pi, (para, para_start) in enumerate(split_paragraph_spans(text)):
            raw_local: list[dict[str, Any]] = []
            for pat in neg["patterns"]:
                raw_local.extend(find_regex(para, pat))
            local = _dedupe_overlapping(raw_local)
            local_sev = "high" if len(local) >= 2 else "low"
            for h in local:
                start = para_start + h["pos"]
                match = h.get("match", "")
                candidates.append({
                    "start": start,
                    "end": start + len(match),
                    "match": match,
                    "word": match,
                    "cat": "negation_parallel",
                    "sev": local_sev,
                    "para_idx": pi,
                })

    ving = bl.get("vapid_ing_analysis", {})
    for pat in ving.get("patterns_zh", []):
        for h in find_regex(text, pat):
            candidates.append({
                "start": h["pos"],
                "end": h["pos"] + len(h["match"]),
                "match": h["match"],
                "cat": "vapid_ing_analysis",
                "sev": "high",
            })

    deco = bl.get("decorative_emojis_in_headings", {})
    if deco.get("regex"):
        for m in re.finditer(deco["regex"], text, re.MULTILINE):
            candidates.append({
                "start": m.start(),
                "end": m.end(),
                "match": m.group(0),
                "cat": "decorative_emojis",
                "sev": "low",
            })

    fp = bl.get("filler_phrases", {}).get("map") or {}
    for h in find_keywords(text, list(fp.keys())):
        candidates.append({
            "start": h["pos"],
            "end": h["pos"] + len(h["word"]),
            "word": h["word"],
            "cat": "filler_phrases",
            "sev": "low",
        })

    vq = bl.get("vague_qualifiers", {})
    for h in find_keywords(text, vq.get("delete") or []):
        candidates.append({
            "start": h["pos"],
            "end": h["pos"] + len(h["word"]),
            "word": h["word"],
            "cat": "vague_qualifiers_delete",
            "sev": "low",
        })
    for h in find_keywords(text, list((vq.get("soften_to_concrete") or {}).keys())):
        candidates.append({
            "start": h["pos"],
            "end": h["pos"] + len(h["word"]),
            "word": h["word"],
            "cat": "vague_qualifiers_soften",
            "sev": "low",
        })

    # 全局 span 级去重（v1.6）：所有可定位 span 候选统一处理
    # 排序键（优先级高→低）：
    #   1. severity 高优先（high > mid > low）
    #   2. 精确词库类优先于泛化 regex/flat 类（避免「反映了...的...」抢走具体翻译腔）
    #   3. 长度长优先（覆盖整词如「击穿心智」优于子串「心智」、「不断演变的格局」优于「格局」）
    #   4. 类别顺序（category_order 列表索引）
    #   5. start 位置升序（确定性）
    candidates.sort(key=lambda c: (
        -sev_rank.get(c["sev"], 0),
        0 if c["cat"] in leveled_categories else 1,
        -(c["end"] - c["start"]),
        cat_rank.get(c["cat"], 999),
        c["start"],
    ))

    kept, suppressed = _dedupe_candidates(candidates, len(text))

    # 第二遍：构建 findings（仅 kept 计入）
    for cat_key in leveled_categories:
        bucket: dict[str, Any] = {}
        for k in kept:
            if k["cat"] != cat_key:
                continue
            sev = k["sev"]
            entry = bucket.setdefault(sev, {"count": 0, "hits": []})
            entry["count"] += 1
            if len(entry["hits"]) < 50:
                entry["hits"].append({"word": k["word"], "pos": k["start"]})
        if bucket:
            findings[cat_key] = bucket

    neg_kept = [k for k in kept if k["cat"] == "negation_parallel"]
    if neg_kept:
        by_para: dict[int, list[dict[str, Any]]] = {}
        for k in neg_kept:
            by_para.setdefault(int(k.get("para_idx", 0)), []).append(k)
        para_hits = []
        high_density_count = 0
        total = 0
        for pi in sorted(by_para):
            items = sorted(by_para[pi], key=lambda x: x["start"])
            total += len(items)
            if len(items) >= 2:
                high_density_count += len(items)
            para_hits.append({
                "para_idx": pi,
                "count": len(items),
                "hits": [
                    {"match": x["match"], "pos": x["start"]}
                    for x in items[:10]
                ],
            })
        findings["negation_parallel"] = {
            "total_hits": total,
            "high_density_hits": high_density_count,
            "low_density_hits": total - high_density_count,
            "per_paragraph": para_hits[:10],
        }

    for cat_key in ("vapid_ing_analysis", "decorative_emojis"):
        hits = [
            {"match": k["match"], "pos": k["start"]}
            for k in kept if k["cat"] == cat_key
        ]
        if hits:
            findings[cat_key] = {"count": len(hits), "hits": hits[:30]}

    for cat_key in ("filler_phrases", "vague_qualifiers_delete", "vague_qualifiers_soften"):
        hits = [
            {"word": k["word"], "pos": k["start"]}
            for k in kept if k["cat"] == cat_key
        ]
        if hits:
            findings[cat_key] = {"count": len(hits), "hits": hits[:30]}

    if suppressed:
        findings["_cross_category_matches"] = {
            "note": (
                "同一/重叠 span 多次命中——v1.6 起所有可定位 span 统一按 (severity, 长度, 类别顺序) "
                "保留最优 span，其他作为 suppressed 记录调试用。"
                "覆盖 (a) 跨类别同 span，(b) 同类内子串重叠，"
                "(c) leveled 类与 flat 类重叠（如『在一定程度上』+『一定』）。"
            ),
            "count": len(suppressed),
            "matches": suppressed[:50],
        }

    # ── 6. 英文弯引号（中文场景默认 report_only，不扣分） ──
    cq_cfg = bl.get("curly_quotes_english", {})
    cq = cq_cfg.get("chars") or []
    cq_count = sum(text.count(c) for c in cq)
    if cq_count:
        findings["curly_quotes"] = {
            "count": cq_count,
            "report_only": bool(cq_cfg.get("report_only")),
        }

    # ── 9. 句子/段落统计 ──
    sents = split_sentences_zh(text)
    sent_lens = [len(s) for s in sents]
    paras = split_paragraphs(text)
    para_lens = [len(split_sentences_zh(p)) for p in paras]
    sent_stats = stats(sent_lens)
    para_stats = stats(para_lens)

    # ── 10. 综合评分（权重表外置；含 raw_total 透明记录） ──
    weights = get_weights(bl)
    score = 100
    deductions = []
    text_len = len(text)

    def deduct(reason: str, points: int):
        nonlocal score
        if points <= 0:
            return
        score -= points
        deductions.append({"reason": reason, "points": points})

    flat_high4 = set(weights.get("flat_high4_categories") or [])
    flat_low1 = set(weights.get("flat_low1_categories") or [])

    for cat_key, bucket in findings.items():
        if cat_key == "negation_parallel":
            high_d = bucket.get("high_density_hits", 0)
            low_d = bucket.get("low_density_hits", 0)
            if high_d:
                deduct(
                    f"否定排比·高密度（同段≥2 处）: {high_d} 处",
                    min(high_d * weights["negation_high_per_hit"], weights["negation_high_cap"]),
                )
            if low_d:
                deductions.append({
                    "reason": f"否定排比·单处保留（合法递进）: {low_d} 处",
                    "points": 0,
                    "note": "未扣分；按密度规则视为合法",
                })
            continue
        if cat_key == "vague_qualifiers_soften":
            # 按密度归一化：每 N 字命中 1 次以上才扣（避免常见词在长文中系统性偏低）
            cnt = bucket.get("count", 0)
            density_per = weights.get("vague_soften_density_per_chars", 200)
            allowance = max(1, text_len // density_per)
            excess = max(0, cnt - allowance)
            if excess > 0:
                pts = min(excess * weights["low_per_hit"], weights["vague_soften_cap"])
                deduct(
                    f"vague_qualifiers_soften·密度超标: {cnt} 处（{text_len} 字允许 {allowance}）",
                    pts,
                )
            elif cnt > 0:
                deductions.append({
                    "reason": f"vague_qualifiers_soften: {cnt} 处（在 {text_len} 字内允许 {allowance} 次，未超标）",
                    "points": 0,
                    "note": "未扣分；按文本长度归一化判定为正常密度",
                })
            continue
        if cat_key in flat_high4:
            cnt = bucket.get("count", 0)
            if cnt:
                deduct(f"{cat_key}: {cnt} 处", min(cnt * weights["high_per_hit"], weights["high_cap"]))
            continue
        if cat_key in flat_low1:
            cnt = bucket.get("count", 0)
            if cnt:
                deduct(f"{cat_key}: {cnt} 处", min(cnt * weights["low_per_hit"], weights["low_cap"]))
            continue
        if cat_key == "curly_quotes":
            cnt = bucket.get("count", 0)
            if not cnt:
                continue
            if bucket.get("report_only"):
                deductions.append({
                    "reason": f"英文弯引号: {cnt} 处（report_only，不扣分；中文场景规范用法）",
                    "points": 0,
                    "note": "未扣分；中文写作中弯引号是规范标点",
                })
            else:
                deduct(
                    f"英文弯引号: {cnt} 处（中文场景弱信号）",
                    min(cnt * weights["curly_quotes_per_hit"], weights["curly_quotes_cap"]),
                )
            continue
        if cat_key == "_cross_category_matches":
            # 仅作为信息字段，不扣分（已在 span_owner 阶段处理）
            continue
        # leveled 类别（dict of high/mid/low）
        high_n = (bucket.get("high") or {}).get("count", 0)
        mid_n = (bucket.get("mid") or {}).get("count", 0)
        low_n = (bucket.get("low") or {}).get("count", 0)
        if high_n:
            deduct(f"{cat_key}.high: {high_n} 处", min(high_n * weights["high_per_hit"], weights["high_cap"]))
        if mid_n:
            deduct(f"{cat_key}.mid: {mid_n} 处", min(mid_n * weights["mid_per_hit"], weights["mid_cap"]))
        if low_n:
            deduct(f"{cat_key}.low: {low_n} 处", min(low_n * weights["low_per_hit"], weights["low_cap"]))

    # 节奏检查
    if sent_stats["n"] >= weights["sentence_min_n"]:
        cv = sent_stats["cv"]
        std = sent_stats["std"]
        if sent_stats.get("all_zero"):
            deduct("句长统计全为 0（异常分句结果）", weights["sentence_uniform_penalty"])
        elif std == 0:
            deduct("句长完全一致（std=0）", weights["sentence_uniform_penalty"])
        elif 0 < cv < weights["sentence_cv_threshold"]:
            deduct(f"句长过于均匀 (cv={cv})", weights["sentence_uniform_penalty"])
    if para_stats["n"] >= weights["paragraph_min_n"]:
        if para_stats.get("all_zero"):
            deduct("段落句数统计全为 0（异常分段结果）", weights["paragraph_uniform_penalty"])
        elif para_stats["std"] < weights["paragraph_std_threshold"]:
            deduct(f"段落长度过于一致 (std={para_stats['std']})", weights["paragraph_uniform_penalty"])

    raw_total = sum(d["points"] for d in deductions)
    final_score = max(0, min(100, score))
    raw_deductions_exceed_score = raw_total > 100

    grade = (
        "优秀（自然）"
        if final_score >= 90
        else "良好（轻微 AI 味）"
        if final_score >= 80
        else "一般（明显 AI 味）"
        if final_score >= 70
        else "较差（模板化严重）"
        if final_score >= 60
        else "很差（典型 AI 文本）"
    )

    return {
        "score": final_score,
        "grade": grade,
        "raw_deductions_total": raw_total,
        "raw_deductions_exceed_score": raw_deductions_exceed_score,
        "deductions": deductions,
        "findings": findings,
        "sentence_stats": sent_stats,
        "paragraph_stats": para_stats,
        "warning": (
            "本评分仅反映模板度，不反映语义保真。"
            "不要把分数升高当作改写目标——若合法术语命中导致扣分，应保留术语；"
            "为刷分而删除语义合法的词是负优化。"
            "本扫描不处理 context_safe_when（专业语境豁免由 LLM 在改写时凭语境判断），"
            "也不处理 ai_writing_structural（结构性惯例由 LLM 凭语义自判）。"
        ),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="speak-like-chinese 静态扫描器")
    ap.add_argument("file", nargs="?", help="待扫描文本文件（与 --stdin / --text 三选一）")
    ap.add_argument("--stdin", action="store_true", help="从标准输入读取")
    ap.add_argument("--text", help="直接传入文本")
    ap.add_argument("--pretty", action="store_true", help="美化 JSON 输出")
    args = ap.parse_args()

    sources = sum(bool(x) for x in [args.file, args.stdin, args.text])
    if sources != 1:
        ap.error("必须三选一：file / --stdin / --text")

    if args.stdin:
        # 按字节限制 stdin，避免中文多字节输入绕过 2MB 上限。
        raw = sys.stdin.buffer.read(MAX_FILE_BYTES + 1)
        if len(raw) > MAX_FILE_BYTES:
            ap.error(
                f"stdin 输入过大（> {MAX_FILE_BYTES} 字节上限）；请分段扫描。"
            )
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as e:
            ap.error(f"stdin 不是 UTF-8 编码：{e}")
    elif args.text is not None:
        text = args.text
        if len(text.encode("utf-8", errors="ignore")) > MAX_FILE_BYTES:
            ap.error(
                f"--text 输入过大（> {MAX_FILE_BYTES} 字节上限）；请使用文件输入分段扫描。"
            )
    else:
        path = Path(args.file)
        try:
            size = path.stat().st_size
        except OSError as e:
            ap.error(f"无法读取文件：{e}")
        if size > MAX_FILE_BYTES:
            ap.error(
                f"文件过大（{size} 字节，上限 {MAX_FILE_BYTES} 字节）；请分段扫描。"
            )
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as e:
            ap.error(f"读文件失败：{e}")
        except UnicodeDecodeError as e:
            ap.error(f"文件不是 UTF-8 编码：{e}")

    bl = load_blacklist()
    report = scan(text, bl)
    indent = 2 if args.pretty else None
    print(json.dumps(report, ensure_ascii=False, indent=indent))
    return 0


if __name__ == "__main__":
    sys.exit(main())
