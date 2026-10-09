"""行旅识景 TripScape
创建日期：2025-09-01

用户账号：注册登录、昵称签名、隐私开关、封禁/禁言/限登字段。
"""

from django.apps import AppConfig


class AccountsConfig(AppConfig):
    name = "apps.accounts"
    label = "accounts"
    verbose_name = "用户"
