import sqlite3


class LandmarkDB:
    def __init__(self, path="data/landmark.db"):
        self.path = path

    def _get_connection(self):
        """为当前请求创建新的数据库连接，返回字典式行"""
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def get_heritage_info(self, target_id=None):
        """获取地标信息（仅 target_id 和 name）"""
        conn = self._get_connection()
        try:
            if target_id:
                sql = "SELECT target_id, name FROM heritage_items WHERE target_id = ?"
                row = conn.execute(sql, (target_id,)).fetchone()
                return row
            else:
                sql = "SELECT target_id, name FROM heritage_items"
                rows = conn.execute(sql).fetchall()
                return rows
        except Exception as e:
            print(f"查询地标信息失败: {e}")
            return None
        finally:
            conn.close()

    def get_all_heritage_targets(self):
        """
        获取所有地标的 target_id（用于后续扩展，如模板图片）
        此版本不再依赖 image_path 列
        """
        conn = self._get_connection()
        try:
            sql = "SELECT target_id FROM heritage_items"
            rows = conn.execute(sql).fetchall()
            return rows
        except Exception as e:
            print(f"查询地标列表失败: {e}")
            return []
        finally:
            conn.close()

    def get_all_knowledge(self):
        """获取所有知识库条目"""
        conn = self._get_connection()
        try:
            sql = "SELECT id, question, keywords, answer FROM knowledge_base"
            rows = conn.execute(sql).fetchall()
            return rows
        except Exception as e:
            print(f"查询知识库失败: {e}")
            return []
        finally:
            conn.close()

    def get_answer_by_question(self, question):
        """根据完整问题精确匹配答案"""
        conn = self._get_connection()
        try:
            sql = "SELECT answer FROM knowledge_base WHERE question = ?"
            row = conn.execute(sql, (question,)).fetchone()
            return row["answer"] if row else None
        except Exception as e:
            print(f"精确查询失败: {e}")
            return None
        finally:
            conn.close()
