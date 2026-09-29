-- 删除旧表（如果存在）
DROP TABLE IF EXISTS heritage_items;
DROP TABLE IF EXISTS knowledge_base;

-- 创建地标信息表
CREATE TABLE heritage_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,  -- 主键，自增
    target_id VARCHAR(50) UNIQUE NOT NULL, -- 地标唯一标识
    name VARCHAR(100) NOT NULL             -- 地标中文名称
);

-- 创建问答知识库表
CREATE TABLE IF NOT EXISTS knowledge_base (
    id INTEGER PRIMARY KEY AUTOINCREMENT,  -- 主键，自动递增的唯一标识
    question TEXT NOT NULL,                -- 典型问题或提示词
    keywords TEXT,                         -- 逗号分隔的关键词，用于辅助匹配
    answer TEXT NOT NULL                   -- 对应的答案文本
);

-- 索引：加速常见检索方式
CREATE INDEX IF NOT EXISTS idx_kb_question ON knowledge_base(question);
CREATE INDEX IF NOT EXISTS idx_kb_keywords ON knowledge_base(keywords);

-- 验证插入数据
SELECT * FROM heritage_items;
SELECT * FROM knowledge_base;