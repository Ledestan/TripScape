"""
行旅识景 TripScape / 文本切分工具
创建日期: 2026-11-25

供叙事卡片与地标页面共用的一套切句/取年规则，提供:
    1. split_sentences：按中文句末标点切句，并清掉 markdown 残留
    2. extract_year：抽取纪年（公元前记为负数），抽不到返回 None

依赖:
    需求文件: requirements.txt
    依赖库: 无（仅标准库）

用法:
    from services.text_utils import split_sentences, extract_year
    for sentence in split_sentences(text):
        year = extract_year(sentence)

注意:
    1. 两个模块必须共用同一套规则，否则卡片与页面会出现口径不一致。
    2. 抽不到年份一律返回 None：不补写、不猜测。
"""

import re

# 中文句末标点 + 换行（与文章库的排版一致）
_SENT_SPLIT = re.compile(r"(?<=[。！？；])\s*|\n+")
# 纪年：公元前后接 1-4 位数字，或 3-4 位年份
_YEAR_RE = re.compile(r"(公元前)?\s*(\d{1,4})\s*年")
# 摘编残留：模板括号、表格竖线、图片尺寸、空括号、括号内以标点开头——命中就整句丢弃
# 注意：不能把「；」「：」当残留——它们是正常中文标点，切句后句尾就带「；」
_CJK_RE = re.compile(r"[\u4e00-\u9fff]")
_ARTIFACT_RE = re.compile(r"[{}|]|thumb|\d{2,4}\s*px|（\s*）|（\s*[；：，、]|</?[a-zA-Z]")



def split_sentences(text: str) -> list[str]:
    """切句并清理 markdown 残留（空句与碎行丢弃，保留句末标点）。

    参数：
        text : str
            原始段落，允许包含 markdown 列表符、标题符与图片尺寸残留

    返回：
        list[str]：按出现顺序排列的句子

    注意：
        含残留标记的句子直接丢弃——宁可少一句，也不让「曲折金字塔（）」
        这种半截话出现在地标页或卡片里。
    """
    out: list[str] = []
    for part in _SENT_SPLIT.split(text or ""):
        sentence = re.sub(r"^[\s\-*·#|>]+", "", part or "").strip()
        sentence = re.sub(r"thumb\|\d+px\|?", "", sentence).strip()
        if len(sentence) < 6:
            continue
        if _ARTIFACT_RE.search(sentence):
            continue
        # 几乎没有中文的句子（英文图注、纯参数行）不进页面
        if len(_CJK_RE.findall(sentence)) < len(sentence) * 0.3:
            continue
        out.append(sentence)
    return out


def extract_year(text: str) -> int | None:
    """抽取纪年（公元前转负数），抽不到返回 None。"""
    match = _YEAR_RE.search(text or "")
    if not match:
        return None
    year = int(match.group(2))
    return -year if match.group(1) else year
