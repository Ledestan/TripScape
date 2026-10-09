-- 徽章种子：10 枚成就徽章的定义数据。
-- 字段：code（唯一标识）/ name（徽章名）/ category（统计类别：footprint/comment/journal）/
--       threshold（达成阈值）/ icon（图标 emoji）/ description（达成条件描述）。
-- 由 `python backend/manage.py init_tripscape` 解析写入 Badge 表；
-- 新增徽章：按格式追加一行 INSERT 元组即可，无需改代码。

INSERT INTO badges (code, name, category, threshold, icon, description) VALUES

('first_footprint', '初次远行', 'footprint', 1, '👣', '留下第一个足迹'),
('footprint_5', '五洲行者', 'footprint', 5, '🧭', '足迹遍布 5 个地标'),
('footprint_15', '环球旅人', 'footprint', 15, '🗺️', '足迹遍布 15 个地标'),
('footprint_26', '世界图鉴', 'footprint', 26, '🌍', '集齐全部 26 个地标'),
('first_comment', '破冰发言', 'comment', 1, '💬', '发表第一条评论'),
('comment_10', '热心的游客', 'comment', 10, '🗣️', '累计发表 10 条评论'),
('comment_50', '社区元老', 'comment', 50, '🏆', '累计发表 50 条评论'),
('first_journal', '第一篇手账', 'journal', 1, '📔', '写下第一篇旅行手账'),
('journal_5', '旅行作家', 'journal', 5, '✍️', '累计创作 5 篇手账'),
('journal_20', '行旅编年史', 'journal', 20, '📚', '累计创作 20 篇手账');
