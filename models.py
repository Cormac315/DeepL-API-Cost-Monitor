from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class ApiGroup(db.Model):
    """API组模型"""
    __tablename__ = 'api_groups'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    query_interval = db.Column(db.Integer, default=3600)  # 查询间隔（秒）
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # 关联的API密钥
    api_keys = db.relationship('ApiKey', backref='group', lazy=True, cascade='all, delete-orphan')
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'query_interval': self.query_interval,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'api_keys_count': len(self.api_keys)
        }

class ApiKey(db.Model):
    """API密钥模型"""
    __tablename__ = 'api_keys'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)  # 密钥别名
    api_key = db.Column(db.String(200), nullable=False, unique=True)  # 实际的API密钥
    api_type = db.Column(db.String(10), nullable=False)  # 'free' 或 'pro'
    group_id = db.Column(db.Integer, db.ForeignKey('api_groups.id'), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_check = db.Column(db.DateTime)
    
    # Pro API的计费周期
    billing_start_time = db.Column(db.DateTime)  # 计费周期开始时间
    billing_end_time = db.Column(db.DateTime)    # 计费周期结束时间
    
    # 关联的用量记录
    usage_records = db.relationship('UsageRecord', backref='api_key', lazy=True, cascade='all, delete-orphan')
    
    def to_dict(self, show_full_key=False):
        latest_record = UsageRecord.query.filter_by(
            api_key_id=self.id
        ).order_by(UsageRecord.check_time.desc()).first()
        
        # 如果有最新记录，处理Pro API的特殊字段
        if latest_record and self.api_type == 'pro':
            usage_dict = latest_record.to_dict()
            # 对于Pro API，如果有api_key_character_count/limit，使用这些值
            if usage_dict.get('api_key_character_count') is not None:
                usage_dict['character_count'] = usage_dict['api_key_character_count']
                usage_dict['character_limit'] = usage_dict['api_key_character_limit'] or 0
                usage_dict['usage_percentage'] = (usage_dict['character_count'] / usage_dict['character_limit'] * 100) if usage_dict['character_limit'] > 0 else 0
        else:
            usage_dict = latest_record.to_dict() if latest_record else None
        
        # 判断是否过期（仅Pro API有计费周期）
        is_expired = False
        if self.api_type == 'pro' and self.billing_end_time:
            is_expired = datetime.utcnow() > self.billing_end_time
        
        return {
            'id': self.id,
            'name': self.name,
            'api_key': self.api_key if show_full_key else (self.api_key[:10] + '...' + self.api_key[-10:]),  # 可选显示完整密钥
            'api_type': self.api_type,
            'group_id': self.group_id,
            'is_active': self.is_active,
            'is_expired': is_expired,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_check': self.last_check.isoformat() if self.last_check else None,
            'billing_start_time': self.billing_start_time.isoformat() if self.billing_start_time else None,
            'billing_end_time': self.billing_end_time.isoformat() if self.billing_end_time else None,
            'latest_usage': usage_dict
        }

class UsageRecord(db.Model):
    """用量记录模型"""
    __tablename__ = 'usage_records'
    
    id = db.Column(db.Integer, primary_key=True)
    api_key_id = db.Column(db.Integer, db.ForeignKey('api_keys.id'), nullable=False)
    check_time = db.Column(db.DateTime, default=datetime.utcnow)
    
    # DeepL API返回的字段
    character_count = db.Column(db.Integer, nullable=False)  # 已使用字符数
    character_limit = db.Column(db.Integer, nullable=False)  # 字符数限制
    
    # Pro API特有字段
    api_key_character_count = db.Column(db.Integer)  # API密钥已使用字符数
    api_key_character_limit = db.Column(db.Integer)  # API密钥字符数限制
    start_time = db.Column(db.DateTime)  # 计费周期开始时间
    end_time = db.Column(db.DateTime)  # 计费周期结束时间
    
    # 查询状态
    is_success = db.Column(db.Boolean, default=True)
    error_message = db.Column(db.Text)
    
    def to_dict(self):
        return {
            'id': self.id,
            'api_key_id': self.api_key_id,
            'check_time': self.check_time.isoformat() if self.check_time else None,
            'character_count': self.character_count,
            'character_limit': self.character_limit,
            'usage_percentage': (self.character_count / self.character_limit * 100) if self.character_limit > 0 else 0,
            'api_key_character_count': self.api_key_character_count,
            'api_key_character_limit': self.api_key_character_limit,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'is_success': self.is_success,
            'error_message': self.error_message
        }
