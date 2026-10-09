-- 敏感词种子：内容安全基线词表（命中即拦截评论/手账发布）。
-- 由 `python backend/manage.py init_tripscape` 解析写入 SensitiveWord 表；
-- 运行期可在管理后台动态增删（后台「审计日志」Tab 的敏感词管理），此处仅为初始基线。

INSERT INTO sensitive_words (word) VALUES

('加微信'),
('代开发票'),
('刷单'),
('赌博'),
('博彩'),
('色情'),
('枪支'),
('毒品');
