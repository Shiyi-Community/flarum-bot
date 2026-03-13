import os
import time
import logging
import json
import signal
import toml
from typing import Dict, Any
from datetime import datetime
from flarum_client import FlarumClient
from ai_client import create_ai_client
from memory_manager import MemoryManager
from image_processor import ImageProcessor

# 从 toml 配置文件读取配置
with open('config.toml', 'r', encoding='utf-8') as f:
    config = toml.load(f)

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('flarumbot.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

class FlarumBot:
    def __init__(self):
        # 从配置文件读取参数
        self.flarum_url = config['flarum']['url']
        self.flarum_username = config['flarum']['username']
        self.flarum_password = config['flarum']['password']
        self.ai_provider = config['bot']['ai_provider']
        self.tag_whitelist = config['tags']['whitelist']
        self.check_interval = config['bot']['check_interval']
        
        # 运行状态标志
        self.running = True
        
        # 注册信号处理
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        self.flarum_client = FlarumClient(
            self.flarum_url,
            self.flarum_username,
            self.flarum_password
        )
        
        self.ai_client = self._init_ai_client()
        self.replied_posts_file = 'replied_posts.json'
        self.replied_posts = self._load_replied_posts()
        self.processed_replies_file = 'processed_replies.json'
        self.processed_replies = self._load_processed_replies()
        
        # 初始化记忆管理和图片处理
        self.memory_manager = MemoryManager()
        
        # 根据提供商选择对应的 API key
        image_provider = config['bot']['image_provider']
        if image_provider == 'siliconflow':
            image_api_key = config['siliconflow']['api_key']
        elif image_provider == 'openai':
            image_api_key = config['openai']['api_key']
        elif image_provider == 'google':
            image_api_key = config['gemini']['api_key']
        else:
            image_api_key = None
        
        self.image_processor = ImageProcessor(
            api_key=image_api_key,
            provider=image_provider
        )
    
    def _signal_handler(self, signum, frame):
        """信号处理函数"""
        logger.info(f"收到关闭信号 {signum}，正在优雅关闭...")
        self.running = False

    def _load_processed_replies(self) -> set:
        if os.path.exists(self.processed_replies_file):
            try:
                with open(self.processed_replies_file, 'r', encoding='utf-8') as f:
                    return set(json.load(f))
            except Exception as e:
                logger.error(f"加载已处理回复列表失败: {e}")
        return set()

    def _save_processed_replies(self):
        try:
            with open(self.processed_replies_file, 'w', encoding='utf-8') as f:
                json.dump(list(self.processed_replies), f)
        except Exception as e:
            logger.error(f"保存已处理回复列表失败: {e}")

    def _init_ai_client(self):
        config = self._get_ai_config()
        return create_ai_client(self.ai_provider, config)

    def _get_ai_config(self) -> dict:
        provider = self.ai_provider.lower()
        config = {
            'system_prompt': globals()['config']['bot']['system_prompt']
        }
        
        if provider == 'openai':
            config.update({
                'api_key': globals()['config']['openai']['api_key'],
                'base_url': globals()['config']['openai']['base_url'],
                'model': globals()['config']['openai']['model']
            })
        elif provider == 'deepseek':
            config.update({
                'api_key': globals()['config']['deepseek']['api_key'],
                'base_url': globals()['config']['deepseek']['base_url'],
                'model': globals()['config']['deepseek']['model']
            })
        elif provider == 'siliconflow':
            config.update({
                'api_key': globals()['config']['siliconflow']['api_key'],
                'base_url': globals()['config']['siliconflow']['base_url'],
                'model': globals()['config']['siliconflow']['model']
            })
        elif provider == 'gemini':
            config.update({
                'api_key': globals()['config']['gemini']['api_key'],
                'model': globals()['config']['gemini']['model']
            })
        
        return config

    def _load_replied_posts(self) -> set:
        if os.path.exists(self.replied_posts_file):
            try:
                with open(self.replied_posts_file, 'r', encoding='utf-8') as f:
                    return set(json.load(f))
            except Exception as e:
                logger.error(f"加载已回复帖子列表失败: {e}")
        return set()

    def _save_replied_posts(self):
        try:
            with open(self.replied_posts_file, 'w', encoding='utf-8') as f:
                json.dump(list(self.replied_posts), f)
        except Exception as e:
            logger.error(f"保存已回复帖子列表失败: {e}")

    def _extract_post_content(self, post_data: dict) -> str:
        attributes = post_data.get('attributes', {})
        # 优先使用 content 字段，然后使用 contentHtml 字段
        content = attributes.get('content', '')
        if not content:
            content = attributes.get('contentHtml', '')
        
        # 简单的 HTML 转文本
        import re
        # 移除 HTML 标签
        content = re.sub(r'<[^>]+>', '', content)
        # 移除多余的空白字符
        content = re.sub(r'\s+', ' ', content).strip()
        
        return content

    def _get_first_post_content(self, discussion_id: int) -> str:
        posts_data = self.flarum_client.get_posts(discussion_id)
        posts = posts_data.get('data', [])
        logger.debug(f"获取到 {len(posts)} 个帖子")
        if posts:
            # 优先找编号为 1 的帖子（首帖）
            for i, post in enumerate(posts):
                logger.debug(f"帖子 {i}: {post}")
                post_num = post.get('attributes', {}).get('number', 0)
                logger.debug(f"帖子编号: {post_num}")
                if post_num == 1:
                    content = self._extract_post_content(post)
                    logger.debug(f"提取的内容: {content}")
                    return content
            # 如果没有找到首帖，返回第一个帖子的内容
            if posts:
                content = self._extract_post_content(posts[0])
                logger.debug(f"未找到首帖，返回第一个帖子的内容: {content}")
                return content
        return ""

    def _check_new_replies(self):
        """检查已回复帖子的新回复"""
        if not self.replied_posts:
            return
        
        for discussion_id in self.replied_posts:
            try:
                posts_data = self.flarum_client.get_posts(int(discussion_id))
                posts = posts_data.get('data', [])
                if posts:
                    for post in posts:
                        post_id = post.get('id')
                        post_number = post.get('attributes', {}).get('number', 0)
                        post_user_id = post.get('relationships', {}).get('user', {}).get('data', {}).get('id')
                        
                        # 跳过自己的回复和已经处理过的回复
                        if post_id in self.processed_replies or post_user_id == str(self.flarum_client.user_id):
                            continue
                        
                        # 检查是否 @ 了机器人
                        content = self._extract_post_content(post)
                        logger.debug(f"处理帖子 {post_id} (编号: {post_number})，内容: {content}")
                        # 从帖子数据中获取用户信息
                        user_data = post.get('relationships', {}).get('user', {})
                        user_id = user_data.get('data', {}).get('id')
                        # 从 included 字段中获取用户名
                        username = '用户'
                        included = posts_data.get('included', [])
                        for item in included:
                            if item.get('type') == 'users' and item.get('id') == user_id:
                                username = item.get('attributes', {}).get('username', '用户')
                                break
                        logger.debug(f"获取到用户名: {username}")
                        if f'@{self.flarum_username}' in content:
                            logger.info(f"收到 @ 提及: 帖子 {discussion_id}, 回复 {post_id}")
                            # 传递完整的帖子数据，包含 included 字段
                            self._reply_to_mention(int(discussion_id), content, post_id, posts_data)
                        # 检查是否是新回复（非首帖）
                        elif post_number > 1:
                            logger.info(f"发现新回复: 帖子 {discussion_id}, 回复 {post_id}")
                            # 传递完整的帖子数据，包含 included 字段
                            self._reply_to_new_reply(int(discussion_id), content, post_id, posts_data)
            except Exception as e:
                logger.error(f"检查新回复失败: {e}")

    def _get_user_info(self, user_id: str) -> Dict[str, Any]:
        """从用户 API 获取用户信息"""
        try:
            # 这里需要实现从 users API 获取用户信息的逻辑
            # 暂时返回模拟数据
            return {
                'username': f'用户{user_id}'
            }
        except Exception as e:
            logger.error(f"获取用户信息失败: {e}")
            return {}

    def _get_post_info(self, post_id: str) -> Dict[str, Any]:
        """获取帖子信息"""
        try:
            # 从讨论 ID 中获取帖子信息
            # 假设 post_id 格式为 "{discussion_id}-{post_number}" 或纯数字
            discussion_id = post_id.split('-')[0] if '-' in post_id else post_id
            posts_data = self.flarum_client.get_posts(int(discussion_id))
            posts = posts_data.get('data', [])
            included = posts_data.get('included', [])
            
            if posts:
                for post in posts:
                    if post.get('id') == post_id:
                        # 从帖子数据中获取用户信息
                        user_data = post.get('relationships', {}).get('user', {})
                        user_id = user_data.get('data', {}).get('id')
                        
                        # 从 included 字段中获取用户名
                        username = '用户'
                        for item in included:
                            if item.get('type') == 'users' and item.get('id') == user_id:
                                username = item.get('attributes', {}).get('username', '用户')
                                break
                        
                        post_number = post.get('attributes', {}).get('number', '')
                        return {
                            'user_id': user_id,
                            'username': username,
                            'post_number': post_number
                        }
        except Exception as e:
            logger.error(f"获取帖子信息失败: {e}")
        return {
            'user_id': '',
            'username': '用户',
            'post_number': '1'
        }

    def _reply_to_mention(self, discussion_id: int, mention_content: str, post_id: str, post_data=None):
        """回复 @ 提及"""
        try:
            # 处理图片内容
            processed_content = self.image_processor.process_content_with_images(mention_content)
            
            # 从帖子数据中获取用户信息
            if post_data:
                # 检查 post_data 的类型
                if isinstance(post_data, dict) and 'data' in post_data:
                    # 完整的 posts_data 字典
                    # 查找对应的帖子
                    found_post = False
                    for post in post_data.get('data', []):
                        if post.get('id') == post_id:
                            user_data = post.get('relationships', {}).get('user', {})
                            user_id = user_data.get('data', {}).get('id')
                            # 从 included 字段中获取用户名
                            included = post_data.get('included', [])
                            username = '用户'
                            for item in included:
                                if item.get('type') == 'users' and item.get('id') == user_id:
                                    username = item.get('attributes', {}).get('username', '用户')
                                    break
                            found_post = True
                            break
                    if not found_post:
                        # 没有找到帖子，使用原来的方法
                        post_info = self._get_post_info(post_id)
                        username = post_info.get('username', '用户')
                elif isinstance(post_data, dict):
                    # 单个帖子对象
                    user_data = post_data.get('relationships', {}).get('user', {})
                    # 检查 included 字段中的用户信息
                    included = post_data.get('included', [])
                    for item in included:
                        if item.get('type') == 'users' and item.get('id') == user_data.get('data', {}).get('id'):
                            username = item.get('attributes', {}).get('username', '用户')
                            break
                    else:
                        # 直接从帖子数据中获取
                        username = user_data.get('attributes', {}).get('username', '用户')
                else:
                    # 其他类型，使用原来的方法
                    post_info = self._get_post_info(post_id)
                    username = post_info.get('username', '用户')
            else:
                # 使用原来的方法
                post_info = self._get_post_info(post_id)
                username = post_info.get('username', '用户')
            
            # 构建引用格式
            if post_id and username:
                quote_format = f'@"{username}"#p{post_id}\n\n'
            else:
                quote_format = ''
            
            # 获取对话历史
            history = self.memory_manager.get_conversation_history(str(discussion_id))
            history_text = "\n".join([f"{msg['role']}: {msg['content']}" for msg in history])
            
            # 构建带记忆的提示
            prompt = f"用户 @ 了你，内容如下:\n{processed_content}\n\n"
            if history:
                prompt += "历史对话:\n"
                for msg in history:
                    if msg['role'] == 'user':
                        prompt += f"用户: {msg['content']}\n"
                    else:
                        prompt += f"你: {msg['content']}\n"
                prompt += "\n"
            prompt += "请回复这个提及:"
            
            ai_response = self.ai_client.generate_response(prompt)
            if ai_response:
                # 构建完整回复，包含引用格式
                full_response = quote_format + ai_response
                if self.flarum_client.create_post(discussion_id, full_response):
                    # 保存到记忆
                    self.memory_manager.add_message(
                        discussion_id=str(discussion_id),
                        content=processed_content,
                        role='user'
                    )
                    self.memory_manager.add_message(
                        discussion_id=str(discussion_id),
                        content=full_response,
                        role='assistant'
                    )
                    
                    self.processed_replies.add(post_id)
                    self._save_processed_replies()
                    logger.info(f"成功回复 @ 提及: 帖子 {discussion_id}")
        except Exception as e:
            logger.error(f"回复 @ 提及失败: {e}")

    def _reply_to_new_reply(self, discussion_id: int, reply_content: str, post_id: str, post_data=None):
        """回复新回复"""
        try:
            # 获取帖子标题和首帖内容
            discussion = self.flarum_client.get_discussion(discussion_id)
            title = discussion.get('data', {}).get('attributes', {}).get('title', '无标题')
            
            # 获取首帖内容
            first_post_content = self._get_first_post_content(discussion_id)
            
            # 处理图片内容
            processed_reply = self.image_processor.process_content_with_images(reply_content)
            
            # 从帖子数据中获取用户信息
            if post_data:
                # 检查 post_data 的类型
                if isinstance(post_data, dict) and 'data' in post_data:
                    # 完整的 posts_data 字典
                    # 查找对应的帖子
                    found_post = False
                    for post in post_data.get('data', []):
                        if post.get('id') == post_id:
                            user_data = post.get('relationships', {}).get('user', {})
                            user_id = user_data.get('data', {}).get('id')
                            # 从 included 字段中获取用户名
                            included = post_data.get('included', [])
                            username = '用户'
                            for item in included:
                                if item.get('type') == 'users' and item.get('id') == user_id:
                                    username = item.get('attributes', {}).get('username', '用户')
                                    break
                            found_post = True
                            break
                    if not found_post:
                        # 没有找到帖子，使用原来的方法
                        post_info = self._get_post_info(post_id)
                        username = post_info.get('username', '用户')
                elif isinstance(post_data, dict):
                    # 单个帖子对象
                    user_data = post_data.get('relationships', {}).get('user', {})
                    # 检查 included 字段中的用户信息
                    included = post_data.get('included', [])
                    for item in included:
                        if item.get('type') == 'users' and item.get('id') == user_data.get('data', {}).get('id'):
                            username = item.get('attributes', {}).get('username', '用户')
                            break
                    else:
                        # 直接从帖子数据中获取
                        username = user_data.get('attributes', {}).get('username', '用户')
                else:
                    # 其他类型，使用原来的方法
                    post_info = self._get_post_info(post_id)
                    username = post_info.get('username', '用户')
            else:
                # 使用原来的方法
                post_info = self._get_post_info(post_id)
                username = post_info.get('username', '用户')
            
            # 构建引用格式
            if post_id and username:
                quote_format = f'@"{username}"#p{post_id}\n\n'
            else:
                quote_format = ''
            
            # 获取对话历史
            history = self.memory_manager.get_conversation_history(str(discussion_id))
            history_text = "\n".join([f"{msg['role']}: {msg['content']}" for msg in history])
            
            # 构建带记忆的提示
            prompt = f"帖子标题: {title}\n\n首帖内容: {first_post_content}\n\n新回复内容: {processed_reply}\n\n"
            if history:
                prompt += "历史对话:\n"
                for msg in history:
                    if msg['role'] == 'user':
                        prompt += f"用户: {msg['content']}\n"
                    else:
                        prompt += f"助手: {msg['content']}\n"
                prompt += "\n"
            prompt += "请回复这个新回复:"
            
            ai_response = self.ai_client.generate_response(prompt)
            if ai_response:
                # 构建完整回复，包含引用格式
                full_response = quote_format + ai_response
                if self.flarum_client.create_post(discussion_id, full_response):
                    # 保存到记忆
                    self.memory_manager.add_message(
                        discussion_id=str(discussion_id),
                        content=processed_reply,
                        role='user'
                    )
                    self.memory_manager.add_message(
                        discussion_id=str(discussion_id),
                        content=full_response,
                        role='assistant'
                    )
                    
                    self.processed_replies.add(post_id)
                    self._save_processed_replies()
                    logger.info(f"成功回复新回复: 帖子 {discussion_id}")
        except Exception as e:
            logger.error(f"回复新回复失败: {e}")

    def run(self):
        logger.info(f"欢迎使用 FlarumBot！")
        logger.info(f"该 Bot 不是由 Flarum 官方开发，Just For Fun~")
        logger.info(f"FlarumBot 不收费，如果有人向你收费出售此软件，他是在骗你！")
        logger.info(f"开源地址：https://github.com/Shiyi-Community/FlarumBot")
        logger.info(f"FlarumBot 启动，监控标签: {self.tag_whitelist}")
        logger.info(f"使用 AI 提供商: {self.ai_provider}")
        logger.info(f"检查间隔: {self.check_interval} 秒")
        
        if not self.flarum_client.login():
            logger.error("Flarum 登录失败，程序退出")
            return

        logger.info("按 Ctrl+C 停止程序...")
        
        while self.running:
            try:
                self._process_discussions()
                self._check_new_replies()
            except Exception as e:
                logger.error(f"处理帖子时发生错误: {e}")
            
            if self.running:
                logger.info(f"等待 {self.check_interval} 秒后继续检查...")
                # 分多次检查运行状态，实现更快的响应
                for _ in range(self.check_interval):
                    if not self.running:
                        break
                    time.sleep(1)
        
        logger.info("FlarumBot 已退出")

    def _process_discussions(self):
        # 使用白名单中的第一个标签作为监控标签
        discussions = []
        if self.tag_whitelist:
            monitor_tag = self.tag_whitelist[0]
            discussions = self.flarum_client.get_discussions_by_tag(monitor_tag)
            logger.info(f"找到 {len(discussions)} 个带有标签 '{monitor_tag}' 的帖子")
        else:
            logger.warning("没有配置白名单标签，跳过帖子处理")
        
        for discussion in discussions:
            discussion_id = discussion.get('id')
            if not discussion_id:
                continue
            
            discussion_id_str = str(discussion_id)
            if discussion_id_str in self.replied_posts:
                logger.debug(f"帖子 {discussion_id} 已回复过，跳过")
                continue
            
            attributes = discussion.get('attributes', {})
            title = attributes.get('title', '无标题')
            can_reply = attributes.get('canReply', False)
            
            if not can_reply:
                logger.info(f"帖子 {discussion_id} 不允许回复 (canReply: {can_reply})，跳过")
                # 标记为已处理，避免重复检查
                self.replied_posts.add(discussion_id_str)
                self._save_replied_posts()
                continue
            
            logger.info(f"处理帖子: {title} (ID: {discussion_id})")
            
            content = self._get_first_post_content(int(discussion_id))
            if not content:
                logger.warning(f"无法获取帖子 {discussion_id} 的内容")
                continue
            
            # 获取首帖的用户信息
            posts_data = self.flarum_client.get_posts(int(discussion_id))
            posts = posts_data.get('data', [])
            username = '用户'
            if posts:
                # 找到首帖（编号为 1 的帖子）
                for post in posts:
                    post_number = post.get('attributes', {}).get('number', 0)
                    if post_number == 1:
                        # 从帖子数据中获取用户信息
                        user_data = post.get('relationships', {}).get('user', {})
                        user_id = user_data.get('data', {}).get('id')
                        # 从 included 字段中获取用户名
                        included = posts_data.get('included', [])
                        for item in included:
                            if item.get('type') == 'users' and item.get('id') == user_id:
                                username = item.get('attributes', {}).get('username', '用户')
                                break
                        break
            logger.debug(f"首帖用户: {username}")
            
            # 处理图片内容
            processed_content = self.image_processor.process_content_with_images(content)
            
            # 获取对话历史
            history = self.memory_manager.get_conversation_history(discussion_id_str)
            history_text = "\n".join([f"{msg['role']}: {msg['content']}" for msg in history])
            
            # 构建带记忆的提示
            prompt = f"帖子标题: {title}\n\n帖子内容: {processed_content}\n\n"
            if history:
                prompt += f"历史对话:\n{history_text}\n\n"
            prompt += "请回复这个帖子:"
            
            ai_response = self.ai_client.generate_response(prompt)
            if not ai_response:
                logger.error(f"AI 生成回复失败，跳过帖子 {discussion_id}")
                continue
            
            # 构建引用格式（首帖回复也需要引用）
            if username != '用户':
                # 找到首帖的 ID
                first_post_id = None
                for post in posts:
                    post_number = post.get('attributes', {}).get('number', 0)
                    if post_number == 1:
                        first_post_id = post.get('id')
                        break
                if first_post_id:
                    quote_format = f'@"{username}"#p{first_post_id}\n\n'
                    full_response = quote_format + ai_response
                else:
                    full_response = ai_response
            else:
                full_response = ai_response
            
            if self.flarum_client.create_post(int(discussion_id), full_response):
                # 保存到记忆
                self.memory_manager.add_message(
                    discussion_id=discussion_id_str,
                    content=processed_content,
                    role='user'
                )
                self.memory_manager.add_message(
                    discussion_id=discussion_id_str,
                    content=full_response,
                    role='assistant'
                )
                
                self.replied_posts.add(discussion_id_str)
                self._save_replied_posts()
                logger.info(f"成功回复帖子 {discussion_id}")
            else:
                logger.error(f"回复帖子 {discussion_id} 失败")

def main():
    bot = FlarumBot()
    bot.run()

if __name__ == '__main__':
    main()
