import sqlite3
import logging
import json
from datetime import datetime
from typing import List, Dict, Optional, Any

logger = logging.getLogger(__name__)

class MemoryManager:
    def __init__(self, db_path: str = 'memory.db'):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """初始化数据库"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 创建对话历史表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS conversations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    discussion_id TEXT NOT NULL,
                    user_id TEXT,
                    username TEXT,
                    content TEXT NOT NULL,
                    role TEXT NOT NULL,  -- 'user' or 'assistant'
                    timestamp TEXT NOT NULL,
                    embedding TEXT
                )
            ''')
            
            # 创建用户信息表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT UNIQUE NOT NULL,
                    username TEXT NOT NULL,
                    metadata TEXT
                )
            ''')
            
            # 创建索引
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_conversations_discussion ON conversations(discussion_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_conversations_timestamp ON conversations(timestamp)')
            
            conn.commit()
            conn.close()
            logger.info(f"数据库初始化成功: {self.db_path}")
        except Exception as e:
            logger.error(f"数据库初始化失败: {e}")

    def add_message(self, discussion_id: str, content: str, role: str, 
                   user_id: Optional[str] = None, username: Optional[str] = None):
        """添加消息到记忆"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            timestamp = datetime.now().isoformat()
            
            cursor.execute('''
                INSERT INTO conversations (discussion_id, user_id, username, content, role, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (discussion_id, user_id, username, content, role, timestamp))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"添加消息失败: {e}")
            return False

    def get_conversation_history(self, discussion_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        """获取对话历史"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT * FROM conversations 
                WHERE discussion_id = ? 
                ORDER BY timestamp DESC 
                LIMIT ?
            ''', (discussion_id, limit))
            
            rows = cursor.fetchall()
            conn.close()
            
            # 反转顺序，使最早的消息在前
            messages = []
            for row in reversed(rows):
                messages.append({
                    'id': row['id'],
                    'discussion_id': row['discussion_id'],
                    'user_id': row['user_id'],
                    'username': row['username'],
                    'content': row['content'],
                    'role': row['role'],
                    'timestamp': row['timestamp']
                })
            
            return messages
        except Exception as e:
            logger.error(f"获取对话历史失败: {e}")
            return []

    def add_user(self, user_id: str, username: str, metadata: Optional[Dict] = None):
        """添加或更新用户信息"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            metadata_str = json.dumps(metadata) if metadata else None
            
            # 尝试更新，如果不存在则插入
            cursor.execute('''
                INSERT INTO users (user_id, username, metadata)
                VALUES (?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    username = excluded.username,
                    metadata = excluded.metadata
            ''', (user_id, username, metadata_str))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"添加用户失败: {e}")
            return False

    def get_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        """获取用户信息"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
            row = cursor.fetchone()
            conn.close()
            
            if row:
                metadata = json.loads(row['metadata']) if row['metadata'] else None
                return {
                    'id': row['id'],
                    'user_id': row['user_id'],
                    'username': row['username'],
                    'metadata': metadata
                }
            return None
        except Exception as e:
            logger.error(f"获取用户信息失败: {e}")
            return None

    def search_memory(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """搜索记忆"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # 简单的文本搜索
            cursor.execute('''
                SELECT * FROM conversations 
                WHERE content LIKE ? 
                ORDER BY timestamp DESC 
                LIMIT ?
            ''', (f'%{query}%', limit))
            
            rows = cursor.fetchall()
            conn.close()
            
            results = []
            for row in rows:
                results.append({
                    'id': row['id'],
                    'discussion_id': row['discussion_id'],
                    'user_id': row['user_id'],
                    'username': row['username'],
                    'content': row['content'],
                    'role': row['role'],
                    'timestamp': row['timestamp']
                })
            
            return results
        except Exception as e:
            logger.error(f"搜索记忆失败: {e}")
            return []

    def clear_memory(self, discussion_id: Optional[str] = None):
        """清除记忆"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            if discussion_id:
                cursor.execute('DELETE FROM conversations WHERE discussion_id = ?', (discussion_id,))
            else:
                cursor.execute('DELETE FROM conversations')
            
            conn.commit()
            conn.close()
            logger.info(f"记忆已清除: {discussion_id or '全部'}")
            return True
        except Exception as e:
            logger.error(f"清除记忆失败: {e}")
            return False
