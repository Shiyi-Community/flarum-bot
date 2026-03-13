import logging
import requests
from typing import Optional, Dict, Any, List
from PIL import Image
import io

logger = logging.getLogger(__name__)

class ImageProcessor:
    def __init__(self, api_key: Optional[str] = None, provider: str = 'openai'):
        self.api_key = api_key
        self.provider = provider.lower()

    def analyze_image(self, image_url: str) -> Optional[str]:
        """分析图片内容"""
        try:
            if self.provider == 'openai':
                return self._analyze_with_openai(image_url)
            elif self.provider == 'google':
                return self._analyze_with_google(image_url)
            elif self.provider == 'siliconflow':
                return self._analyze_with_siliconflow(image_url)
            elif self.provider == 'local':
                return self._analyze_with_local(image_url)
            else:
                logger.error(f"不支持的图片分析提供商: {self.provider}")
                return None
        except Exception as e:
            logger.error(f"图片分析失败: {e}")
            return None

    def _analyze_with_openai(self, image_url: str) -> Optional[str]:
        """使用 OpenAI Vision API 分析图片"""
        if not self.api_key:
            logger.error("OpenAI API key 未设置")
            return None
        
        try:
            import openai
            client = openai.OpenAI(api_key=self.api_key)
            
            # 下载图片
            response = requests.get(image_url)
            response.raise_for_status()
            image_data = response.content
            
            # 分析图片
            response = client.chat.completions.create(
                model="gpt-4-vision-preview",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": "请详细描述这张图片的内容，包括场景、人物、物体、颜色等细节。"
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": image_url
                                }
                            }
                        ]
                    }
                ],
                max_tokens=1000
            )
            
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"OpenAI 图片分析失败: {e}")
            return None

    def _analyze_with_google(self, image_url: str) -> Optional[str]:
        """使用 Google Vision API 分析图片"""
        if not self.api_key:
            logger.error("Google API key 未设置")
            return None
        
        try:
            from google.cloud import vision
            client = vision.ImageAnnotatorClient(
                client_options={
                    "api_key": self.api_key
                }
            )
            
            image = vision.Image()
            image.source.image_uri = image_url
            
            # 分析图片
            response = client.label_detection(image=image)
            labels = response.label_annotations
            
            if labels:
                description = "图片中包含: " + ", ".join([label.description for label in labels[:10]])
                return description
            else:
                return "未能识别图片内容"
        except Exception as e:
            logger.error(f"Google 图片分析失败: {e}")
            return None

    def _analyze_with_siliconflow(self, image_url: str) -> Optional[str]:
        """使用 SiliconFlow API 分析图片"""
        if not self.api_key:
            logger.error("SiliconFlow API key 未设置")
            return None
        
        try:
            import openai
            client = openai.OpenAI(
                api_key=self.api_key,
                base_url="https://api.siliconflow.cn/v1"
            )
            
            # 分析图片
            response = client.chat.completions.create(
                model="Qwen/Qwen2.5-7B-Instruct",
                messages=[
                    {
                        "role": "user",
                        "content": f"请详细描述这张图片的内容，包括场景、人物、物体、颜色等细节。图片链接: {image_url}"
                    }
                ],
                max_tokens=1000
            )
            
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"SiliconFlow 图片分析失败: {e}")
            return None

    def _analyze_with_local(self, image_url: str) -> Optional[str]:
        """使用本地方法分析图片（基本信息）"""
        try:
            # 下载图片
            response = requests.get(image_url)
            response.raise_for_status()
            image_data = response.content
            
            # 打开图片
            image = Image.open(io.BytesIO(image_data))
            width, height = image.size
            mode = image.mode
            format = image.format
            
            description = f"图片信息: 尺寸 {width}x{height}, 模式 {mode}, 格式 {format}"
            return description
        except Exception as e:
            logger.error(f"本地图片分析失败: {e}")
            return None

    def extract_images_from_content(self, content: str) -> List[str]:
        """从内容中提取图片链接"""
        import re
        # 匹配图片链接
        image_patterns = [
            r'https?://[^\s]+\.(jpg|jpeg|png|gif|webp)',
            r'!\[.*?\]\((https?://[^\s]+\.(jpg|jpeg|png|gif|webp))\)'
        ]
        
        image_urls = []
        for pattern in image_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            for match in matches:
                if isinstance(match, tuple):
                    image_urls.append(match[0])
                else:
                    image_urls.append(match)
        
        # 去重
        return list(set(image_urls))

    def process_content_with_images(self, content: str) -> str:
        """处理包含图片的内容"""
        image_urls = self.extract_images_from_content(content)
        if not image_urls:
            return content
        
        processed_content = content
        for image_url in image_urls:
            image_description = self.analyze_image(image_url)
            if image_description:
                processed_content += f"\n\n[图片分析] {image_description}"
        
        return processed_content
