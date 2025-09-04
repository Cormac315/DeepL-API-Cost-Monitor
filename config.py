import os
from datetime import timedelta

class Config:
    # Flask配置
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'deepl-api-monitor-secret-key'
    
    # 数据库配置
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///api_monitor.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # DeepL API配置
    DEEPL_FREE_BASE_URL = 'https://api-free.deepl.com/v2'
    DEEPL_PRO_BASE_URL = 'https://api.deepl.com/v2'
    
    # 调度器配置
    SCHEDULER_API_ENABLED = True
    SCHEDULER_TIMEZONE = 'Asia/Shanghai'
    
    # 默认查询频率（秒）
    DEFAULT_QUERY_INTERVAL = 3600  # 1小时
    
    # 并发控制
    MAX_CONCURRENT_GROUPS = 10
    REQUEST_TIMEOUT = 30


