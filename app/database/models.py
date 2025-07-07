"""
数据库模型模块
"""
import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, JSON, Boolean

from app.database.connection import Base


class Settings(Base):
    """
    设置表，对应.env中的配置项
    """
    __tablename__ = "t_settings"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(100), nullable=False, unique=True, comment="配置项键名")
    value = Column(Text, nullable=True, comment="配置项值")
    description = Column(String(255), nullable=True, comment="配置项描述")
    created_at = Column(DateTime, default=datetime.datetime.now, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.datetime.now, onupdate=datetime.datetime.now, comment="更新时间")
    
    def __repr__(self):
        return f"<Settings(key='{self.key}', value='{self.value}')>"


class ErrorLog(Base):
    """
    错误日志表
    """
    __tablename__ = "t_error_logs"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    gemini_key = Column(String(100), nullable=True, comment="Gemini API密钥")
    model_name = Column(String(100), nullable=True, comment="模型名称")
    error_type = Column(String(50), nullable=True, comment="错误类型")
    error_log = Column(Text, nullable=True, comment="错误日志")
    error_code = Column(Integer, nullable=True, comment="错误代码")
    request_msg = Column(JSON, nullable=True, comment="请求消息")
    request_time = Column(DateTime, default=datetime.datetime.now, comment="请求时间")
    
    def __repr__(self):
        return f"<ErrorLog(id='{self.id}', gemini_key='{self.gemini_key}')>"


class RequestLog(Base):
    """
    API 请求日志表
    """

    __tablename__ = "t_request_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    request_time = Column(DateTime, default=datetime.datetime.now, comment="请求时间")
    model_name = Column(String(100), nullable=True, comment="模型名称")
    api_key = Column(String(100), nullable=True, comment="使用的API密钥")
    is_success = Column(Boolean, nullable=False, comment="请求是否成功")
    status_code = Column(Integer, nullable=True, comment="API响应状态码")
    latency_ms = Column(Integer, nullable=True, comment="请求耗时(毫秒)")
    # 新增詳細資料欄位
    request_body = Column(JSON, nullable=True, comment="请求内容")
    response_summary = Column(Text, nullable=True, comment="响应摘要")
    prompt_tokens = Column(Integer, nullable=True, comment="输入Token数")
    completion_tokens = Column(Integer, nullable=True, comment="输出Token数")
    total_tokens = Column(Integer, nullable=True, comment="总Token数")
    error_message = Column(Text, nullable=True, comment="错误信息")

    def __repr__(self):
        return f"<RequestLog(id='{self.id}', key='{self.api_key[:4]}...', success='{self.is_success}')>"
