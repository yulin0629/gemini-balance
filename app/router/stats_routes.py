from fastapi import APIRouter, Depends, HTTPException, Request
from starlette import status
from app.core.security import verify_auth_token, should_bypass_auth
from app.service.stats.stats_service import StatsService
from app.service.key.key_manager import get_key_manager_instance
from app.log.logger import get_stats_logger

logger = get_stats_logger()


async def verify_token(request: Request):
    # localhost 環境跳過認證
    if should_bypass_auth(request):
        return
    
    auth_token = request.cookies.get("auth_token")
    if not auth_token or not verify_auth_token(auth_token):
        logger.warning("Unauthorized access attempt to scheduler API")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

router = APIRouter(
    prefix="/api",
    tags=["stats"],
    dependencies=[Depends(verify_token)]
)

stats_service = StatsService()

@router.get("/key-usage-details/{key}",
            summary="获取指定密钥最近24小时的模型调用次数",
            description="根据提供的 API 密钥，返回过去24小时内每个模型被调用的次数统计。")
async def get_key_usage_details(key: str):
    """
    Retrieves the model usage count for a specific API key within the last 24 hours.

    Args:
        key: The API key to get usage details for.

    Returns:
        A dictionary with model names as keys and their call counts as values.
        Example: {"gemini-pro": 10, "gemini-1.5-pro-latest": 5}

    Raises:
        HTTPException: If an error occurs during data retrieval.
    """
    try:
        usage_details = await stats_service.get_key_usage_details_last_24h(key)
        if usage_details is None:
            return {}
        return usage_details
    except Exception as e:
        logger.error(f"Error fetching key usage details for key {key[:4]}...: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取密钥使用详情时出错: {e}"
        )


@router.get("/rpm-status",
            summary="获取当前 RPM 使用状态",
            description="返回所有 API key 的当前 RPM 使用情况，包括使用率、限制和失败次数。")
async def get_rpm_status(model: str = None):
    """
    Retrieves the current RPM (Requests Per Minute) status for all API keys.

    Args:
        model: Optional model name to get specific RPM limits for that model.

    Returns:
        A dictionary containing RPM status for all API keys and vertex keys.
        Example: {
            "api_keys": {
                "key1": {
                    "current_rpm": 5,
                    "rpm_limit": 10,
                    "usage_percentage": 50.0,
                    "is_current": true,
                    "failure_count": 0
                }
            },
            "vertex_keys": {...},
            "current_model": "gemini-2.5-flash",
            "rpm_window_seconds": 60,
            "rpm_prefer_cache": true
        }

    Raises:
        HTTPException: If an error occurs during status retrieval.
    """
    try:
        key_manager = await get_key_manager_instance()
        rpm_status = await key_manager.get_rpm_status(model)
        return rpm_status
    except Exception as e:
        logger.error(f"Error fetching RPM status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取 RPM 状态时出错: {e}"
        )