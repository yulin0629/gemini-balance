"""
日志路由模块
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import (
    APIRouter,
    Body,
    HTTPException,
    Path,
    Query,
    Request,
    Response,
    status,
)
from pydantic import BaseModel

from app.core.security import verify_auth_token, should_bypass_auth
from app.log.logger import get_log_routes_logger
from app.service.error_log import error_log_service

router = APIRouter(prefix="/api/logs", tags=["logs"])

logger = get_log_routes_logger()


class ErrorLogListItem(BaseModel):
    id: int
    gemini_key: Optional[str] = None
    error_type: Optional[str] = None
    error_code: Optional[int] = None
    model_name: Optional[str] = None
    request_time: Optional[datetime] = None


class ErrorLogListResponse(BaseModel):
    logs: List[ErrorLogListItem]
    total: int


@router.get("/errors", response_model=ErrorLogListResponse)
async def get_error_logs_api(
    request: Request,
    limit: int = Query(10, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    key_search: Optional[str] = Query(
        None, description="Search term for Gemini key (partial match)"
    ),
    error_search: Optional[str] = Query(
        None, description="Search term for error type or log message"
    ),
    error_code_search: Optional[str] = Query(
        None, description="Search term for error code"
    ),
    start_date: Optional[datetime] = Query(
        None, description="Start datetime for filtering"
    ),
    end_date: Optional[datetime] = Query(
        None, description="End datetime for filtering"
    ),
    sort_by: str = Query(
        "id", description="Field to sort by (e.g., 'id', 'request_time')"
    ),
    sort_order: str = Query("desc", description="Sort order ('asc' or 'desc')"),
):
    """
    获取错误日志列表 (返回错误码)，支持过滤和排序

    Args:
        request: 请求对象
        limit: 限制数量
        offset: 偏移量
        key_search: 密钥搜索
        error_search: 错误搜索 (可能搜索类型或日志内容，由DB层决定)
        error_code_search: 错误码搜索
        start_date: 开始日期
        end_date: 结束日期
        sort_by: 排序字段
        sort_order: 排序顺序

    Returns:
        ErrorLogListResponse: An object containing the list of logs (with error_code) and the total count.
    """
    # localhost 環境跳過認證
    if not should_bypass_auth(request):
        auth_token = request.cookies.get("auth_token")
        if not auth_token or not verify_auth_token(auth_token):
            logger.warning("Unauthorized access attempt to error logs list")
            raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        result = await error_log_service.process_get_error_logs(
            limit=limit,
            offset=offset,
            key_search=key_search,
            error_search=error_search,
            error_code_search=error_code_search,
            start_date=start_date,
            end_date=end_date,
            sort_by=sort_by,
            sort_order=sort_order,
        )
        logs_data = result["logs"]
        total_count = result["total"]

        validated_logs = [ErrorLogListItem(**log) for log in logs_data]
        return ErrorLogListResponse(logs=validated_logs, total=total_count)
    except Exception as e:
        logger.exception(f"Failed to get error logs list: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to get error logs list: {str(e)}"
        )


class ErrorLogDetailResponse(BaseModel):
    id: int
    gemini_key: Optional[str] = None
    error_type: Optional[str] = None
    error_log: Optional[str] = None
    request_msg: Optional[str] = None
    model_name: Optional[str] = None
    request_time: Optional[datetime] = None


@router.get("/errors/{log_id}/details", response_model=ErrorLogDetailResponse)
async def get_error_log_detail_api(request: Request, log_id: int = Path(..., ge=1)):
    """
    根据日志 ID 获取错误日志的详细信息 (包括 error_log 和 request_msg)
    """
    # localhost 環境跳過認證
    if not should_bypass_auth(request):
        auth_token = request.cookies.get("auth_token")
        if not auth_token or not verify_auth_token(auth_token):
            logger.warning(
                f"Unauthorized access attempt to error log details for ID: {log_id}"
            )
            raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        log_details = await error_log_service.process_get_error_log_details(
            log_id=log_id
        )
        if not log_details:
            raise HTTPException(status_code=404, detail="Error log not found")

        return ErrorLogDetailResponse(**log_details)
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.exception(f"Failed to get error log details for ID {log_id}: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to get error log details: {str(e)}"
        )


@router.delete("/errors", status_code=status.HTTP_204_NO_CONTENT)
async def delete_error_logs_bulk_api(
    request: Request, payload: Dict[str, List[int]] = Body(...)
):
    """
    批量删除错误日志 (异步)
    """
    # localhost 環境跳過認證
    if not should_bypass_auth(request):
        auth_token = request.cookies.get("auth_token")
        if not auth_token or not verify_auth_token(auth_token):
            logger.warning("Unauthorized access attempt to bulk delete error logs")
            raise HTTPException(status_code=401, detail="Not authenticated")

    log_ids = payload.get("ids")
    if not log_ids:
        raise HTTPException(status_code=400, detail="No log IDs provided for deletion.")

    try:
        deleted_count = await error_log_service.process_delete_error_logs_by_ids(
            log_ids
        )
        # 注意：异步函数返回的是尝试删除的数量，可能不是精确值
        logger.info(
            f"Attempted bulk deletion for {deleted_count} error logs with IDs: {log_ids}"
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except Exception as e:
        logger.exception(f"Error bulk deleting error logs with IDs {log_ids}: {str(e)}")
        raise HTTPException(
            status_code=500, detail="Internal server error during bulk deletion"
        )


@router.delete("/errors/all", status_code=status.HTTP_204_NO_CONTENT)
async def delete_all_error_logs_api(request: Request):
    """
    删除所有错误日志 (异步)
    """
    auth_token = request.cookies.get("auth_token")
    if not auth_token or not verify_auth_token(auth_token):
        logger.warning("Unauthorized access attempt to delete all error logs")
        raise HTTPException(status_code=401, detail="Not authenticated")
 
    try:
        deleted_count = await error_log_service.process_delete_all_error_logs()
        logger.info(f"Successfully deleted all {deleted_count} error logs.")
        # No body needed for 204 response
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except Exception as e:
        logger.exception(f"Error deleting all error logs: {str(e)}")
        raise HTTPException(
            status_code=500, detail="Internal server error during deletion of all logs"
        )
 
 
@router.delete("/errors/{log_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_error_log_api(request: Request, log_id: int = Path(..., ge=1)):
    """
    删除单个错误日志 (异步)
    """
    # localhost 環境跳過認證
    if not should_bypass_auth(request):
        auth_token = request.cookies.get("auth_token")
        if not auth_token or not verify_auth_token(auth_token):
            logger.warning(f"Unauthorized access attempt to delete error log ID: {log_id}")
            raise HTTPException(status_code=401, detail="Not authenticated")
 
    try:
        success = await error_log_service.process_delete_error_log_by_id(log_id)
        if not success:
            # 服务层现在在未找到时返回 False，我们在这里转换为 404
            raise HTTPException(
                status_code=404, detail=f"Error log with ID {log_id} not found"
            )
        logger.info(f"Successfully deleted error log with ID: {log_id}")
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.exception(f"Error deleting error log with ID {log_id}: {str(e)}")
        raise HTTPException(
            status_code=500, detail="Internal server error during deletion"
        )


# ===== Request Log Routes =====

class RequestLogListItem(BaseModel):
    id: int
    request_time: Optional[datetime] = None
    model_name: Optional[str] = None
    api_key: Optional[str] = None
    is_success: bool
    status_code: Optional[int] = None
    latency_ms: Optional[int] = None


class RequestLogListResponse(BaseModel):
    logs: List[RequestLogListItem]
    total: int


@router.get("/requests", response_model=RequestLogListResponse)
async def get_request_logs_api(
    request: Request,
    limit: int = Query(10, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    model_search: Optional[str] = Query(
        None, description="Search term for model name (partial match)"
    ),
    key_search: Optional[str] = Query(
        None, description="Search term for API key (partial match)"
    ),
    success_filter: Optional[bool] = Query(
        None, description="Filter by success status (true/false/null for all)"
    ),
    start_date: Optional[datetime] = Query(
        None, description="Start datetime for filtering"
    ),
    end_date: Optional[datetime] = Query(
        None, description="End datetime for filtering"
    ),
    sort_by: str = Query(
        "id", description="Field to sort by (e.g., 'id', 'request_time', 'latency_ms')"
    ),
    sort_order: str = Query("desc", description="Sort order ('asc' or 'desc')"),
):
    """
    获取请求日志列表，支持过滤和排序

    Args:
        request: 请求对象
        limit: 限制数量
        offset: 偏移量
        model_search: 模型名称搜索
        key_search: API密钥搜索
        success_filter: 成功状态过滤
        start_date: 开始日期
        end_date: 结束日期
        sort_by: 排序字段
        sort_order: 排序顺序

    Returns:
        RequestLogListResponse: 包含请求日志列表和总数的响应对象
    """
    # localhost 環境跳過認證
    if not should_bypass_auth(request):
        auth_token = request.cookies.get("auth_token")
        if not auth_token or not verify_auth_token(auth_token):
            logger.warning("Unauthorized access attempt to request logs list")
            raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        result = await error_log_service.process_get_request_logs(
            limit=limit,
            offset=offset,
            model_search=model_search,
            key_search=key_search,
            success_filter=success_filter,
            start_date=start_date,
            end_date=end_date,
            sort_by=sort_by,
            sort_order=sort_order,
        )
        logs_data = result["logs"]
        total_count = result["total"]

        validated_logs = [RequestLogListItem(**log) for log in logs_data]
        return RequestLogListResponse(logs=validated_logs, total=total_count)
    except Exception as e:
        logger.exception(f"Failed to get request logs list: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to get request logs list: {str(e)}"
        )


class RequestLogDetailResponse(BaseModel):
    id: int
    request_time: Optional[datetime] = None
    model_name: Optional[str] = None
    api_key: Optional[str] = None
    is_success: bool
    status_code: Optional[int] = None
    latency_ms: Optional[int] = None
    request_body: Optional[Dict[str, Any]] = None
    response_summary: Optional[str] = None
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    error_message: Optional[str] = None


@router.get("/requests/{log_id}/details", response_model=RequestLogDetailResponse)
async def get_request_log_detail_api(request: Request, log_id: int = Path(..., ge=1)):
    """
    根据日志 ID 获取请求日志的详细信息
    """
    # localhost 環境跳過認證
    if not should_bypass_auth(request):
        auth_token = request.cookies.get("auth_token")
        if not auth_token or not verify_auth_token(auth_token):
            logger.warning(
                f"Unauthorized access attempt to request log details for ID: {log_id}"
            )
            raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        log_details = await error_log_service.process_get_request_log_details(
            log_id=log_id
        )
        if not log_details:
            raise HTTPException(status_code=404, detail="Request log not found")

        return RequestLogDetailResponse(**log_details)
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.exception(f"Failed to get request log details for ID {log_id}: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to get request log details: {str(e)}"
        )


@router.delete("/requests", status_code=status.HTTP_204_NO_CONTENT)
async def delete_request_logs_bulk_api(
    request: Request, payload: Dict[str, List[int]] = Body(...)
):
    """
    批量删除请求日志 (异步)
    """
    # localhost 環境跳過認證
    if not should_bypass_auth(request):
        auth_token = request.cookies.get("auth_token")
        if not auth_token or not verify_auth_token(auth_token):
            logger.warning("Unauthorized access attempt to bulk delete request logs")
            raise HTTPException(status_code=401, detail="Not authenticated")

    log_ids = payload.get("ids")
    if not log_ids:
        raise HTTPException(status_code=400, detail="No log IDs provided for deletion.")

    try:
        deleted_count = await error_log_service.process_delete_request_logs_by_ids(
            log_ids
        )
        logger.info(
            f"Attempted bulk deletion for {deleted_count} request logs with IDs: {log_ids}"
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except Exception as e:
        logger.exception(f"Error bulk deleting request logs with IDs {log_ids}: {str(e)}")
        raise HTTPException(
            status_code=500, detail="Internal server error during bulk deletion"
        )


@router.delete("/requests/all", status_code=status.HTTP_204_NO_CONTENT)
async def delete_all_request_logs_api(request: Request):
    """
    删除所有请求日志 (异步)
    """
    # localhost 環境跳過認證
    if not should_bypass_auth(request):
        auth_token = request.cookies.get("auth_token")
        if not auth_token or not verify_auth_token(auth_token):
            logger.warning("Unauthorized access attempt to delete all request logs")
            raise HTTPException(status_code=401, detail="Not authenticated")
 
    try:
        deleted_count = await error_log_service.process_delete_all_request_logs()
        logger.info(f"Successfully deleted all {deleted_count} request logs.")
        # No body needed for 204 response
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except Exception as e:
        logger.exception(f"Error deleting all request logs: {str(e)}")
        raise HTTPException(
            status_code=500, detail="Internal server error during deletion of all request logs"
        )


@router.delete("/requests/{log_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_request_log_api(request: Request, log_id: int = Path(..., ge=1)):
    """
    删除单个请求日志 (异步)
    """
    # localhost 環境跳過認證
    if not should_bypass_auth(request):
        auth_token = request.cookies.get("auth_token")
        if not auth_token or not verify_auth_token(auth_token):
            logger.warning(f"Unauthorized access attempt to delete request log ID: {log_id}")
            raise HTTPException(status_code=401, detail="Not authenticated")
 
    try:
        success = await error_log_service.process_delete_request_log_by_id(log_id)
        if not success:
            raise HTTPException(
                status_code=404, detail=f"Request log with ID {log_id} not found"
            )
        logger.info(f"Successfully deleted request log with ID: {log_id}")
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.exception(f"Error deleting request log with ID {log_id}: {str(e)}")
        raise HTTPException(
            status_code=500, detail="Internal server error during deletion"
        )
