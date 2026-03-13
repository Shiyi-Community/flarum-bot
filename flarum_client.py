import requests
import json
import logging
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

class FlarumClient:
    def __init__(self, base_url: str, username: str, password: str):
        self.base_url = base_url.rstrip('/')
        self.username = username
        self.password = password
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Referer': f'{self.base_url}/',
            'X-Requested-With': 'XMLHttpRequest'
        })
        self.token: Optional[str] = None
        self.user_id: Optional[int] = None
        self.csrf_token: Optional[str] = None

    def _get_csrf_token(self) -> bool:
        try:
            response = self.session.get(f"{self.base_url}/")
            import re
            # 从 JavaScript 代码中提取 CSRF token
            match = re.search(r'csrfToken":"([^"]+)"', response.text)
            if match:
                self.csrf_token = match.group(1)
                logger.info(f"获取到 CSRF token: {self.csrf_token[:10]}...")
                self.session.headers.update({
                    'X-CSRF-Token': self.csrf_token
                })
                return True
            else:
                logger.error("无法从页面中提取 CSRF token")
                logger.debug(f"页面内容前 500 字符: {response.text[:500]}")
                return False
        except Exception as e:
            logger.error(f"获取 CSRF token 失败: {e}")
            return False

    def login(self) -> bool:
        # 先获取 CSRF token
        if not self._get_csrf_token():
            return False
            
        url = f"{self.base_url}/api/token"
        payload = {
            "identification": self.username,
            "password": self.password
        }
        try:
            response = self.session.post(url, json=payload)
            logger.debug(f"登录请求 URL: {url}")
            logger.debug(f"登录请求响应状态码: {response.status_code}")
            logger.debug(f"登录请求响应内容: {response.text[:500]}")
            
            response.raise_for_status()
            data = response.json()
            self.token = data.get('token')
            self.user_id = data.get('userId')
            if self.token:
                # 确保会话头中包含所有必要的 headers
                self.session.headers.update({
                    'Authorization': f'Token {self.token}',
                    'X-CSRF-Token': self.csrf_token,
                    'Content-Type': 'application/json',
                    'Accept': 'application/json',
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'Connection': 'keep-alive',
                    'Referer': f'{self.base_url}/',
                    'X-Requested-With': 'XMLHttpRequest'
                })
                logger.info(f"登录成功: {self.username}")
                logger.info(f"获取到 Token: {self.token[:10]}...")
                logger.info(f"设置 Authorization 头: Token {self.token[:10]}...")
                return True
        except Exception as e:
            logger.error(f"登录失败: {e}")
            logger.error(f"响应状态码: {response.status_code if 'response' in locals() else 'N/A'}")
            logger.error(f"响应内容: {response.text[:500] if 'response' in locals() else 'N/A'}")
        return False

    def get_discussions_by_tag(self, tag: str, page: int = 0, limit: int = 20) -> List[Dict[str, Any]]:
        url = f"{self.base_url}/api/discussions"
        params = {
            'filter[q]': f'tag:{tag}',
            'page[offset]': page * limit,
            'page[limit]': limit
        }
        try:
            response = self.session.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            return data.get('data', [])
        except Exception as e:
            logger.error(f"获取帖子列表失败: {e}")
            return []

    def get_discussion(self, discussion_id: int) -> Optional[Dict[str, Any]]:
        url = f"{self.base_url}/api/discussions/{discussion_id}"
        try:
            response = self.session.get(url)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"获取帖子详情失败: {e}")
            return None

    def get_posts(self, discussion_id: int) -> Dict[str, Any]:
        url = f"{self.base_url}/api/posts"
        params = {
            'filter[discussion]': discussion_id
        }
        try:
            response = self.session.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            return data
        except Exception as e:
            logger.error(f"获取帖子回复失败: {e}")
            return {'data': [], 'included': []}

    def create_post(self, discussion_id: int, content: str) -> bool:
        url = f"{self.base_url}/api/posts"
        # 正确的 JSON API 格式
        payload = {
            "data": {
                "type": "posts",
                "attributes": {
                    "content": content
                },
                "relationships": {
                    "discussion": {
                        "data": {
                            "type": "discussions",
                            "id": str(discussion_id)
                        }
                    }
                }
            }
        }
        try:
            # 确保会话仍然有效
            if not self.token:
                logger.error("Token 不存在，需要重新登录")
                if not self.login():
                    return False
            
            # 更新 Referer 头，使用当前讨论的 URL
            self.session.headers['Referer'] = f'{self.base_url}/d/{discussion_id}'
            
            # 直接使用 session 中已经设置好的 headers
            response = self.session.post(url, json=payload)
            logger.debug(f"回复请求 URL: {url}")
            logger.debug(f"回复请求 payload: {payload}")
            logger.debug(f"回复请求响应状态码: {response.status_code}")
            logger.debug(f"回复请求响应内容: {response.text}")
            
            if response.status_code == 403:
                logger.error(f"权限不足，尝试重新登录")
                if self.login():
                    # 重新发送请求
                    self.session.headers['Referer'] = f'{self.base_url}/d/{discussion_id}'
                    response = self.session.post(url, json=payload)
                    logger.debug(f"重新发送请求后的状态码: {response.status_code}")
                    logger.debug(f"重新发送请求后的响应内容: {response.text}")
            
            response.raise_for_status()
            logger.info(f"回复成功: 讨论ID {discussion_id}")
            return True
        except Exception as e:
            logger.error(f"回复失败: {e}")
            if 'response' in locals():
                logger.error(f"响应状态码: {response.status_code}")
                logger.error(f"响应内容: {response.text}")
            return False

    def get_tags(self) -> List[Dict[str, Any]]:
        url = f"{self.base_url}/api/tags"
        try:
            response = self.session.get(url)
            response.raise_for_status()
            data = response.json()
            return data.get('data', [])
        except Exception as e:
            logger.error(f"获取标签列表失败: {e}")
            return []
