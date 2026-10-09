"""敏感词服务与问答引擎单元测试。"""

import os
import sys
from pathlib import Path

import django

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "backend"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from apps.core.sensitive import check_text, mask_text


class TestSensitive:
    def test_clean_text(self):
        ok, word = check_text("这是一个正常的旅行分享")
        assert ok and word is None

    def test_hit(self):
        ok, word = check_text("加微信聊")
        assert not ok and word == "加微信"

    def test_custom_word_from_db(self, db):
        from apps.admin_panel.models import SensitiveWord

        SensitiveWord.objects.create(word="黑导游")
        ok, word = check_text("小心黑导游")
        assert not ok and word == "黑导游"

    def test_fullwidth_bypass_blocked(self):
        # 全角绕过也应拦截
        ok, _ = check_text("加微ｃｈａｔ刷单")
        assert not ok

    def test_mask(self):
        masked = mask_text("这里有加微信广告")
        assert "加微信" not in masked
