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
# 纪年：只认"年份"，不把时长当成年份（41年、4500年、19世纪70年代都不算）
_BC_RE = re.compile(r"公元前\s*(\d{1,4})\s*年")
_BC_SHORT_RE = re.compile(r"(?<!公元)前\s*(\d{1,4})\s*年")
_AD_RE = re.compile(r"公元\s*(\d{1,4})\s*年")
_FOUR_DIGIT_RE = re.compile(r"(\d{4})\s*年(?!代)")
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
        # 以逗号/顿号/冒号结尾的是半截话（原文换行被切断），不进页面；
        # 以分号结尾的是分句，补成句号后保留（分号在正文里读起来像没说完）
        if sentence.endswith(("，", "、", "：", ",")):
            continue
        if sentence.endswith("；"):
            sentence = sentence[:-1] + "。"
        out.append(sentence)
    return out


def extract_year(text: str) -> int | None:
    """抽取纪年（公元前记为负数），抽不到返回 None。

    参数：
        text : str，一句话

    返回：
        int | None：年份；公元前为负；不是年份（时长、年代、数量）一律 None

    注意：
        1. 只有"公元前/前…年""公元…年""4 位年份"才算纪年：
           「曾是世界最高建筑 41 年」「已逾 4500 年」「19 世纪 70 年代」
           都不是年份，直接返回 None，宁可时间轴少一条也不写错。
        2. 句中已出现"公元"且不是"公元前"时，允许 3 位年份（公元 72 年 - 82 年）。
    """
    if not text:
        return None

    match = _BC_RE.search(text) or _BC_SHORT_RE.search(text)
    if match:
        return -int(match.group(1))

    match = _AD_RE.search(text)
    if match:
        return int(match.group(1))

    if "公元" in text and "公元前" not in text:
        for match in re.finditer(r"(\d{1,3})\s*年(?!代)", text):
            return int(match.group(1))

    match = _FOUR_DIGIT_RE.search(text)
    if match:
        year = int(match.group(1))
        if 1000 <= year <= 2029:
            return year

    return None
