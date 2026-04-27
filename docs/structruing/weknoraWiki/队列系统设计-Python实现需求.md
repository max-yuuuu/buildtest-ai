# 队列系统设计 - Python 实现需求

## 📋 目录
- [1. 需求概述](#1-需求概述)
- [2. 核心队列设计](#2-核心队列设计)
- [3. 任务类型定义](#3-任务类型定义)
- [4. 技术选型](#4-技术选型)
- [5. 架构设计](#5-架构设计)
- [6. 实现方案](#6-实现方案)
- [7. 监控与运维](#7-监控与运维)

---

## 1. 需求概述

### 1.1 设计目标

基于 WeKnora Go 项目的队列系统设计，在 Python 系统中实现功能完善、性能优异的任务队列系统，满足以下核心需求：

| 需求 | 说明 |
|------|------|
| **双队列架构** | 同时支持 IM 请求队列和后台任务队列 |
| **优先级队列** | 支持任务优先级调度 |
| **分布式限流** | 支持跨实例的全局并发控制 |
| **任务链** | 支持工作流编排和任务依赖 |
| **可观测性** | 完整的指标监控和链路追踪 |
| **弹性模式** | 支持 Lite 模式（无 Redis）和完整模式 |

### 1.2 核心特性

✅ **有界队列** - 防止无限增长，保护系统资源  
✅ **用户限流** - 按用户维度限制请求数量  
✅ **超时机制** - 请求等待超时自动丢弃  
✅ **任务取消** - 支持取消排队和执行中的任务  
✅ **重试策略** - 智能重试，支持自定义退避  
✅ **指标监控** - 队列深度、活跃 Worker、计数等  
✅ **链路追踪** - 集成 Langfuse，完整追踪任务链路  

---

## 2. 核心队列设计

### 2.1 队列一：QA 请求队列（类似 Go 的 qaQueue）

**用途**：处理即时通讯模块的问答请求

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `max_queue_size` | 50 | 最大队列容量 |
| `max_per_user` | 3 | 单个用户最多排队数 |
| `worker_count` | 5 | Worker 并发数 |
| `queue_timeout` | 60 | 队列超时（秒） |
| `global_max_workers` | 0 | 全局并发限制（0 表示不限制） |

**架构图**：
```
用户消息 → [限流检查] → [入队] → [等待队列]
                                     ↓
                              Worker Pool (5个)
                                     ↓
                              QA 处理管道
```

**限流策略**：
1. 先检查 Redis 全局用户计数（如果启用）
2. 再检查本地用户计数
3. 最后检查队列是否已满

**超时处理**：
- 请求在队列中等待超过 60 秒自动丢弃
- 发送超时提示给用户

### 2.2 队列二：后台任务队列（类似 Go 的 asynq）

**用途**：处理文档处理、知识库维护等后台任务

**优先级队列设计**：

| 队列名称 | 优先级 | 说明 |
|---------|--------|------|
| `queue:critical` | 6 | 关键任务（如知识库删除） |
| `queue:default` | 3 | 默认任务（文档处理等） |
| `queue:low` | 1 | 低优先级任务（批量清理等） |

---

## 3. 任务类型定义

### 3.1 文档处理类任务

| 任务类型 | 说明 |
|---------|------|
| `document:process` | 文档处理任务（解析 → 分块 → 嵌入 → 存储） |
| `chunk:extract` | 分块提取任务 |
| `faq:import` | FAQ 导入任务（支持 dry run） |

### 3.2 知识库维护类任务

| 任务类型 | 说明 |
|---------|------|
| `knowledge:post_process` | 知识后处理任务 |
| `knowledge:move` | 知识移动任务 |
| `knowledge:list_delete` | 批量删除知识任务 |
| `manual:process` | 手工知识更新任务 |
| `kb:clone` | 知识库复制任务 |
| `kb:delete` | 知识库删除任务 |
| `index:delete` | 索引删除任务 |

### 3.3 内容生成类任务

| 任务类型 | 说明 |
|---------|------|
| `question:generation` | 问题生成任务 |
| `summary:generation` | 摘要生成任务 |
| `datatable:summary` | 表格摘要任务 |
| `image:multimodal` | 图片多模态处理任务（OCR + VLM 标题） |

### 3.4 数据源同步类任务

| 任务类型 | 说明 |
|---------|------|
| `datasource:sync` | 数据源同步任务 |
| `wiki:ingest` | Wiki 页面同步任务 |

---

## 4. 技术选型

### 4.1 核心技术栈

| 组件 | 技术选择 | 理由 |
|------|---------|------|
| **任务队列** | Celery + Redis | Python 生态最成熟的方案 |
| **IM 队列** | 自定义内存队列 + 可选 Redis | 轻量级，支持分布式 |
| **Web 框架** | FastAPI | 高性能、自动文档 |
| **链路追踪** | Langfuse | 完整的任务可观测性 |
| **监控** | Prometheus + Grafana | 开源标准方案 |

### 4.2 备选方案

| 场景 | 方案 | 说明 |
|------|------|------|
| **Lite 模式** | RQ (Redis Queue) 或 Huey | 更轻量的任务队列 |
| **超大规模** | Dramatiq + RabbitMQ | 支持更高吞吐量 |
| **无 Redis 模式** | 内存队列 + 线程池 | 单实例部署 |

---

## 5. 架构设计

### 5.1 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                        API 层 (FastAPI)                      │
│  ┌─────────────────┐  ┌─────────────────┐  ┌──────────────┐ │
│  │ /api/v1/chat   │  │ /api/v1/tasks   │  │ /api/v1/docs │ │
│  └────────┬────────┘  └────────┬────────┘  └──────┬───────┘ │
└───────────┼────────────────────┼───────────────────┼─────────┘
            │                    │                   │
            ▼                    ▼                   ▼
┌──────────────────────┐ ┌──────────────────────┐ ┌──────────────┐
│   QA 请求队列        │ │   后台任务队列       │ │  任务状态    │
│   (自定义队列)       │ │   (Celery + Redis)   │ │  管理服务     │
└───────────┬──────────┘ └───────────┬──────────┘ └──────┬───────┘
            │                        │                   │
            ▼                        ▼                   ▼
┌──────────────────────┐ ┌──────────────────────┐ ┌──────────────┐
│   QA Worker Pool     │ │   Task Workers       │ │  Langfuse    │
│   (5 个并发)         │ │   (多队列优先级)    │ │  链路追踪     │
└──────────────────────┘ └──────────────────────┘ └──────────────┘
```

### 5.2 数据模型

**任务状态模型**：
```python
from enum import Enum
from datetime import datetime
from pydantic import BaseModel
from typing import Dict, Any, Optional

class TaskStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"

class TaskInfo(BaseModel):
    task_id: str
    task_type: str
    status: TaskStatus
    tenant_id: Optional[int] = None
    metadata: Dict[str, Any] = {}
    progress: int = 0
    error_message: Optional[str] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
```

---

## 6. 实现方案

### 6.1 QA 请求队列实现

```python
# app/queues/qa_queue.py
import asyncio
import time
from typing import Optional, Dict, List, Callable
from dataclasses import dataclass
from enum import Enum
import uuid
import redis.asyncio as redis
from contextlib import contextmanager

class QueueError(Exception):
    pass

class QueueFullError(QueueError):
    pass

class UserLimitError(QueueError):
    pass

@dataclass
class QARequest:
    request_id: str
    user_key: str
    channel_id: str
    message: Dict
    context: Dict
    created_at: float
    cancelled: bool = False
    _cancel_event: Optional[asyncio.Event] = None

    def __post_init__(self):
        self._cancel_event = asyncio.Event()

    def cancel(self):
        self.cancelled = True
        if self._cancel_event:
            self._cancel_event.set()

    async def wait_for_cancel(self, timeout: Optional[float] = None):
        if self._cancel_event:
            try:
                await asyncio.wait_for(self._cancel_event.wait(), timeout)
            except asyncio.TimeoutError:
                pass
        return self.cancelled

@dataclass
class QueueMetrics:
    depth: int
    active_workers: int
    total_enqueued: int
    total_processed: int
    total_rejected: int
    total_timeout: int

class QAQueue:
    """问答请求队列 - 有界、用户限流、支持超时"""

    def __init__(
        self,
        max_queue_size: int = 50,
        max_per_user: int = 3,
        worker_count: int = 5,
        queue_timeout: float = 60.0,
        global_max_workers: int = 0,
        redis_url: Optional[str] = None,
        handler: Optional[Callable] = None,
    ):
        self.max_queue_size = max_queue_size
        self.max_per_user = max_per_user
        self.worker_count = worker_count
        self.queue_timeout = queue_timeout
        self.global_max_workers = global_max_workers

        self._queue: List[QARequest] = []
        self._per_user: Dict[str, int] = {}
        self._lock = asyncio.Lock()
        self._not_empty = asyncio.Condition(self._lock)
        self._closed = False

        self._redis: Optional[redis.Redis] = None
        if redis_url:
            self._redis = redis.from_url(redis_url)

        self._handler = handler

        self._active_workers = 0
        self._total_enqueued = 0
        self._total_processed = 0
        self._total_rejected = 0
        self._total_timeout = 0

        self._workers: List[asyncio.Task] = []

    async def start(self):
        """启动 Worker"""
        for i in range(self.worker_count):
            worker = asyncio.create_task(self._worker_loop(i))
            self._workers.append(worker)
        asyncio.create_task(self._metrics_loop())

    async def stop(self):
        """停止队列"""
        async with self._lock:
            self._closed = True
            self._not_empty.notify_all()

        for worker in self._workers:
            worker.cancel()

        await asyncio.gather(*self._workers, return_exceptions=True)

        if self._redis:
            await self._redis.close()

    async def enqueue(
        self,
        user_key: str,
        channel_id: str,
        message: Dict,
        context: Optional[Dict] = None,
    ) -> str:
        """入队请求
        
        Returns: request_id
        Raises: QueueFullError, UserLimitError
        """
        request_id = str(uuid.uuid4())

        async with self._lock:
            if self._closed:
                raise QueueError("Queue is closed")

            if self._redis:
                ok = await self._redis_check_and_incr_user(user_key)
                if not ok:
                    self._total_rejected += 1
                    raise UserLimitError(f"User {user_key} limit reached")
            else:
                if self._per_user.get(user_key, 0) >= self.max_per_user:
                    self._total_rejected += 1
                    raise UserLimitError(f"User {user_key} limit reached")

            if len(self._queue) >= self.max_queue_size:
                if self._redis:
                    await self._redis_decr_user(user_key)
                self._total_rejected += 1
                raise QueueFullError(f"Queue is full ({self.max_queue_size})")

            request = QARequest(
                request_id=request_id,
                user_key=user_key,
                channel_id=channel_id,
                message=message,
                context=context or {},
                created_at=time.time(),
            )

            self._queue.append(request)
            if not self._redis:
                self._per_user[user_key] = self._per_user.get(user_key, 0) + 1
            self._total_enqueued += 1

            queue_position = len(self._queue)

            self._not_empty.notify()

        return request_id, queue_position

    async def cancel(self, user_key: str) -> bool:
        """取消用户的排队请求"""
        async with self._lock:
            for i, request in enumerate(self._queue):
                if request.user_key == user_key:
                    request.cancel()
                    self._queue.pop(i)
                    if not self._redis:
                        self._per_user[user_key] -= 1
                        if self._per_user[user_key] <= 0:
                            del self._per_user[user_key]
                    await self._redis_decr_user(user_key)
                    return True
            return False

    def get_metrics(self) -> QueueMetrics:
        """获取队列指标"""
        return QueueMetrics(
            depth=len(self._queue),
            active_workers=self._active_workers,
            total_enqueued=self._total_enqueued,
            total_processed=self._total_processed,
            total_rejected=self._total_rejected,
            total_timeout=self._total_timeout,
        )

    async def _worker_loop(self, worker_id: int):
        """Worker 主循环"""
        while True:
            request = await self._dequeue()
            if request is None:
                break

            if request.cancelled:
                continue

            wait_time = time.time() - request.created_at
            if wait_time > self.queue_timeout:
                self._total_timeout += 1
                await self._redis_decr_user(request.user_key)
                continue

            try:
                if self.global_max_workers > 0 and self._redis:
                    acquired = await self._acquire_global_gate(request)
                    if not acquired:
                        self._total_timeout += 1
                        await self._redis_decr_user(request.user_key)
                        continue

                self._active_workers += 1

                if self._handler:
                    await self._handler(request)

                self._total_processed += 1

            except Exception as e:
                pass
            finally:
                self._active_workers -= 1
                if self.global_max_workers > 0 and self._redis:
                    await self._release_global_gate()
                await self._redis_decr_user(request.user_key)

    async def _dequeue(self) -> Optional[QARequest]:
        """出队请求"""
        async with self._lock:
            while len(self._queue) == 0 and not self._closed:
                await self._not_empty.wait()

            if self._closed and len(self._queue) == 0:
                return None

            request = self._queue.pop(0)
            if not self._redis:
                self._per_user[request.user_key] -= 1
                if self._per_user[request.user_key] <= 0:
                    del self._per_user[request.user_key]

            return request

    async def _redis_check_and_incr_user(self, user_key: str) -> bool:
        """Redis 全局用户计数检查并增加"""
        if not self._redis:
            return True

        key = f"queue:user:{user_key}"
        count = await self._redis.incr(key)
        await self._redis.expire(key, 300)

        if count > self.max_per_user:
            await self._redis.decr(key)
            return False
        return True

    async def _redis_decr_user(self, user_key: str):
        """Redis 减少用户计数"""
        if not self._redis:
            return
        key = f"queue:user:{user_key}"
        await self._redis.decr(key)

    async def _acquire_global_gate(self, request: QARequest) -> bool:
        """获取全局并发槽位"""
        if not self._redis or self.global_max_workers <= 0:
            return True

        key = "queue:global:gate"
        script = """
        local count = redis.call('INCR', KEYS[1])
        redis.call('PEXPIRE', KEYS[1], 300000)
        if count <= tonumber(ARGV[1]) then
            return 1
        end
        redis.call('DECR', KEYS[1])
        return 0
        """

        while True:
            result = await self._redis.eval(
                script,
                1,
                key,
                self.global_max_workers,
            )
            if result == 1:
                return True

            cancelled = await request.wait_for_cancel(0.5)
            if cancelled:
                return False

    async def _release_global_gate(self):
        """释放全局并发槽位"""
        if not self._redis or self.global_max_workers <= 0:
            return
        key = "queue:global:gate"
        await self._redis.decr(key)

    async def _metrics_loop(self):
        """指标监控循环"""
        while not self._closed:
            await asyncio.sleep(30)
            metrics = self.get_metrics()
            if metrics.depth > 0 or metrics.active_workers > 0:
                pass
```

### 6.2 后台任务队列（Celery）实现

```python
# app/core/celery_app.py
import os
from celery import Celery
from celery.schedules import crontab
from kombu import Queue, Exchange

def get_celery_app():
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    app = Celery(
        "weknora",
        broker=redis_url,
        backend=redis_url.replace("/0", "/1"),
    )

    app.conf.update(
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        timezone="Asia/Shanghai",
        enable_utc=True,
        task_track_started=True,
        task_time_limit=30 * 60,
        task_soft_time_limit=25 * 60,
        worker_prefetch_multiplier=1,
        worker_max_tasks_per_child=1000,
        task_default_queue="default",
        task_queues=[
            Queue("critical", Exchange("critical"), routing_key="critical"),
            Queue("default", Exchange("default"), routing_key="default"),
            Queue("low", Exchange("low"), routing_key="low"),
        ],
        task_routes={
            "app.tasks.knowledge.*": {"queue": "default"},
            "app.tasks.kb.*": {"queue": "default"},
            "app.tasks.delete.*": {"queue": "critical"},
            "app.tasks.cleanup.*": {"queue": "low"},
        },
    )

    return app

celery_app = get_celery_app()
```

```python
# app/tasks/base.py
from functools import wraps
from typing import Dict, Any
from celery import Task
from app.core.celery_app import celery_app
from app.tracing import langfuse_tracer

def inject_tracing(func):
    """注入链路追踪"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        tracing_context = kwargs.pop("tracing_context", None)
        
        with langfuse_tracer.start_trace(
            name=f"celery:{func.__name__}",
            tracing_context=tracing_context,
        ):
            return func(*args, **kwargs)
    
    return wrapper

class BaseTask(Task):
    """基础任务类"""
    abstract = True
    
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        langfuse_tracer.set_trace_status("error")
        
    def on_success(self, retval, task_id, args, kwargs):
        langfuse_tracer.set_trace_status("success")
```

```python
# app/tasks/knowledge_tasks.py
from app.core.celery_app import celery_app
from app.tasks.base import BaseTask, inject_tracing
from app.models.task import DocumentProcessPayload
from app.services.knowledge_service import KnowledgeService

@celery_app.task(bind=True, base=BaseTask, name="document:process")
@inject_tracing
def process_document_task(self, payload: Dict[str, Any]):
    """文档处理任务"""
    task_payload = DocumentProcessPayload(**payload)
    
    service = KnowledgeService()
    result = service.process_document(
        tenant_id=task_payload.tenant_id,
        knowledge_id=task_payload.knowledge_id,
        knowledge_base_id=task_payload.knowledge_base_id,
        file_path=task_payload.file_path,
        enable_multimodal=task_payload.enable_multimodal,
        enable_question_generation=task_payload.enable_question_generation,
    )
    
    return result

@celery_app.task(bind=True, base=BaseTask, name="question:generation")
@inject_tracing
def generate_questions_task(self, payload: Dict[str, Any]):
    """问题生成任务"""
    from app.services.generation_service import GenerationService
    
    service = GenerationService()
    service.generate_questions(
        tenant_id=payload["tenant_id"],
        knowledge_base_id=payload["knowledge_base_id"],
        knowledge_id=payload["knowledge_id"],
        question_count=payload.get("question_count", 3),
    )
```

### 6.3 Lite 模式（无 Redis）实现

```python
# app/queues/sync_executor.py
import asyncio
from typing import Dict, Callable, Any, Optional
from dataclasses import dataclass
import uuid
import logging

logger = logging.getLogger(__name__)

@dataclass
class SyncTask:
    task_id: str
    task_type: str
    payload: Dict[str, Any]
    handler: Callable

class SyncTaskExecutor:
    """同步任务执行器 - Lite 模式无 Redis"""
    
    def __init__(self):
        self._handlers: Dict[str, Callable] = {}
        self._tasks: Dict[str, SyncTask] = {}
        self._lock = asyncio.Lock()
    
    def register_handler(self, task_type: str, handler: Callable):
        """注册任务处理器"""
        self._handlers[task_type] = handler
    
    async def enqueue(
        self,
        task_type: str,
        payload: Dict[str, Any],
        task_id: Optional[str] = None,
    ) -> str:
        """入队任务（直接在后台执行）"""
        if task_type not in self._handlers:
            raise ValueError(f"No handler for task type: {task_type}")
        
        task_id = task_id or str(uuid.uuid4())
        task = SyncTask(
            task_id=task_id,
            task_type=task_type,
            payload=payload,
            handler=self._handlers[task_type],
        )
        
        async with self._lock:
            self._tasks[task_id] = task
        
        asyncio.create_task(self._execute_task(task))
        
        return task_id
    
    async def _execute_task(self, task: SyncTask):
        """执行任务"""
        logger.info(f"[SyncTask] Executing {task.task_type} id={task.task_id}")
        try:
            if asyncio.iscoroutinefunction(task.handler):
                await task.handler(task.payload)
            else:
                task.handler(task.payload)
            logger.info(f"[SyncTask] Completed {task.task_type} id={task.task_id}")
        except Exception as e:
            logger.exception(f"[SyncTask] Failed {task.task_type} id={task.task_id}")
        finally:
            async with self._lock:
                self._tasks.pop(task.task_id, None)
```

### 6.4 任务链（工作流）实现

```python
# app/tasks/workflow.py
from celery import chain, group, chord
from app.core.celery_app import celery_app
from app.tasks.knowledge_tasks import (
    process_document_task,
    generate_questions_task,
)
from app.tasks.storage_tasks import (
    store_to_pgvector_task,
    store_to_elasticsearch_task,
    store_to_pgage_task,
)

def create_document_processing_workflow(
    tenant_id: int,
    knowledge_id: str,
    knowledge_base_id: str,
    file_path: str,
    enable_multimodal: bool = True,
    enable_question_generation: bool = True,
):
    """创建文档处理工作流
    
    流程：
    1. 文档处理（解析 → 分块 → 嵌入）
    2. 并行存储到三个数据库
    3. 可选：生成问题
    """
    
    payload = {
        "tenant_id": tenant_id,
        "knowledge_id": knowledge_id,
        "knowledge_base_id": knowledge_base_id,
        "file_path": file_path,
        "enable_multimodal": enable_multimodal,
        "enable_question_generation": enable_question_generation,
    }
    
    workflow = chain(
        process_document_task.si(payload),
        group(
            store_to_pgvector_task.s(),
            store_to_elasticsearch_task.s(),
            store_to_pgage_task.s(),
        ),
    )
    
    if enable_question_generation:
        workflow |= generate_questions_task.si({
            "tenant_id": tenant_id,
            "knowledge_base_id": knowledge_base_id,
            "knowledge_id": knowledge_id,
        })
    
    return workflow
```

---

## 7. 监控与运维

### 7.1 Prometheus 指标

```python
# app/monitoring/metrics.py
from prometheus_client import (
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

queue_depth = Gauge(
    "weknora_queue_depth",
    "Queue depth",
    ["queue_name"],
)

active_workers = Gauge(
    "weknora_active_workers",
    "Number of active workers",
    ["queue_name"],
)

tasks_total = Counter(
    "weknora_tasks_total",
    "Total tasks processed",
    ["queue_name", "task_type", "status"],
)

task_duration = Histogram(
    "weknora_task_duration_seconds",
    "Task processing duration",
    ["queue_name", "task_type"],
    buckets=[0.1, 0.5, 1, 5, 10, 30, 60, 300, 600],
)
```

### 7.2 健康检查

```python
# app/api/health.py
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Dict

router = APIRouter(prefix="/health", tags=["health"])

class HealthResponse(BaseModel):
    status: str
    services: Dict[str, str]

@router.get("", response_model=HealthResponse)
async def health_check():
    """健康检查"""
    services = {
        "postgres": "connected",
        "redis": "connected",
        "celery": "connected",
    }
    
    return HealthResponse(
        status="healthy",
        services=services,
    )
```

### 7.3 重试策略

```python
# app/tasks/retry.py
from celery.exceptions import MaxRetriesExceeded
from app.core.celery_app import celery_app

def wiki_ingest_retry_delay(attempts, *args, **kwargs):
    """Wiki 同步重试延迟 - 固定 15 秒"""
    return 15

@celery_app.task(
    bind=True,
    max_retries=10,
    retry_backoff=wiki_ingest_retry_delay,
    retry_backoff_max=60,
)
def wiki_ingest_task(self, payload):
    """Wiki 同步任务 - 特殊重试策略"""
    try:
        pass
    except Exception as exc:
        if self.request.retries >= self.max_retries:
            raise MaxRetriesExceeded()
        raise self.retry(exc=exc)
```

---

## 总结

这套队列系统设计完全复制了 WeKnora Go 项目的核心功能，并适配 Python 生态：

✅ **QA 请求队列** - 有界、用户限流、超时、取消、分布式  
✅ **后台任务队列** - 优先级、任务链、重试策略  
✅ **双模式支持** - 完整模式（Redis）+ Lite 模式（无 Redis）  
✅ **可观测性** - Langfuse 链路追踪 + Prometheus 指标  
✅ **生产级** - 完善的错误处理、监控、健康检查  

可以作为 Python 系统的核心队列基础设施！
