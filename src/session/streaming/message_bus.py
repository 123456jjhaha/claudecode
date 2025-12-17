"""Redis 消息总线 - 实时消息推送"""

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import AsyncIterator, Optional

import yaml

logger = logging.getLogger(__name__)


class MessageBus:
    """
    全局消息总线（Redis Pub/Sub）

    特性：
    - 全局单例模式，所有 AgentSystem 实例共享
    - 支持多频道发布和订阅
    - 降级策略：Redis 不可用时静默失败
    - 连接池管理，支持并发
    """

    def __init__(
        self,
        redis_url: str = "redis://localhost:6379",
        redis_db: int = 0,
        max_connections: int = 50
    ):
        """
        初始化消息总线

        Args:
            redis_url: Redis 连接 URL
            redis_db: Redis 数据库编号
            max_connections: 连接池最大连接数
        """
        self.redis_url = redis_url
        self.redis_db = redis_db
        self.max_connections = max_connections

        self._redis_client = None
        self._pubsub = None
        self._connected = False
        self._lock = asyncio.Lock()

    @classmethod
    def from_config(cls, config_path: Optional[str] = None) -> "MessageBus":
        """
        从配置文件或环境变量加载配置

        配置优先级：环境变量 > streaming.yaml > 默认值

        Args:
            config_path: 配置文件路径（可选）

        Returns:
            MessageBus 实例
        """
        # 默认配置
        redis_url = "redis://localhost:6379"
        redis_db = 0
        max_connections = 50

        # 尝试从 streaming.yaml 加载
        if config_path is None:
            # 查找项目根目录的 streaming.yaml
            config_path = Path.cwd() / "streaming.yaml"
        else:
            config_path = Path(config_path)

        if config_path.exists():
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    config = yaml.safe_load(f)

                redis_config = config.get("redis", {})
                redis_url = redis_config.get("url", redis_url)
                redis_db = redis_config.get("db", redis_db)
                max_connections = redis_config.get("max_connections", max_connections)

                logger.info(f"从 {config_path} 加载 MessageBus 配置")
            except Exception as e:
                logger.warning(f"加载配置文件失败: {e}，使用默认配置")

        # 环境变量覆盖
        redis_url = os.getenv("REDIS_URL", redis_url)
        redis_db = int(os.getenv("REDIS_DB", str(redis_db)))
        max_connections = int(os.getenv("REDIS_MAX_CONNECTIONS", str(max_connections)))

        return cls(
            redis_url=redis_url,
            redis_db=redis_db,
            max_connections=max_connections
        )

    async def connect(self) -> bool:
        """
        连接到 Redis

        Returns:
            是否连接成功
        """
        if self._connected:
            return True

        async with self._lock:
            if self._connected:
                return True

            try:
                # 导入 redis.asyncio
                import redis.asyncio as aioredis

                # 创建连接池
                pool = aioredis.ConnectionPool.from_url(
                    self.redis_url,
                    db=self.redis_db,
                    max_connections=self.max_connections,
                    decode_responses=True
                )

                # 创建 Redis 客户端
                self._redis_client = aioredis.Redis(connection_pool=pool)

                # 测试连接
                await self._redis_client.ping()

                self._connected = True
                logger.info(f"MessageBus 已连接到 Redis: {self.redis_url}")
                return True

            except ImportError:
                logger.warning("redis 库未安装，MessageBus 降级运行（不推送实时消息）")
                self._connected = False
                return False
            except Exception as e:
                logger.warning(f"连接 Redis 失败: {e}，MessageBus 降级运行")
                self._connected = False
                return False

    async def publish(self, channel: str, message: dict) -> bool:
        """
        发布消息到指定频道

        Args:
            channel: 频道名称
            message: 消息内容（字典）

        Returns:
            是否发布成功
        """
        if not self._connected or self._redis_client is None:
            # 降级：静默失败
            return False

        try:
            message_json = json.dumps(message, ensure_ascii=False)
            await self._redis_client.publish(channel, message_json)
            return True
        except Exception as e:
            logger.warning(f"发布消息到 {channel} 失败: {e}")
            return False

    async def subscribe(self, *channels: str) -> AsyncIterator[dict]:
        """
        订阅一个或多个频道

        Args:
            *channels: 频道名称列表

        Yields:
            消息字典
        """
        if not self._connected or self._redis_client is None:
            logger.error("Redis 未连接，无法订阅消息")
            return

        try:
            # 创建 PubSub 对象
            pubsub = self._redis_client.pubsub()

            # 订阅频道
            await pubsub.subscribe(*channels)
            logger.info(f"订阅频道: {channels}")

            # 监听消息
            async for message in pubsub.listen():
                if message["type"] == "message":
                    try:
                        data = json.loads(message["data"])
                        yield data
                    except json.JSONDecodeError as e:
                        logger.warning(f"解析消息失败: {e}")
                        continue
        except Exception as e:
            logger.error(f"订阅消息失败: {e}")
        finally:
            if pubsub:
                await pubsub.unsubscribe(*channels)
                await pubsub.close()

    async def close(self):
        """关闭 Redis 连接"""
        if self._redis_client:
            try:
                await self._redis_client.close()
                await self._redis_client.connection_pool.disconnect()
                self._connected = False
                logger.info("MessageBus 已关闭")
            except Exception as e:
                logger.warning(f"关闭 MessageBus 时发生错误: {e}")

    @property
    def is_connected(self) -> bool:
        """是否已连接"""
        return self._connected
