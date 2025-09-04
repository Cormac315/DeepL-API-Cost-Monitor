from flask import Flask, render_template, request, jsonify, flash, redirect, url_for
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from datetime import datetime, timedelta
import atexit
import logging
from config import Config

# 设置日志
logging.basicConfig(level=logging.INFO)

# 创建Flask应用
app = Flask(__name__)
app.config.from_object(Config)

# 先导入db，然后初始化
from models import db
db.init_app(app)

# 初始化调度器
scheduler = BackgroundScheduler(timezone=app.config['SCHEDULER_TIMEZONE'])
scheduler.start()

# 确保应用关闭时停止调度器
atexit.register(lambda: scheduler.shutdown())

# 导入模型
from models import ApiKey, ApiGroup, UsageRecord, db

# 导入服务
from services.deepl_service import DeepLService
from services.scheduler_service import SchedulerService

# 初始化服务
deepl_service = DeepLService()
scheduler_service = SchedulerService(scheduler, deepl_service, db)

# 创建数据库表
with app.app_context():
    db.create_all()
    # 如果没有默认组，创建一个
    if not ApiGroup.query.first():
        default_group = ApiGroup(
            name='默认组',
            query_interval=app.config['DEFAULT_QUERY_INTERVAL'],
            is_active=True
        )
        db.session.add(default_group)
        db.session.commit()
    
    # 初始化所有组的调度器
    groups = ApiGroup.query.filter_by(is_active=True).all()
    for group in groups:
        scheduler_service.setup_group_scheduler(group)

@app.route('/')
def index():
    """主页 - 显示所有组和API密钥"""
    groups = ApiGroup.query.all()
    return render_template('index.html', groups=groups)

@app.route('/api/groups', methods=['GET', 'POST'])
def manage_groups():
    """API组管理"""
    if request.method == 'POST':
        data = request.get_json()
        
        group = ApiGroup(
            name=data['name'],
            query_interval=data.get('query_interval', app.config['DEFAULT_QUERY_INTERVAL']),
            is_active=data.get('is_active', True)
        )
        
        db.session.add(group)
        db.session.commit()
        
        # 重新配置调度器
        scheduler_service.setup_group_scheduler(group)
        
        return jsonify({'status': 'success', 'group_id': group.id})
    
    groups = ApiGroup.query.all()
    return jsonify([group.to_dict() for group in groups])

@app.route('/api/groups/<int:group_id>', methods=['PUT', 'DELETE'])
def update_group(group_id):
    """更新或删除API组"""
    group = ApiGroup.query.get_or_404(group_id)
    
    if request.method == 'PUT':
        data = request.get_json()
        
        group.name = data.get('name', group.name)
        old_interval = group.query_interval
        group.query_interval = data.get('query_interval', group.query_interval)
        group.is_active = data.get('is_active', group.is_active)
        
        db.session.commit()
        
        # 如果查询间隔改变，重新配置调度器
        if old_interval != group.query_interval:
            scheduler_service.update_group_scheduler(group)
        
        return jsonify({'status': 'success'})
    
    elif request.method == 'DELETE':
        # 删除组及其所有API密钥
        ApiKey.query.filter_by(group_id=group_id).delete()
        scheduler_service.remove_group_scheduler(group)
        db.session.delete(group)
        db.session.commit()
        
        return jsonify({'status': 'success'})

@app.route('/api/keys', methods=['POST'])
def add_api_key():
    """添加API密钥"""
    data = request.get_json()
    
    # 验证API密钥格式
    api_key = data['api_key'].strip()
    if not api_key:
        return jsonify({'status': 'error', 'message': 'API密钥不能为空'}), 400
    
    # 检查是否已存在
    if ApiKey.query.filter_by(api_key=api_key).first():
        return jsonify({'status': 'error', 'message': 'API密钥已存在'}), 400
    
    # 确定API类型
    api_type = 'free' if api_key.endswith(':fx') else 'pro'
    
    key = ApiKey(
        api_key=api_key,
        name=data.get('name', f'API-{api_key[-8:]}'),
        api_type=api_type,
        group_id=data['group_id'],
        is_active=True
    )
    
    db.session.add(key)
    db.session.commit()
    
    return jsonify({'status': 'success', 'key_id': key.id})

@app.route('/api/keys/<int:key_id>', methods=['PUT', 'DELETE'])
def update_api_key(key_id):
    """更新或删除API密钥"""
    key = ApiKey.query.get_or_404(key_id)
    
    if request.method == 'PUT':
        data = request.get_json()
        
        key.name = data.get('name', key.name)
        key.is_active = data.get('is_active', key.is_active)
        
        db.session.commit()
        return jsonify({'status': 'success'})
    
    elif request.method == 'DELETE':
        db.session.delete(key)
        db.session.commit()
        return jsonify({'status': 'success'})

@app.route('/api/keys/<int:key_id>/details')
def get_api_key_details(key_id):
    """获取API密钥详细信息"""
    key = ApiKey.query.get_or_404(key_id)
    return jsonify(key.to_dict(show_full_key=True))

@app.route('/api/usage/<int:key_id>')
def get_usage_history(key_id):
    """获取API密钥的用量历史"""
    key = ApiKey.query.get_or_404(key_id)
    
    # 获取时间范围参数
    period = request.args.get('period', 'hour')  # hour, day
    hours = request.args.get('hours', 24, type=int)
    start_time = datetime.utcnow() - timedelta(hours=hours)
    
    records = UsageRecord.query.filter(
        UsageRecord.api_key_id == key_id,
        UsageRecord.check_time >= start_time
    ).order_by(UsageRecord.check_time.desc()).all()
    
    # 如果是按天查看，需要聚合数据
    if period == 'day':
        # 按天聚合数据
        daily_data = {}
        for record in records:
            day = record.check_time.date().isoformat()
            if day not in daily_data:
                daily_data[day] = {
                    'date': day,
                    'max_usage': record.character_count,
                    'records': 1
                }
            else:
                daily_data[day]['max_usage'] = max(daily_data[day]['max_usage'], record.character_count)
                daily_data[day]['records'] += 1
        
        return jsonify(list(daily_data.values()))
    
    return jsonify([record.to_dict() for record in records])

@app.route('/api/usage/summary')
def get_usage_summary():
    """获取所有API密钥的用量摘要"""
    keys = ApiKey.query.filter_by(is_active=True).all()
    summary = []
    
    for key in keys:
        latest_record = UsageRecord.query.filter_by(
            api_key_id=key.id
        ).order_by(UsageRecord.check_time.desc()).first()
        
        if latest_record:
            # 对于Pro API，使用api_key_character_count/limit字段
            if key.api_type == 'pro' and latest_record.api_key_character_count is not None:
                character_count = latest_record.api_key_character_count
                character_limit = latest_record.api_key_character_limit or 0
            else:
                character_count = latest_record.character_count
                character_limit = latest_record.character_limit
            
            # 判断是否过期（仅Pro API有计费周期）
            is_expired = False
            if key.api_type == 'pro' and key.billing_end_time:
                is_expired = datetime.utcnow() > key.billing_end_time
            
            summary.append({
                'key_id': key.id,
                'key_name': key.name,
                'api_key': key.api_key,  # 添加完整密钥
                'api_type': key.api_type,
                'character_count': character_count,
                'character_limit': character_limit,
                'usage_percentage': (character_count / character_limit * 100) if character_limit > 0 else 0,
                'last_check': latest_record.check_time.isoformat(),
                'group_id': key.group_id,
                'is_expired': is_expired,
                'billing_end_time': key.billing_end_time.isoformat() if key.billing_end_time else None
            })
        else:
            # 即使没有使用记录，也显示API密钥
            summary.append({
                'key_id': key.id,
                'key_name': key.name,
                'api_key': key.api_key,  # 添加完整密钥
                'api_type': key.api_type,
                'character_count': 0,
                'character_limit': 0,
                'usage_percentage': 0,
                'last_check': None,
                'group_id': key.group_id
            })
    
    return jsonify(summary)

@app.route('/api/check-now/<int:group_id>')
def check_group_now(group_id):
    """立即检查指定组的所有API密钥"""
    group = ApiGroup.query.get_or_404(group_id)
    
    try:
        scheduler_service.check_group_usage(group.id)
        return jsonify({'status': 'success', 'message': f'已开始检查组 {group.name} 的用量'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5323)
