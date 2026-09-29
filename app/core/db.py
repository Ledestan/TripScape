"""
模块名称：地标数据库访问层

封装 SQLite 连接与查询，提供地标信息、知识库条目的读取接口。

约定：
- 每次查询创建新连接，避免线程间共享连接
- 行对象使用 sqlite3.Row，支持按列名访问
- 查询失败时统一返回 None
- 成功但无数据时返回 []（列表型）或 None（单值型）
"""

import sys

sys.dont_write_bytecode = True

import sqlite3

from app.core.config import DB_PATH


class LandmarkDB:
    """
    地标数据库访问对象。

    封装 heritage_items（地标信息）与 knowledge_base（知识库）两张表的读取。
    每次查询创建新连接，行对象支持按列名访问。
    """

    def __init__(self, path=DB_PATH):
        self.path = str(path)

    def _get_connection(self):
        """为当前请求创建新的数据库连接，返回字典式行"""
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def get_heritage_info(self, target_id=None):
        """
        获取地标信息（仅 target_id 和 name 两列）。

        参数：
            target_id : str, optional
                指定地标 ID；不传则返回全部记录

        返回：
            sqlite3.Row 或 list of sqlite3.Row；查询失败返回 None
        """
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
        获取所有地标的 target_id（用于后续扩展，如模板图片）。

        返回：
            list of sqlite3.Row，仅含 target_id 列；查询失败返回 None
        """
        conn = self._get_connection()
        try:
            sql = "SELECT target_id FROM heritage_items"
            rows = conn.execute(sql).fetchall()
            return rows
        except Exception as e:
            print(f"查询地标列表失败: {e}")
            return None
        finally:
            conn.close()

    def get_all_knowledge(self):
        """
        获取所有知识库条目。

        返回：
            list of sqlite3.Row，含 id / question / keywords / answer；
            查询失败返回 None
        """
        conn = self._get_connection()
        try:
            sql = "SELECT id, question, keywords, answer FROM knowledge_base"
            rows = conn.execute(sql).fetchall()
            return rows
        except Exception as e:
            print(f"查询知识库失败: {e}")
            return None
        finally:
            conn.close()

    def get_answer_by_question(self, question):
        """
        根据完整问题精确匹配答案。

        参数：
            question : str
                要匹配的问题原文

        返回：
            str 或 None，未匹配到或查询失败时返回 None
        """
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
