import requests
from datetime import datetime
from config import Config
import logging

logger = logging.getLogger(__name__)

class DeepLService:
    """DeepL API服务类"""
    
    def __init__(self):
        self.free_base_url = Config.DEEPL_FREE_BASE_URL
        self.pro_base_url = Config.DEEPL_PRO_BASE_URL
        self.timeout = Config.REQUEST_TIMEOUT
    
    def get_usage(self, api_key):
        """
        获取API密钥的用量信息
        
        Args:
            api_key (str): DeepL API密钥
            
        Returns:
            dict: 用量信息，包含成功状态和数据或错误信息
        """
        try:
            # 确定API类型和基础URL
            is_free = api_key.endswith(':fx')
            base_url = self.free_base_url if is_free else self.pro_base_url
            
            # 构建请求
            url = f"{base_url}/usage"
            headers = {
                'Authorization': f'DeepL-Auth-Key {api_key}',
                'Content-Type': 'application/json'
            }
            
            logger.info(f"查询API用量: {api_key[:10]}...{api_key[-4:]} ({'Free' if is_free else 'Pro'})")
            
            # 发送请求
            response = requests.get(url, headers=headers, timeout=self.timeout)
            
            if response.status_code == 200:
                data = response.json()
                
                # 解析响应数据
                usage_info = {
                    'is_success': True,
                    'character_count': data.get('character_count', 0),
                    'character_limit': data.get('character_limit', 0),
                    'api_type': 'free' if is_free else 'pro',
                    'check_time': datetime.utcnow()
                }
                
                # Pro API特有字段
                if not is_free:
                    usage_info.update({
                        'api_key_character_count': data.get('api_key_character_count'),
                        'api_key_character_limit': data.get('api_key_character_limit'),
                        'start_time': self._parse_datetime(data.get('start_time')),
                        'end_time': self._parse_datetime(data.get('end_time'))
                    })
                
                logger.info(f"查询成功: {usage_info['character_count']}/{usage_info['character_limit']}")
                return usage_info
                
            else:
                error_msg = f"API请求失败: HTTP {response.status_code}"
                if response.text:
                    try:
                        error_data = response.json()
                        error_msg += f" - {error_data.get('message', response.text)}"
                    except:
                        error_msg += f" - {response.text}"
                
                logger.error(f"查询失败: {error_msg}")
                return {
                    'is_success': False,
                    'error_message': error_msg,
                    'character_count': 0,
                    'character_limit': 0,
                    'check_time': datetime.utcnow()
                }
                
        except requests.exceptions.Timeout:
            error_msg = "请求超时"
            logger.error(f"查询超时: {api_key[:10]}...{api_key[-4:]}")
            return {
                'is_success': False,
                'error_message': error_msg,
                'character_count': 0,
                'character_limit': 0,
                'check_time': datetime.utcnow()
            }
            
        except requests.exceptions.RequestException as e:
            error_msg = f"网络请求错误: {str(e)}"
            logger.error(f"网络错误: {error_msg}")
            return {
                'is_success': False,
                'error_message': error_msg,
                'character_count': 0,
                'character_limit': 0,
                'check_time': datetime.utcnow()
            }
            
        except Exception as e:
            error_msg = f"未知错误: {str(e)}"
            logger.error(f"未知错误: {error_msg}")
            return {
                'is_success': False,
                'error_message': error_msg,
                'character_count': 0,
                'character_limit': 0,
                'check_time': datetime.utcnow()
            }
    
    def _parse_datetime(self, datetime_str):
        """解析ISO 8601格式的时间字符串"""
        if not datetime_str:
            return None
        
        try:
            # 移除时区信息中的Z并解析
            if datetime_str.endswith('Z'):
                datetime_str = datetime_str[:-1]
            
            return datetime.fromisoformat(datetime_str)
        except:
            return None
    
    def validate_api_key(self, api_key):
        """
        验证API密钥格式
        
        Args:
            api_key (str): API密钥
            
        Returns:
            dict: 验证结果
        """
        if not api_key or not isinstance(api_key, str):
            return {
                'is_valid': False,
                'error': 'API密钥不能为空'
            }
        
        api_key = api_key.strip()
        
        if len(api_key) < 10:
            return {
                'is_valid': False,
                'error': 'API密钥长度不足'
            }
        
        # 检测API类型
        is_free = api_key.endswith(':fx')
        api_type = 'free' if is_free else 'pro'
        
        return {
            'is_valid': True,
            'api_type': api_type,
            'api_key': api_key
        }

