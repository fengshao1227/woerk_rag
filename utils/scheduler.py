"""
定时索引调度器 - 使用 APScheduler 定时执行增量索引
"""
import threading
from datetime import datetime
from typing import Dict, Optional, Callable

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR, JobExecutionEvent

from config import (
    SCHEDULER_ENABLE,
    SCHEDULER_INTERVAL_MINUTES,
    SCHEDULER_INDEX_CODE,
    SCHEDULER_INDEX_DOCS,
    SCHEDULER_INDEX_ON_STARTUP,
    PROJECT_ROOT,
    CODE_PATTERNS,
    IGNORE_PATTERNS,
)
from utils.logger import logger


class IndexScheduler:
    """定时索引调度器"""

    _instance: Optional["IndexScheduler"] = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True

        self._scheduler: Optional[BackgroundScheduler] = None
        self._is_running = False
        self._last_run_time: Optional[datetime] = None
        self._last_run_result: Optional[Dict] = None
        self._job_id = "incremental_index_job"
        self._is_indexing = False  # 防止并发索引

    def _create_scheduler(self) -> BackgroundScheduler:
        """创建调度器实例"""
        scheduler = BackgroundScheduler(
            job_defaults={
                'coalesce': True,  # 合并错过的任务
                'max_instances': 1,  # 同时只运行一个实例
                'misfire_grace_time': 60 * 5,  # 允许 5 分钟的延迟
            }
        )
        scheduler.add_listener(self._job_listener, EVENT_JOB_EXECUTED | EVENT_JOB_ERROR)
        return scheduler

    def _job_listener(self, event: JobExecutionEvent):
        """任务执行监听器"""
        if event.job_id != self._job_id:
            return

        if event.exception:
            logger.error(f"定时索引任务失败: {event.exception}")
            self._last_run_result = {
                "success": False,
                "error": str(event.exception),
                "time": datetime.now().isoformat()
            }
        else:
            logger.info("定时索引任务完成")

    def _run_incremental_index(self) -> Dict:
        """
        执行增量索引任务

        Returns:
            索引统计结果
        """
        if self._is_indexing:
            logger.warning("索引任务正在执行中，跳过本次调度")
            return {"skipped": True, "reason": "already_running"}

        self._is_indexing = True
        self._last_run_time = datetime.now()

        try:
            # 延迟导入避免循环依赖
            from pathlib import Path
            from indexer.code_indexer import CodeIndexer
            from indexer.doc_indexer import DocumentIndexer
            from indexer.incremental import get_incremental_indexer

            logger.info("=" * 50)
            logger.info("[调度器] 开始执行定时增量索引...")

            incremental_indexer = get_incremental_indexer()
            total_stats = {
                "start_time": self._last_run_time.isoformat(),
                "code": {"files": 0, "chunks": 0, "errors": 0, "skipped": False},
                "docs": {"files": 0, "chunks": 0, "errors": 0, "skipped": False},
            }

            # ===================== 索引代码 =====================
            if SCHEDULER_INDEX_CODE:
                logger.info("[调度器] 开始索引代码库...")
                code_indexer = CodeIndexer()

                # 查找代码文件
                code_files = self._find_code_files(Path(PROJECT_ROOT))
                logger.info(f"[调度器] 找到 {len(code_files)} 个代码文件")

                new_files, modified_files, deleted_files = incremental_indexer.get_changed_files(
                    code_files, force_reindex=False
                )
                files_to_index = new_files + modified_files

                if files_to_index:
                    logger.info(f"[调度器] 代码需要索引: 新增 {len(new_files)}, 修改 {len(modified_files)}")

                    for file_path in files_to_index:
                        try:
                            chunks_count = code_indexer.index_file(Path(file_path))
                            if chunks_count > 0:
                                total_stats["code"]["files"] += 1
                                total_stats["code"]["chunks"] += chunks_count
                                incremental_indexer.mark_indexed(file_path)
                        except Exception as e:
                            logger.error(f"[调度器] 索引代码文件失败 {file_path}: {e}")
                            total_stats["code"]["errors"] += 1

                    # 处理删除的文件
                    for file_path in deleted_files:
                        qdrant_ids = incremental_indexer.mark_deleted(file_path)
                        if qdrant_ids:
                            logger.info(f"[调度器] 文件已删除: {file_path}")
                else:
                    logger.info("[调度器] 代码库无变更")
                    total_stats["code"]["skipped"] = True
            else:
                total_stats["code"]["skipped"] = True
                total_stats["code"]["reason"] = "disabled"

            # ===================== 索引文档 =====================
            if SCHEDULER_INDEX_DOCS:
                logger.info("[调度器] 开始索引文档...")
                doc_indexer = DocumentIndexer()

                # 查找文档文件
                doc_files = self._find_doc_files(Path(PROJECT_ROOT))
                logger.info(f"[调度器] 找到 {len(doc_files)} 个文档文件")

                new_files, modified_files, deleted_files = incremental_indexer.get_changed_files(
                    doc_files, force_reindex=False
                )
                files_to_index = new_files + modified_files

                if files_to_index:
                    logger.info(f"[调度器] 文档需要索引: 新增 {len(new_files)}, 修改 {len(modified_files)}")

                    for file_path in files_to_index:
                        try:
                            chunks_count = doc_indexer.index_file(Path(file_path))
                            if chunks_count > 0:
                                total_stats["docs"]["files"] += 1
                                total_stats["docs"]["chunks"] += chunks_count
                                incremental_indexer.mark_indexed(file_path)
                        except Exception as e:
                            logger.error(f"[调度器] 索引文档文件失败 {file_path}: {e}")
                            total_stats["docs"]["errors"] += 1

                    # 处理删除的文件
                    for file_path in deleted_files:
                        qdrant_ids = incremental_indexer.mark_deleted(file_path)
                        if qdrant_ids:
                            logger.info(f"[调度器] 文件已删除: {file_path}")
                else:
                    logger.info("[调度器] 文档库无变更")
                    total_stats["docs"]["skipped"] = True
            else:
                total_stats["docs"]["skipped"] = True
                total_stats["docs"]["reason"] = "disabled"

            # 汇总
            total_stats["end_time"] = datetime.now().isoformat()
            total_stats["total_files"] = total_stats["code"]["files"] + total_stats["docs"]["files"]
            total_stats["total_chunks"] = total_stats["code"]["chunks"] + total_stats["docs"]["chunks"]
            total_stats["total_errors"] = total_stats["code"]["errors"] + total_stats["docs"]["errors"]
            total_stats["success"] = True

            logger.info(f"[调度器] 增量索引完成: 文件 {total_stats['total_files']}, "
                       f"chunks {total_stats['total_chunks']}, 错误 {total_stats['total_errors']}")

            self._last_run_result = total_stats
            return total_stats

        except Exception as e:
            logger.error(f"[调度器] 增量索引任务异常: {e}", exc_info=True)
            self._last_run_result = {
                "success": False,
                "error": str(e),
                "time": datetime.now().isoformat()
            }
            return self._last_run_result

        finally:
            self._is_indexing = False

    def _find_code_files(self, root_path) -> list:
        """查找代码文件"""
        code_files = []
        for pattern in CODE_PATTERNS:
            pattern = pattern.strip()
            for file_path in root_path.rglob(pattern):
                if file_path.is_file():
                    path_str = str(file_path)
                    should_ignore = False
                    for ignore in IGNORE_PATTERNS:
                        ignore = ignore.strip().rstrip('/')
                        if ignore in path_str:
                            should_ignore = True
                            break
                    if not should_ignore:
                        code_files.append(path_str)
        return code_files

    def _find_doc_files(self, root_path) -> list:
        """查找文档文件"""
        doc_files = []
        patterns = ['*.md', '*.txt', '*.html', '*.htm', '*.pdf', '*.docx', '*.doc']
        for pattern in patterns:
            for file_path in root_path.rglob(pattern):
                if file_path.is_file():
                    path_str = str(file_path)
                    should_ignore = False
                    for ignore in IGNORE_PATTERNS:
                        ignore = ignore.strip().rstrip('/')
                        if ignore in path_str:
                            should_ignore = True
                            break
                    if not should_ignore:
                        doc_files.append(path_str)
        return doc_files

    def start(self, run_immediately: bool = None):
        """
        启动调度器

        Args:
            run_immediately: 是否立即执行一次，None 时使用配置
        """
        if self._is_running:
            logger.warning("调度器已在运行中")
            return

        if not SCHEDULER_ENABLE:
            logger.info("定时索引调度器已禁用 (SCHEDULER_ENABLE=0)")
            return

        self._scheduler = self._create_scheduler()

        # 添加定时任务
        self._scheduler.add_job(
            func=self._run_incremental_index,
            trigger=IntervalTrigger(minutes=SCHEDULER_INTERVAL_MINUTES),
            id=self._job_id,
            name="增量索引任务",
            replace_existing=True,
        )

        self._scheduler.start()
        self._is_running = True

        logger.info(f"定时索引调度器已启动，间隔 {SCHEDULER_INTERVAL_MINUTES} 分钟")

        # 是否立即执行
        if run_immediately is None:
            run_immediately = SCHEDULER_INDEX_ON_STARTUP

        if run_immediately:
            logger.info("启动时立即执行一次索引...")
            # 使用线程执行，避免阻塞启动
            thread = threading.Thread(target=self._run_incremental_index, daemon=True)
            thread.start()

    def stop(self):
        """停止调度器"""
        if not self._is_running or self._scheduler is None:
            logger.warning("调度器未运行")
            return

        self._scheduler.shutdown(wait=False)
        self._scheduler = None
        self._is_running = False
        logger.info("定时索引调度器已停止")

    def trigger_now(self) -> Dict:
        """
        立即触发一次索引

        Returns:
            索引结果
        """
        if self._is_indexing:
            return {"success": False, "error": "索引任务正在执行中"}

        logger.info("手动触发增量索引...")
        return self._run_incremental_index()

    def get_status(self) -> Dict:
        """
        获取调度器状态

        Returns:
            状态信息
        """
        status = {
            "enabled": SCHEDULER_ENABLE,
            "running": self._is_running,
            "is_indexing": self._is_indexing,
            "interval_minutes": SCHEDULER_INTERVAL_MINUTES,
            "index_code": SCHEDULER_INDEX_CODE,
            "index_docs": SCHEDULER_INDEX_DOCS,
            "last_run_time": self._last_run_time.isoformat() if self._last_run_time else None,
            "last_run_result": self._last_run_result,
        }

        if self._is_running and self._scheduler:
            job = self._scheduler.get_job(self._job_id)
            if job and job.next_run_time:
                status["next_run_time"] = job.next_run_time.isoformat()

        return status

    def update_interval(self, minutes: int):
        """
        更新索引间隔

        Args:
            minutes: 新的间隔（分钟）
        """
        if minutes < 1:
            raise ValueError("间隔必须大于等于 1 分钟")

        if self._is_running and self._scheduler:
            self._scheduler.reschedule_job(
                self._job_id,
                trigger=IntervalTrigger(minutes=minutes)
            )
            logger.info(f"索引间隔已更新为 {minutes} 分钟")


# 全局实例
_scheduler_instance: Optional[IndexScheduler] = None


def get_scheduler() -> IndexScheduler:
    """获取调度器单例"""
    global _scheduler_instance
    if _scheduler_instance is None:
        _scheduler_instance = IndexScheduler()
    return _scheduler_instance


def start_scheduler(run_immediately: bool = None):
    """启动调度器"""
    scheduler = get_scheduler()
    scheduler.start(run_immediately=run_immediately)


def stop_scheduler():
    """停止调度器"""
    scheduler = get_scheduler()
    scheduler.stop()
