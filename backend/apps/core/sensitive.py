"""行旅识景 TripScape
创建日期：2025-09-01

敏感词服务：评论 / 手账发布时自动拦截。

- 词库来源：SensitiveWord 模型（管理端可增删改），叠加内置基础词表
- 命中即返回 True，发布层负责拦截（评论/手账转待审核或直接拒绝）
"""

import logging

logger = logging.getLogger("tripscape.sensitive")

# 内置兜底词表（可通过管理端扩充）
BUILTIN_WORDS = [
    "加微信",
    "代开发票",
    "刷单",
    "赌博",
    "博彩",
    "色情",
    "枪支",
    "毒品",
]


def _normalize(text: str) -> str:
    """全角转半角 + 去空白，规避常见绕过。"""
    if not text:
        return ""
    out = []
    for ch in text:
        code = ord(ch)
        if code == 0x3000:
            code = 32
        elif 0xFF01 <= code <= 0xFF5E:
            code -= 0xFEE0
        out.append(chr(code))
    return "".join(out).replace(" ", "").replace("\t", "").replace("\n", "")


def load_words() -> set:
    from apps.admin_panel.models import SensitiveWord

    words = set(BUILTIN_WORDS)
    try:
        for w in SensitiveWord.objects.filter(is_active=True).values_list(
            "word", flat=True
        ):
            if w:
                words.add(_normalize(w))
    except Exception as exc:  # 初次迁移前表不存在
        logger.debug("加载敏感词失败（可能未迁移）：%s", exc)
    return words


def check_text(text: str):
    """检查文本。

    返回：
        (ok, hit_word)
        ok=True 表示未命中；ok=False 时 hit_word 为命中的词
    """
    if not text:
        return True, None
    normalized = _normalize(text)
    for word in load_words():
        if word and word in normalized:
            return False, word
    return True, None


def mask_text(text: str, mask: str = "*") -> str:
    """将命中的敏感词打码（用于展示层）。"""
    ok, word = check_text(text)
    if ok:
        return text
    return text.replace(word, mask * len(word))
