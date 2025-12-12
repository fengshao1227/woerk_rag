"""
知识添加任务队列服务

异步处理知识添加请求，避免阻塞 API 响应
"""
import asyncio
import hashlib
import json
import re
from datetime import datetime
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

from utils.logger import logger


@dataclass
class KnowledgeTaskPayload:
    """任务载荷"""
    task_id: str
    content: str
    title: Optional[str]
    category: str
    group_names: Optional[List[str]]
    user_id: int
    username: str
    is_public: bool = False  # 新增：知识是否公开


class KnowledgeTaskQueue:
    """知识添加任务队列

    使用 asyncio.Queue 实现内存队列，后台 worker 异步处理
    """

    def __init__(self, max_workers: int = 3):
        self.queue: asyncio.Queue = asyncio.Queue()
        self.max_workers = max_workers
        self.workers: List[asyncio.Task] = []
        self._running = False

        # 依赖注入（延迟初始化）
        self._llm_client = None
        self._embedding_model = None
        self._qdrant_client = None
        self._collection_name = None

    def set_dependencies(
        self,
        llm_client,
        embedding_model,
        qdrant_client,
        collection_name: str
    ):
        """设置依赖（从 server.py 注入）"""
        self._llm_client = llm_client
        self._embedding_model = embedding_model
        self._qdrant_client = qdrant_client
        self._collection_name = collection_name
        logger.info("任务队列依赖注入完成")

    async def enqueue(self, payload: KnowledgeTaskPayload) -> str:
        """将任务加入队列

        Returns:
            task_id
        """
        await self.queue.put(payload)
        logger.info(f"任务入队: {payload.task_id}, 队列大小: {self.queue.qsize()}")
        return payload.task_id

    async def start_workers(self) -> None:
        """启动后台 worker"""
        if self._running:
            logger.warning("任务队列已在运行")
            return

        self._running = True
        for i in range(self.max_workers):
            worker = asyncio.create_task(self._worker(i))
            self.workers.append(worker)

        logger.info(f"任务队列启动，{self.max_workers} 个 worker 就绪")

    async def stop_workers(self) -> None:
        """停止后台 worker"""
        self._running = False

        # 发送停止信号
        for _ in self.workers:
            await self.queue.put(None)

        # 等待 worker 结束
        if self.workers:
            await asyncio.gather(*self.workers, return_exceptions=True)

        self.workers.clear()
        logger.info("任务队列已停止")

    async def _worker(self, worker_id: int) -> None:
        """Worker 主循环"""
        logger.info(f"Worker-{worker_id} 启动")

        while self._running:
            try:
                # 获取任务（阻塞）
                payload = await self.queue.get()

                # 停止信号
                if payload is None:
                    break

                # 处理任务
                await self._process_task(worker_id, payload)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Worker-{worker_id} 异常: {e}")

        logger.info(f"Worker-{worker_id} 退出")

    async def _process_task(self, worker_id: int, payload: KnowledgeTaskPayload) -> None:
        """处理单个任务"""
        from admin.database import SessionLocal
        from admin.models import KnowledgeTask, KnowledgeEntry, KnowledgeGroup, KnowledgeGroupItem
        from qdrant_client.models import PointStruct

        task_id = payload.task_id
        logger.info(f"Worker-{worker_id} 开始处理任务: {task_id}")

        # 更新状态为 processing
        try:
            with SessionLocal() as db:
                task = db.query(KnowledgeTask).filter(KnowledgeTask.id == task_id).first()
                if task:
                    task.status = 'processing'
                    db.commit()
        except Exception as e:
            logger.error(f"更新任务状态失败: {e}")

        try:
            # 1. LLM 提取关键信息
            extracted_info = await self._extract_info(payload.content)

            # 2. 构建增强内容
            enhanced_content = self._build_enhanced_content(payload, extracted_info)

            # 3. 生成嵌入向量（在线程池中执行同步操作）
            loop = asyncio.get_event_loop()
            embeddings = await loop.run_in_executor(
                None,
                lambda: self._embedding_model.encode([enhanced_content])
            )

            # 4. 生成唯一 ID
            content_hash = hashlib.md5(
                f"{payload.content}:{datetime.now().isoformat()}".encode()
            ).hexdigest()

            # 5. 存储到 Qdrant
            point = PointStruct(
                id=content_hash,
                vector=embeddings[0].tolist(),
                payload={
                    "content": enhanced_content,
                    "original_content": payload.content,
                    "title": extracted_info.get('title', payload.title),
                    "summary": extracted_info.get('summary', ''),
                    "keywords": extracted_info.get('keywords', []),
                    "tech_stack": extracted_info.get('tech_stack', []),
                    "type": "knowledge",
                    "category": extracted_info.get('type', payload.category),
                    "created_at": datetime.now().isoformat(),
                    "file_path": f"knowledge/{content_hash[:8]}",
                    "user_id": payload.user_id,  # 新增：归属用户ID
                    "is_public": payload.is_public  # 新增：是否公开
                }
            )

            self._qdrant_client.upsert(
                collection_name=self._collection_name,
                points=[point]
            )

            # 6. 同步到 MySQL
            with SessionLocal() as db:
                # 写入知识条目
                knowledge_entry = KnowledgeEntry(
                    qdrant_id=content_hash,
                    title=extracted_info.get('title', payload.title),
                    category=extracted_info.get('type', payload.category) or 'general',
                    summary=extracted_info.get('summary', ''),
                    keywords=extracted_info.get('keywords', []),
                    tech_stack=extracted_info.get('tech_stack', []),
                    content_preview=payload.content[:500] if payload.content else None,
                    user_id=payload.user_id,  # 新增：归属用户ID
                    is_public=payload.is_public  # 新增：是否公开
                )
                db.add(knowledge_entry)
                db.commit()

                # 添加到分组
                if payload.group_names:
                    groups = db.query(KnowledgeGroup).filter(
                        KnowledgeGroup.name.in_(payload.group_names),
                        KnowledgeGroup.is_active == True
                    ).all()
                    for group in groups:
                        group_item = KnowledgeGroupItem(
                            group_id=group.id,
                            qdrant_id=content_hash
                        )
                        db.add(group_item)
                    if groups:
                        db.commit()

                # 更新任务状态为完成
                task = db.query(KnowledgeTask).filter(KnowledgeTask.id == task_id).first()
                if task:
                    task.status = 'completed'
                    task.result_id = content_hash
                    db.commit()

            logger.info(f"Worker-{worker_id} 任务完成: {task_id} -> {content_hash}")

        except Exception as e:
            logger.error(f"Worker-{worker_id} 任务失败: {task_id}, 错误: {e}")

            # 更新任务状态为失败
            try:
                with SessionLocal() as db:
                    task = db.query(KnowledgeTask).filter(KnowledgeTask.id == task_id).first()
                    if task:
                        task.status = 'failed'
                        task.error_message = str(e)[:500]
                        db.commit()
            except Exception as db_err:
                logger.error(f"更新失败状态异常: {db_err}")

    async def _extract_info(self, content: str) -> Dict[str, Any]:
        """使用 LLM 提取关键信息"""
        extract_prompt = f"""请分析以下内容，提取关键信息并返回 JSON 格式：

内容：
{content}

请返回以下格式的 JSON（只返回 JSON，不要其他内容）：
{{
    "title": "简洁的标题（如果用户没提供）",
    "summary": "50字以内的摘要",
    "keywords": ["关键词1", "关键词2", "关键词3"],
    "tech_stack": ["涉及的技术栈"],
    "type": "类型（project/skill/experience/note/other）"
}}
"""

        try:
            messages = [{"role": "user", "content": extract_prompt}]

            # 在线程池中执行同步 LLM 调用
            loop = asyncio.get_event_loop()
            llm_result = await loop.run_in_executor(
                None,
                lambda: self._llm_client.invoke(messages)
            )

            response_text = llm_result.content

            # 解析 JSON
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if json_match:
                return json.loads(json_match.group())
        except Exception as e:
            logger.warning(f"LLM 提取失败: {e}")

        # 降级返回默认值
        return {
            "title": "未命名知识",
            "summary": content[:100],
            "keywords": [],
            "tech_stack": [],
            "type": "general"
        }

    def _build_enhanced_content(
        self,
        payload: KnowledgeTaskPayload,
        extracted_info: Dict[str, Any]
    ) -> str:
        """构建增强后的内容"""
        return f"""# {extracted_info.get('title', payload.title or '知识条目')}

## 摘要
{extracted_info.get('summary', '')}

## 关键词
{', '.join(extracted_info.get('keywords', []))}

## 技术栈
{', '.join(extracted_info.get('tech_stack', []))}

## 详细内容
{payload.content}
"""


# 全局单例
_task_queue: Optional[KnowledgeTaskQueue] = None


def get_task_queue(max_workers: int = 3) -> KnowledgeTaskQueue:
    """获取任务队列单例"""
    global _task_queue
    if _task_queue is None:
        _task_queue = KnowledgeTaskQueue(max_workers=max_workers)
    return _task_queue
