import asyncio
# 移除 cycle import，不再使用
from typing import Dict, Union, List, Deque
from collections import deque, defaultdict
import time
import json

from app.config.config import settings
from app.log.logger import get_key_manager_logger

logger = get_key_manager_logger()


class KeyManager:
    def __init__(self, api_keys: list, vertex_api_keys: list):
        self.api_keys = api_keys
        self.vertex_api_keys = vertex_api_keys
        # 使用索引而不是 cycle 迭代器
        self.current_key_index = 0
        self.current_vertex_key_index = 0
        self.key_index_lock = asyncio.Lock()
        self.vertex_key_index_lock = asyncio.Lock()
        self.failure_count_lock = asyncio.Lock()
        self.vertex_failure_count_lock = asyncio.Lock()
        self.key_failure_counts: Dict[str, int] = {key: 0 for key in api_keys}
        self.vertex_key_failure_counts: Dict[str, int] = {
            key: 0 for key in vertex_api_keys
        }
        self.MAX_FAILURES = settings.MAX_FAILURES
        self.paid_key = settings.PAID_KEY
        
        # RPM tracking
        self.rpm_lock = asyncio.Lock()
        self.vertex_rpm_lock = asyncio.Lock()
        # Store timestamps of requests for each key and model combination
        # Structure: {key: {model: deque([timestamps])}}
        self.key_request_times: Dict[str, Dict[str, Deque[float]]] = {
            key: defaultdict(deque) for key in api_keys
        }
        self.vertex_key_request_times: Dict[str, Dict[str, Deque[float]]] = {
            key: defaultdict(deque) for key in vertex_api_keys
        }
        # Current key being used (for caching)
        self.current_key: Union[str, None] = None
        self.current_vertex_key: Union[str, None] = None
        self.last_key_switch_time: float = 0.0
        self.last_vertex_key_switch_time: float = 0.0
        # Track current model for RPM-aware failure handling
        self.current_model: Union[str, None] = None
        
        # Load RPM settings
        self.rpm_limits = settings.RPM_LIMITS
        self.rpm_window_seconds = settings.RPM_WINDOW_SECONDS
        self.rpm_prefer_cache = settings.RPM_PREFER_CACHE
        
        logger.info(f"[RPM] KeyManager initialized with RPM support")
        logger.info(f"[RPM] RPM limits: {self.rpm_limits}")
        logger.info(f"[RPM] RPM window: {self.rpm_window_seconds}s, Prefer cache: {self.rpm_prefer_cache}")

    async def get_paid_key(self) -> str:
        return self.paid_key
    
    def _clean_old_requests(self, timestamps: Deque[float], current_time: float) -> None:
        """清理超過時間窗口的舊請求記錄"""
        cutoff_time = current_time - self.rpm_window_seconds
        while timestamps and timestamps[0] < cutoff_time:
            timestamps.popleft()
    
    def _get_rpm_count(self, key: str, model: str, is_vertex: bool = False) -> int:
        """獲取指定 key 和模型的當前 RPM 計數"""
        current_time = time.time()
        key_dict = (
            self.vertex_key_request_times[key] if is_vertex 
            else self.key_request_times[key]
        )
        timestamps = key_dict[model]
        before_clean = len(timestamps)
        self._clean_old_requests(timestamps, current_time)
        after_clean = len(timestamps)
        if before_clean != after_clean:
            logger.debug(f"[RPM DEBUG] Cleaned old requests for key {key} model {model}: {before_clean} -> {after_clean}")
        return len(timestamps)
    
    async def _record_request(self, key: str, model: str, is_vertex: bool = False) -> None:
        """記錄一個新的請求"""
        current_time = time.time()
        if is_vertex:
            async with self.vertex_rpm_lock:
                self.vertex_key_request_times[key][model].append(current_time)
                logger.debug(f"[RPM DEBUG] Recorded request for vertex key {key} model {model} at {current_time}")
        else:
            async with self.rpm_lock:
                self.key_request_times[key][model].append(current_time)
                logger.debug(f"[RPM DEBUG] Recorded request for key {key} model {model} at {current_time}, total requests in window: {len(self.key_request_times[key][model])}")
    
    def _get_rpm_limit_for_model(self, model: str) -> int:
        """根據模型名稱獲取 RPM 限制"""
        # 嘗試直接匹配
        if model in self.rpm_limits:
            return self.rpm_limits[model]
        
        # 嘗試模糊匹配
        model_lower = model.lower()
        for key, value in self.rpm_limits.items():
            key_parts = key.lower().split('-')
            # 檢查是否包含主要型號標識（如 pro、flash、flash-lite）
            if 'lite' in key_parts and 'lite' in model_lower:
                return value
            elif 'flash' in key_parts and 'flash' in model_lower and 'lite' not in model_lower:
                return value
            elif 'pro' in key_parts and 'pro' in model_lower:
                return value
        
        # 默認使用最保守的限制
        return min(self.rpm_limits.values()) if self.rpm_limits else 10
    
    async def is_key_within_rpm_limit(self, key: str, model: str, is_vertex: bool = False) -> bool:
        """檢查 key 是否在 RPM 限制內"""
        rpm_limit = self._get_rpm_limit_for_model(model)
        current_rpm = self._get_rpm_count(key, model, is_vertex)
        return current_rpm < rpm_limit

    async def get_next_key(self) -> str:
        """获取下一个API key"""
        async with self.key_index_lock:
            if not self.api_keys:
                return ""
            # 獲取當前索引的 key
            key = self.api_keys[self.current_key_index]
            # 推進索引到下一個
            self.current_key_index = (self.current_key_index + 1) % len(self.api_keys)
            return key

    async def get_next_vertex_key(self) -> str:
        """获取下一个 Vertex Express API key"""
        async with self.vertex_key_index_lock:
            if not self.vertex_api_keys:
                return ""
            # 獲取當前索引的 key
            key = self.vertex_api_keys[self.current_vertex_key_index]
            # 推進索引到下一個
            self.current_vertex_key_index = (self.current_vertex_key_index + 1) % len(self.vertex_api_keys)
            return key

    async def is_key_valid(self, key: str) -> bool:
        """检查key是否有效"""
        async with self.failure_count_lock:
            return self.key_failure_counts[key] < self.MAX_FAILURES

    async def is_vertex_key_valid(self, key: str) -> bool:
        """检查 Vertex key 是否有效"""
        async with self.vertex_failure_count_lock:
            return self.vertex_key_failure_counts[key] < self.MAX_FAILURES

    async def reset_failure_counts(self):
        """重置所有key的失败计数"""
        async with self.failure_count_lock:
            for key in self.key_failure_counts:
                self.key_failure_counts[key] = 0

    async def reset_vertex_failure_counts(self):
        """重置所有 Vertex key 的失败计数"""
        async with self.vertex_failure_count_lock:
            for key in self.vertex_key_failure_counts:
                self.vertex_key_failure_counts[key] = 0

    async def reset_key_failure_count(self, key: str) -> bool:
        """重置指定key的失败计数"""
        async with self.failure_count_lock:
            if key in self.key_failure_counts:
                self.key_failure_counts[key] = 0
                logger.info(f"Reset failure count for key: {key}")
                return True
            logger.warning(
                f"Attempt to reset failure count for non-existent key: {key}"
            )
            return False

    async def reset_vertex_key_failure_count(self, key: str) -> bool:
        """重置指定 Vertex key 的失败计数"""
        async with self.vertex_failure_count_lock:
            if key in self.vertex_key_failure_counts:
                self.vertex_key_failure_counts[key] = 0
                logger.info(f"Reset failure count for Vertex key: {key}")
                return True
            logger.warning(
                f"Attempt to reset failure count for non-existent Vertex key: {key}"
            )
            return False

    async def get_next_working_key(self) -> str:
        """获取下一可用的API key（舊版方法，保持向後兼容）"""
        initial_key = await self.get_next_key()
        current_key = initial_key

        while True:
            if await self.is_key_valid(current_key):
                return current_key

            current_key = await self.get_next_key()
            if current_key == initial_key:
                return current_key
    
    async def get_next_working_key_with_rpm(self, model: str) -> str:
        """獲取下一個可用的 API key，考慮 RPM 限制"""
        async with self.key_index_lock:
            # 記錄當前模型
            self.current_model = model
            rpm_limit = self._get_rpm_limit_for_model(model)
            
            logger.info(f"[RPM DEBUG] ========== START get_next_working_key_with_rpm ==========")
            logger.info(f"[RPM DEBUG] Model: {model}, RPM limit: {rpm_limit}")
            logger.info(f"[RPM DEBUG] rpm_prefer_cache: {self.rpm_prefer_cache}")
            logger.info(f"[RPM DEBUG] current_key: {self.current_key}")
            logger.info(f"[RPM DEBUG] current_key_index: {self.current_key_index}")
            logger.info(f"[RPM DEBUG] Total keys: {len(self.api_keys)}")
            
            # 如果啟用了緩存優先，並且當前 key 仍在 RPM 限制內，繼續使用它
            if self.rpm_prefer_cache and self.current_key:
                current_rpm = self._get_rpm_count(self.current_key, model)
                is_valid = await self.is_key_valid(self.current_key)
                is_within_limit = await self.is_key_within_rpm_limit(self.current_key, model)
                
                logger.info(f"[RPM DEBUG] Checking current key {self.current_key}:")
                logger.info(f"[RPM DEBUG]   - Current RPM for {model}: {current_rpm}/{rpm_limit}")
                logger.info(f"[RPM DEBUG]   - Is valid: {is_valid}")
                logger.info(f"[RPM DEBUG]   - Is within limit: {is_within_limit}")
                
                if is_valid and is_within_limit:
                    await self._record_request(self.current_key, model)
                    logger.info(f"[RPM DEBUG] ✓ REUSING cached key {self.current_key}")
                    logger.info(f"[RPM DEBUG] ========== END (reused key) ==========")
                    return self.current_key
                else:
                    logger.info(f"[RPM DEBUG] ✗ Current key cannot be reused, finding new key")
            else:
                logger.info(f"[RPM DEBUG] Not checking current key (prefer_cache={self.rpm_prefer_cache}, current_key={self.current_key})")
            
            # 需要找一個新的 key，但不要立即推進索引
            if not self.api_keys:
                logger.error("[RPM DEBUG] No API keys available!")
                return ""
            
            # 從當前索引開始檢查所有 key
            start_index = self.current_key_index
            checked_count = 0
            
            logger.info(f"[RPM DEBUG] Starting key search from index {start_index}")
            
            while checked_count < len(self.api_keys):
                # 獲取當前索引的 key（不推進索引）
                check_index = (start_index + checked_count) % len(self.api_keys)
                current_key = self.api_keys[check_index]
                
                # 檢查這個 key 是否可用
                key_rpm = self._get_rpm_count(current_key, model)
                is_valid = await self.is_key_valid(current_key)
                is_within_limit = await self.is_key_within_rpm_limit(current_key, model)
                
                logger.info(f"[RPM DEBUG] Checking key {current_key} at index {check_index}:")
                logger.info(f"[RPM DEBUG]   - Current RPM for {model}: {key_rpm}/{rpm_limit}")
                logger.info(f"[RPM DEBUG]   - Is valid: {is_valid}")
                logger.info(f"[RPM DEBUG]   - Is within limit: {is_within_limit}")
                
                if is_valid and is_within_limit:
                    # 找到可用的 key，更新索引
                    self.current_key_index = (check_index + 1) % len(self.api_keys)
                    self.current_key = current_key
                    await self._record_request(current_key, model)
                    logger.info(f"[RPM DEBUG] ✓ SELECTED new key {current_key}")
                    logger.info(f"[RPM DEBUG] Updated current_key_index to {self.current_key_index}")
                    logger.info(f"[RPM DEBUG] ========== END (new key) ==========")
                    return current_key
                
                checked_count += 1
            
            logger.info(f"[RPM DEBUG] All keys checked, none within limits")
            
            # 所有 key 都檢查過了，選擇 RPM 使用率最低的
            best_key = await self._get_least_used_key(model)
            if best_key:
                # 找到最佳 key 的索引
                best_index = self.api_keys.index(best_key)
                self.current_key_index = (best_index + 1) % len(self.api_keys)
                self.current_key = best_key
                await self._record_request(best_key, model)
                logger.info(f"[RPM DEBUG] Using least used key {best_key}")
                logger.info(f"[RPM DEBUG] ========== END (least used) ==========")
                return best_key
            
            # 沒有可用的 key，使用當前索引的
            current_key = self.api_keys[self.current_key_index]
            self.current_key_index = (self.current_key_index + 1) % len(self.api_keys)
            self.current_key = current_key
            await self._record_request(current_key, model)
            logger.warning(f"[RPM DEBUG] No keys within RPM limit, using {current_key} anyway")
            logger.info(f"[RPM DEBUG] ========== END (forced) ==========")
            return current_key
    
    async def _get_least_used_key(self, model: str) -> Union[str, None]:
        """獲取 RPM 使用率最低的有效 key"""
        rpm_limit = self._get_rpm_limit_for_model(model)
        best_key = None
        lowest_usage = float('inf')
        
        for key in self.api_keys:
            if await self.is_key_valid(key):
                current_rpm = self._get_rpm_count(key, model)
                usage_ratio = current_rpm / rpm_limit if rpm_limit > 0 else 0
                if usage_ratio < lowest_usage:
                    lowest_usage = usage_ratio
                    best_key = key
        
        return best_key

    async def get_next_working_vertex_key(self) -> str:
        """获取下一可用的 Vertex Express API key"""
        initial_key = await self.get_next_vertex_key()
        current_key = initial_key

        while True:
            if await self.is_vertex_key_valid(current_key):
                return current_key

            current_key = await self.get_next_vertex_key()
            if current_key == initial_key:
                return current_key
    
    async def get_next_working_vertex_key_with_rpm(self, model: str) -> str:
        """獲取下一個可用的 Vertex API key，考慮 RPM 限制"""
        async with self.vertex_key_index_lock:
            # 如果啟用了緩存優先，並且當前 key 仍在 RPM 限制內，繼續使用它
            if self.rpm_prefer_cache and self.current_vertex_key:
                if (await self.is_vertex_key_valid(self.current_vertex_key) and 
                    await self.is_key_within_rpm_limit(self.current_vertex_key, model, is_vertex=True)):
                    await self._record_request(self.current_vertex_key, model, is_vertex=True)
                    logger.debug(f"Reusing cached vertex key {self.current_vertex_key} for model {model}")
                    return self.current_vertex_key
            
            # 需要找一個新的 key
            initial_key = await self.get_next_vertex_key()
            current_key = initial_key
            checked_keys = set()
            
            while True:
                # 避免無限循環
                if current_key in checked_keys:
                    # 所有 key 都檢查過了，選擇 RPM 使用率最低的
                    best_key = await self._get_least_used_vertex_key(model)
                    if best_key:
                        self.current_vertex_key = best_key
                        await self._record_request(best_key, model, is_vertex=True)
                        logger.info(f"All vertex keys at capacity, using least used key {best_key} for model {model}")
                        return best_key
                    else:
                        # 沒有可用的 key，返回當前的
                        self.current_vertex_key = current_key
                        await self._record_request(current_key, model, is_vertex=True)
                        logger.warning(f"No vertex keys within RPM limit, using {current_key} anyway")
                        return current_key
                
                checked_keys.add(current_key)
                
                # 檢查這個 key 是否可用
                if (await self.is_vertex_key_valid(current_key) and 
                    await self.is_key_within_rpm_limit(current_key, model, is_vertex=True)):
                    self.current_vertex_key = current_key
                    await self._record_request(current_key, model, is_vertex=True)
                    logger.debug(f"Selected vertex key {current_key} for model {model}")
                    return current_key
                
                # 嘗試下一個 key
                current_key = await self.get_next_vertex_key()
    
    async def _get_least_used_vertex_key(self, model: str) -> Union[str, None]:
        """獲取 RPM 使用率最低的有效 Vertex key"""
        rpm_limit = self._get_rpm_limit_for_model(model)
        best_key = None
        lowest_usage = float('inf')
        
        for key in self.vertex_api_keys:
            if await self.is_vertex_key_valid(key):
                current_rpm = self._get_rpm_count(key, model, is_vertex=True)
                usage_ratio = current_rpm / rpm_limit if rpm_limit > 0 else 0
                if usage_ratio < lowest_usage:
                    lowest_usage = usage_ratio
                    best_key = key
        
        return best_key

    async def handle_api_failure(self, api_key: str, retries: int, model: str = None) -> str:
        """处理API调用失败"""
        async with self.failure_count_lock:
            self.key_failure_counts[api_key] += 1
            if self.key_failure_counts[api_key] >= self.MAX_FAILURES:
                logger.warning(
                    f"API key {api_key} has failed {self.MAX_FAILURES} times"
                )
        if retries < settings.MAX_RETRIES:
            # 使用傳入的 model 參數，如果沒有則使用內部狀態
            model_to_use = model or self.current_model
            if model_to_use:
                logger.info(f"[RPM] Handling API failure, getting new key for model: {model_to_use}")
                # 清除當前緩存的 key，強制選擇新的
                self.current_key = None
                return await self.get_next_working_key_with_rpm(model_to_use)
            else:
                logger.warning("[RPM] No model info available, falling back to non-RPM key selection")
                return await self.get_next_working_key()
        else:
            return ""

    async def handle_vertex_api_failure(self, api_key: str, retries: int) -> str:
        """处理 Vertex Express API 调用失败"""
        async with self.vertex_failure_count_lock:
            self.vertex_key_failure_counts[api_key] += 1
            if self.vertex_key_failure_counts[api_key] >= self.MAX_FAILURES:
                logger.warning(
                    f"Vertex Express API key {api_key} has failed {self.MAX_FAILURES} times"
                )

    def get_fail_count(self, key: str) -> int:
        """获取指定密钥的失败次数"""
        return self.key_failure_counts.get(key, 0)

    def get_vertex_fail_count(self, key: str) -> int:
        """获取指定 Vertex 密钥的失败次数"""
        return self.vertex_key_failure_counts.get(key, 0)

    async def get_keys_by_status(self) -> dict:
        """获取分类后的API key列表，包括失败次数"""
        valid_keys = {}
        invalid_keys = {}

        async with self.failure_count_lock:
            for key in self.api_keys:
                fail_count = self.key_failure_counts[key]
                if fail_count < self.MAX_FAILURES:
                    valid_keys[key] = fail_count
                else:
                    invalid_keys[key] = fail_count

        return {"valid_keys": valid_keys, "invalid_keys": invalid_keys}

    async def get_vertex_keys_by_status(self) -> dict:
        """获取分类后的 Vertex Express API key 列表，包括失败次数"""
        valid_keys = {}
        invalid_keys = {}

        async with self.vertex_failure_count_lock:
            for key in self.vertex_api_keys:
                fail_count = self.vertex_key_failure_counts[key]
                if fail_count < self.MAX_FAILURES:
                    valid_keys[key] = fail_count
                else:
                    invalid_keys[key] = fail_count
        return {"valid_keys": valid_keys, "invalid_keys": invalid_keys}
    
    async def get_rpm_status(self, model: str = None) -> dict:
        """獲取 RPM 使用狀況報告"""
        current_time = time.time()
        rpm_status = {
            "api_keys": {},
            "vertex_keys": {},
            "current_model": self.current_model,
            "rpm_window_seconds": self.rpm_window_seconds,
            "rpm_prefer_cache": self.rpm_prefer_cache,
            "rpm_limits": self.rpm_limits
        }
        
        if model:
            rpm_status["model_rpm_limit"] = self._get_rpm_limit_for_model(model)
        
        # 獲取 API keys 的 RPM 狀況
        async with self.rpm_lock:
            for key in self.api_keys:
                key_status = {
                    "models": {},
                    "is_current": key == self.current_key,
                    "failure_count": self.key_failure_counts[key]
                }
                
                # 顯示每個模型的使用情況
                for model_name in set(self.key_request_times[key].keys()):
                    timestamps = self.key_request_times[key][model_name]
                    self._clean_old_requests(timestamps, current_time)
                    current_rpm = len(timestamps)
                    rpm_limit = self._get_rpm_limit_for_model(model_name)
                    
                    key_status["models"][model_name] = {
                        "current_rpm": current_rpm,
                        "rpm_limit": rpm_limit,
                        "usage_percentage": (current_rpm / rpm_limit * 100) if rpm_limit > 0 else 0
                    }
                
                rpm_status["api_keys"][key] = key_status
        
        # 獲取 Vertex keys 的 RPM 狀況
        async with self.vertex_rpm_lock:
            for key in self.vertex_api_keys:
                key_status = {
                    "models": {},
                    "is_current": key == self.current_vertex_key,
                    "failure_count": self.vertex_key_failure_counts[key]
                }
                
                # 顯示每個模型的使用情況
                for model_name in set(self.vertex_key_request_times[key].keys()):
                    timestamps = self.vertex_key_request_times[key][model_name]
                    self._clean_old_requests(timestamps, current_time)
                    current_rpm = len(timestamps)
                    rpm_limit = self._get_rpm_limit_for_model(model_name)
                    
                    key_status["models"][model_name] = {
                        "current_rpm": current_rpm,
                        "rpm_limit": rpm_limit,
                        "usage_percentage": (current_rpm / rpm_limit * 100) if rpm_limit > 0 else 0
                    }
                
                rpm_status["vertex_keys"][key] = key_status
        
        logger.info(f"RPM Status Report: {json.dumps(rpm_status, indent=2)}")
        return rpm_status

    async def get_first_valid_key(self) -> str:
        """获取第一个有效的API key"""
        async with self.failure_count_lock:
            for key in self.key_failure_counts:
                if self.key_failure_counts[key] < self.MAX_FAILURES:
                    return key
        if self.api_keys:
            return self.api_keys[0]
        if not self.api_keys:
            logger.warning("API key list is empty, cannot get first valid key.")
            return ""
        return self.api_keys[0]


_singleton_instance = None
_singleton_lock = asyncio.Lock()
_preserved_failure_counts: Union[Dict[str, int], None] = None
_preserved_vertex_failure_counts: Union[Dict[str, int], None] = None
_preserved_old_api_keys_for_reset: Union[list, None] = None
_preserved_vertex_old_api_keys_for_reset: Union[list, None] = None
_preserved_next_key_in_cycle: Union[str, None] = None
_preserved_vertex_next_key_in_cycle: Union[str, None] = None


async def get_key_manager_instance(
    api_keys: list = None, vertex_api_keys: list = None
) -> KeyManager:
    """
    获取 KeyManager 单例实例。

    如果尚未创建实例，将使用提供的 api_keys,vertex_api_keys 初始化 KeyManager。
    如果已创建实例，则忽略 api_keys 参数，返回现有单例。
    如果在重置后调用，会尝试恢复之前的状态（失败计数、循环位置）。
    """
    global _singleton_instance, _preserved_failure_counts, _preserved_vertex_failure_counts, _preserved_old_api_keys_for_reset, _preserved_vertex_old_api_keys_for_reset, _preserved_next_key_in_cycle, _preserved_vertex_next_key_in_cycle

    async with _singleton_lock:
        if _singleton_instance is None:
            if api_keys is None:
                raise ValueError(
                    "API keys are required to initialize or re-initialize the KeyManager instance."
                )
            if vertex_api_keys is None:
                raise ValueError(
                    "Vertex Express API keys are required to initialize or re-initialize the KeyManager instance."
                )

            if not api_keys:
                logger.warning(
                    "Initializing KeyManager with an empty list of API keys."
                )
            if not vertex_api_keys:
                logger.warning(
                    "Initializing KeyManager with an empty list of Vertex Express API keys."
                )

            _singleton_instance = KeyManager(api_keys, vertex_api_keys)
            logger.info(
                f"KeyManager instance created/re-created with {len(api_keys)} API keys and {len(vertex_api_keys)} Vertex Express API keys."
            )

            # 1. 恢复失败计数
            if _preserved_failure_counts:
                current_failure_counts = {
                    key: 0 for key in _singleton_instance.api_keys
                }
                for key, count in _preserved_failure_counts.items():
                    if key in current_failure_counts:
                        current_failure_counts[key] = count
                _singleton_instance.key_failure_counts = current_failure_counts
                logger.info("Inherited failure counts for applicable keys.")
            _preserved_failure_counts = None

            if _preserved_vertex_failure_counts:
                current_vertex_failure_counts = {
                    key: 0 for key in _singleton_instance.vertex_api_keys
                }
                for key, count in _preserved_vertex_failure_counts.items():
                    if key in current_vertex_failure_counts:
                        current_vertex_failure_counts[key] = count
                _singleton_instance.vertex_key_failure_counts = (
                    current_vertex_failure_counts
                )
                logger.info("Inherited failure counts for applicable Vertex keys.")
            _preserved_vertex_failure_counts = None

            # 2. 调整 key_cycle 的起始点
            start_key_for_new_cycle = None
            if (
                _preserved_old_api_keys_for_reset
                and _preserved_next_key_in_cycle
                and _singleton_instance.api_keys
            ):
                try:
                    start_idx_in_old = _preserved_old_api_keys_for_reset.index(
                        _preserved_next_key_in_cycle
                    )

                    for i in range(len(_preserved_old_api_keys_for_reset)):
                        current_old_key_idx = (start_idx_in_old + i) % len(
                            _preserved_old_api_keys_for_reset
                        )
                        key_candidate = _preserved_old_api_keys_for_reset[
                            current_old_key_idx
                        ]
                        if key_candidate in _singleton_instance.api_keys:
                            start_key_for_new_cycle = key_candidate
                            break
                except ValueError:
                    logger.warning(
                        f"Preserved next key '{_preserved_next_key_in_cycle}' not found in preserved old API keys. "
                        "New cycle will start from the beginning of the new list."
                    )
                except Exception as e:
                    logger.error(
                        f"Error determining start key for new cycle from preserved state: {e}. "
                        "New cycle will start from the beginning."
                    )

            if start_key_for_new_cycle and _singleton_instance.api_keys:
                try:
                    target_idx = _singleton_instance.api_keys.index(
                        start_key_for_new_cycle
                    )
                    # 設置索引而不是推進 cycle
                    _singleton_instance.current_key_index = target_idx
                    logger.info(
                        f"Key cycle in new instance advanced. Next call to get_next_key() will yield: {start_key_for_new_cycle}"
                    )
                except ValueError:
                    logger.warning(
                        f"Determined start key '{start_key_for_new_cycle}' not found in new API keys during cycle advancement. "
                        "New cycle will start from the beginning."
                    )
                except StopIteration:
                    logger.error(
                        "StopIteration while advancing key cycle, implies empty new API key list previously missed."
                    )
                except Exception as e:
                    logger.error(
                        f"Error advancing new key cycle: {e}. Cycle will start from beginning."
                    )
            else:
                if _singleton_instance.api_keys:
                    logger.info(
                        "New key cycle will start from the beginning of the new API key list (no specific start key determined or needed)."
                    )
                else:
                    logger.info(
                        "New key cycle not applicable as the new API key list is empty."
                    )

            # 清理所有保存的状态
            _preserved_old_api_keys_for_reset = None
            _preserved_next_key_in_cycle = None

            # 3. 调整 vertex_key_cycle 的起始点
            start_key_for_new_vertex_cycle = None
            if (
                _preserved_vertex_old_api_keys_for_reset
                and _preserved_vertex_next_key_in_cycle
                and _singleton_instance.vertex_api_keys
            ):
                try:
                    start_idx_in_old = _preserved_vertex_old_api_keys_for_reset.index(
                        _preserved_vertex_next_key_in_cycle
                    )

                    for i in range(len(_preserved_vertex_old_api_keys_for_reset)):
                        current_old_key_idx = (start_idx_in_old + i) % len(
                            _preserved_vertex_old_api_keys_for_reset
                        )
                        key_candidate = _preserved_vertex_old_api_keys_for_reset[
                            current_old_key_idx
                        ]
                        if key_candidate in _singleton_instance.vertex_api_keys:
                            start_key_for_new_vertex_cycle = key_candidate
                            break
                except ValueError:
                    logger.warning(
                        f"Preserved next key '{_preserved_vertex_next_key_in_cycle}' not found in preserved old Vertex Express API keys. "
                        "New cycle will start from the beginning of the new list."
                    )
                except Exception as e:
                    logger.error(
                        f"Error determining start key for new Vertex key cycle from preserved state: {e}. "
                        "New cycle will start from the beginning."
                    )

            if start_key_for_new_vertex_cycle and _singleton_instance.vertex_api_keys:
                try:
                    target_idx = _singleton_instance.vertex_api_keys.index(
                        start_key_for_new_vertex_cycle
                    )
                    # 設置索引而不是推進 cycle
                    _singleton_instance.current_vertex_key_index = target_idx
                    logger.info(
                        f"Vertex key cycle in new instance advanced. Next call to get_next_vertex_key() will yield: {start_key_for_new_vertex_cycle}"
                    )
                except ValueError:
                    logger.warning(
                        f"Determined start key '{start_key_for_new_vertex_cycle}' not found in new Vertex Express API keys during cycle advancement. "
                        "New cycle will start from the beginning."
                    )
                except StopIteration:
                    logger.error(
                        "StopIteration while advancing Vertex key cycle, implies empty new Vertex Express API key list previously missed."
                    )
                except Exception as e:
                    logger.error(
                        f"Error advancing new Vertex key cycle: {e}. Cycle will start from beginning."
                    )
            else:
                if _singleton_instance.vertex_api_keys:
                    logger.info(
                        "New Vertex key cycle will start from the beginning of the new Vertex Express API key list (no specific start key determined or needed)."
                    )
                else:
                    logger.info(
                        "New Vertex key cycle not applicable as the new Vertex Express API key list is empty."
                    )

            # 清理所有保存的状态
            _preserved_vertex_old_api_keys_for_reset = None
            _preserved_vertex_next_key_in_cycle = None

        return _singleton_instance


async def reset_key_manager_instance():
    """
    重置 KeyManager 单例实例。
    将保存当前实例的状态（失败计数、旧 API keys、下一个 key 提示）
    以供下一次 get_key_manager_instance 调用时恢复。
    """
    global _singleton_instance, _preserved_failure_counts, _preserved_vertex_failure_counts, _preserved_old_api_keys_for_reset, _preserved_vertex_old_api_keys_for_reset, _preserved_next_key_in_cycle, _preserved_vertex_next_key_in_cycle
    async with _singleton_lock:
        if _singleton_instance:
            # 1. 保存失败计数
            _preserved_failure_counts = _singleton_instance.key_failure_counts.copy()
            _preserved_vertex_failure_counts = (
                _singleton_instance.vertex_key_failure_counts.copy()
            )

            # 2. 保存旧的 API keys 列表
            _preserved_old_api_keys_for_reset = _singleton_instance.api_keys.copy()
            _preserved_vertex_old_api_keys_for_reset = (
                _singleton_instance.vertex_api_keys.copy()
            )

            # 3. 保存 key_cycle 的下一个 key 提示
            try:
                if _singleton_instance.api_keys:
                    _preserved_next_key_in_cycle = (
                        await _singleton_instance.get_next_key()
                    )
                else:
                    _preserved_next_key_in_cycle = None
            except StopIteration:
                logger.warning(
                    "Could not preserve next key hint: key cycle was empty or exhausted in old instance."
                )
                _preserved_next_key_in_cycle = None
            except Exception as e:
                logger.error(f"Error preserving next key hint during reset: {e}")
                _preserved_next_key_in_cycle = None

            # 4. 保存 vertex_key_cycle 的下一个 key 提示
            try:
                if _singleton_instance.vertex_api_keys:
                    _preserved_vertex_next_key_in_cycle = (
                        await _singleton_instance.get_next_vertex_key()
                    )
                else:
                    _preserved_vertex_next_key_in_cycle = None
            except StopIteration:
                logger.warning(
                    "Could not preserve next key hint: Vertex key cycle was empty or exhausted in old instance."
                )
                _preserved_vertex_next_key_in_cycle = None
            except Exception as e:
                logger.error(f"Error preserving next key hint during reset: {e}")
                _preserved_vertex_next_key_in_cycle = None

            _singleton_instance = None
            logger.info(
                "KeyManager instance has been reset. State (failure counts, old keys, next key hint) preserved for next instantiation."
            )
        else:
            logger.info(
                "KeyManager instance was not set (or already reset), no reset action performed."
            )
