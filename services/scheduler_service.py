import threading
import time
import logging
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger(__name__)

class SchedulerService:
    """调度器服务类 - 管理不同组的定时任务"""
    
    def __init__(self, scheduler, deepl_service, db):
        self.scheduler = scheduler
        self.deepl_service = deepl_service
        self.db = db
        self.group_jobs = {}  # 存储各组的任务ID
        self.max_workers = 10  # 最大并发线程数
        
        # 启动时初始化所有组的调度器
        self._initialize_all_groups()
    
    def _initialize_all_groups(self):
        """初始化所有活跃组的调度器"""
        # 延迟初始化，避免在应用上下文外运行
        pass
    
    def setup_group_scheduler(self, group):
        """为指定组设置调度器"""
        job_id = f"group_{group.id}_usage_check"
        
        # 如果已存在任务，先移除
        if job_id in self.group_jobs:
            try:
                self.scheduler.remove_job(job_id)
            except:
                pass
        
        # 添加新的定时任务
        if group.is_active and group.query_interval > 0:
            self.scheduler.add_job(
                func=self.check_group_usage,
                trigger=IntervalTrigger(seconds=group.query_interval),
                id=job_id,
                args=[group.id],
                max_instances=1,  # 防止任务重叠
                replace_existing=True
            )
            
            self.group_jobs[job_id] = group.id
            logger.info(f"为组 '{group.name}' 设置了 {group.query_interval} 秒间隔的调度器")
    
    def update_group_scheduler(self, group):
        """更新组的调度器设置"""
        self.setup_group_scheduler(group)
    
    def remove_group_scheduler(self, group):
        """移除组的调度器"""
        job_id = f"group_{group.id}_usage_check"
        
        try:
            self.scheduler.remove_job(job_id)
            if job_id in self.group_jobs:
                del self.group_jobs[job_id]
            logger.info(f"移除了组 '{group.name}' 的调度器")
        except Exception as e:
            logger.error(f"移除组调度器失败: {e}")
    
    def check_group_usage(self, group_id):
        """
        检查指定组的所有API密钥用量
        组内的密钥按顺序查询，不同组之间并发执行
        """
        from models import ApiGroup, ApiKey, UsageRecord
        
        try:
            # 获取组信息
            group = ApiGroup.query.get(group_id)
            if not group or not group.is_active:
                logger.warning(f"组 {group_id} 不存在或已禁用")
                return
            
            # 获取组内所有活跃的API密钥
            api_keys = ApiKey.query.filter_by(
                group_id=group_id, 
                is_active=True
            ).all()
            
            if not api_keys:
                logger.info(f"组 '{group.name}' 没有活跃的API密钥")
                return
            
            logger.info(f"开始检查组 '{group.name}' 的 {len(api_keys)} 个API密钥")
            
            # 按顺序检查组内的每个API密钥（符合您的需求）
            success_count = 0
            for api_key in api_keys:
                try:
                    # 查询API用量
                    usage_info = self.deepl_service.get_usage(api_key.api_key)
                    
                    # 创建用量记录
                    record = UsageRecord(
                        api_key_id=api_key.id,
                        check_time=usage_info['check_time'],
                        character_count=usage_info['character_count'],
                        character_limit=usage_info['character_limit'],
                        is_success=usage_info['is_success'],
                        error_message=usage_info.get('error_message')
                    )
                    
                    # Pro API特有字段
                    if usage_info.get('api_key_character_count') is not None:
                        record.api_key_character_count = usage_info['api_key_character_count']
                    if usage_info.get('api_key_character_limit') is not None:
                        record.api_key_character_limit = usage_info['api_key_character_limit']
                    if usage_info.get('start_time'):
                        record.start_time = usage_info['start_time']
                    if usage_info.get('end_time'):
                        record.end_time = usage_info['end_time']
                    
                    # 更新API密钥的最后检查时间和计费周期（仅Pro API）
                    api_key.last_check = usage_info['check_time']
                    if api_key.api_type == 'pro' and usage_info.get('start_time'):
                        api_key.billing_start_time = usage_info['start_time']
                        api_key.billing_end_time = usage_info['end_time']
                    
                    self.db.session.add(record)
                    
                    if usage_info['is_success']:
                        success_count += 1
                        logger.info(f"API密钥 '{api_key.name}' 用量: {usage_info['character_count']}/{usage_info['character_limit']}")
                    else:
                        logger.error(f"API密钥 '{api_key.name}' 查询失败: {usage_info.get('error_message')}")
                    
                    # 在每次查询之间添加小延迟，避免过于频繁的请求
                    time.sleep(0.5)
                    
                except Exception as e:
                    logger.error(f"检查API密钥 '{api_key.name}' 时发生错误: {e}")
                    
                    # 创建错误记录
                    error_record = UsageRecord(
                        api_key_id=api_key.id,
                        check_time=datetime.utcnow(),
                        character_count=0,
                        character_limit=0,
                        is_success=False,
                        error_message=f"检查过程中发生错误: {str(e)}"
                    )
                    self.db.session.add(error_record)
            
            # 提交所有更改
            self.db.session.commit()
            
            logger.info(f"组 '{group.name}' 检查完成: {success_count}/{len(api_keys)} 成功")
            
        except Exception as e:
            logger.error(f"检查组 {group_id} 用量时发生严重错误: {e}")
            self.db.session.rollback()
    
    def check_all_groups_now(self):
        """立即检查所有活跃组的用量（并发执行不同组）"""
        from models import ApiGroup
        
        try:
            groups = ApiGroup.query.filter_by(is_active=True).all()
            
            if not groups:
                logger.info("没有活跃的组需要检查")
                return
            
            logger.info(f"开始并发检查 {len(groups)} 个组的用量")
            
            # 使用线程池并发执行不同组的检查
            with ThreadPoolExecutor(max_workers=min(len(groups), self.max_workers)) as executor:
                # 提交所有组的检查任务
                future_to_group = {
                    executor.submit(self.check_group_usage, group.id): group 
                    for group in groups
                }
                
                # 等待所有任务完成
                completed = 0
                for future in as_completed(future_to_group):
                    group = future_to_group[future]
                    try:
                        future.result()  # 获取结果（如果有异常会抛出）
                        completed += 1
                        logger.info(f"组 '{group.name}' 检查完成 ({completed}/{len(groups)})")
                    except Exception as e:
                        logger.error(f"组 '{group.name}' 检查失败: {e}")
            
            logger.info("所有组的用量检查完成")
            
        except Exception as e:
            logger.error(f"并发检查所有组时发生错误: {e}")
    
    def get_scheduler_status(self):
        """获取调度器状态信息"""
        from models import ApiGroup
        
        status = {
            'running_jobs': len(self.group_jobs),
            'total_jobs': len(self.scheduler.get_jobs()),
            'groups': []
        }
        
        for job_id, group_id in self.group_jobs.items():
            group = ApiGroup.query.get(group_id)
            if group:
                job = self.scheduler.get_job(job_id)
                status['groups'].append({
                    'group_id': group_id,
                    'group_name': group.name,
                    'interval': group.query_interval,
                    'next_run': job.next_run_time.isoformat() if job and job.next_run_time else None,
                    'is_active': group.is_active
                })
        
        return status
