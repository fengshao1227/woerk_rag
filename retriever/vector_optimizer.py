"""
向量索引优化器
- HNSW 参数调优
- 批量写入优化
- 索引预热
"""
import time
from typing import Optional
from qdrant_client import QdrantClient
from qdrant_client.models import (
    OptimizersConfigDiff,
    HnswConfigDiff,
    VectorParams,
    Distance,
)
from utils.logger import logger
from config import (
    QDRANT_HOST,
    QDRANT_PORT,
    QDRANT_API_KEY,
    QDRANT_COLLECTION_NAME,
)


class VectorIndexOptimizer:
    """向量索引优化器"""

    # HNSW 优化参数配置
    HNSW_CONFIGS = {
        "default": {
            "m": 16,              # 每个节点的连接数
            "ef_construct": 100,  # 构建时的搜索宽度
            "full_scan_threshold": 10000,  # 全扫描阈值
        },
        "high_recall": {
            "m": 32,              # 更多连接，更高召回
            "ef_construct": 200,  # 更大搜索宽度
            "full_scan_threshold": 20000,
        },
        "fast_search": {
            "m": 8,               # 较少连接，更快搜索
            "ef_construct": 64,   # 较小搜索宽度
            "full_scan_threshold": 5000,
        },
        "balanced": {
            "m": 16,
            "ef_construct": 128,
            "full_scan_threshold": 15000,
        },
    }

    def __init__(self):
        """初始化优化器"""
        self.client = QdrantClient(
            host=QDRANT_HOST,
            port=QDRANT_PORT,
            api_key=QDRANT_API_KEY if QDRANT_API_KEY else None,
        )
        self.collection_name = QDRANT_COLLECTION_NAME

    def get_collection_info(self) -> dict:
        """获取集合信息"""
        try:
            info = self.client.get_collection(self.collection_name)
            return {
                "vectors_count": info.vectors_count,
                "points_count": info.points_count,
                "indexed_vectors_count": info.indexed_vectors_count,
                "status": info.status.value,
                "optimizer_status": info.optimizer_status.status.value if info.optimizer_status else "unknown",
                "config": {
                    "vector_size": info.config.params.vectors.size if hasattr(info.config.params.vectors, 'size') else None,
                    "distance": info.config.params.vectors.distance.value if hasattr(info.config.params.vectors, 'distance') else "Cosine",
                },
            }
        except Exception as e:
            logger.error(f"获取集合信息失败: {e}")
            return {}

    def optimize_hnsw(self, profile: str = "balanced") -> bool:
        """
        优化 HNSW 索引参数

        Args:
            profile: 优化配置 (default, high_recall, fast_search, balanced)

        Returns:
            是否成功
        """
        if profile not in self.HNSW_CONFIGS:
            logger.error(f"未知的优化配置: {profile}")
            return False

        config = self.HNSW_CONFIGS[profile]
        logger.info(f"应用 HNSW 优化配置: {profile}")
        logger.info(f"参数: m={config['m']}, ef_construct={config['ef_construct']}")

        try:
            self.client.update_collection(
                collection_name=self.collection_name,
                hnsw_config=HnswConfigDiff(
                    m=config["m"],
                    ef_construct=config["ef_construct"],
                    full_scan_threshold=config["full_scan_threshold"],
                ),
            )
            logger.info("HNSW 参数更新成功")
            return True
        except Exception as e:
            logger.error(f"HNSW 参数更新失败: {e}")
            return False

    def optimize_indexing(self,
                          indexing_threshold: int = 20000,
                          memmap_threshold: int = 50000) -> bool:
        """
        优化索引配置

        Args:
            indexing_threshold: 索引阈值（向量数量超过此值才建立索引）
            memmap_threshold: 内存映射阈值

        Returns:
            是否成功
        """
        logger.info(f"优化索引配置: indexing_threshold={indexing_threshold}")

        try:
            self.client.update_collection(
                collection_name=self.collection_name,
                optimizers_config=OptimizersConfigDiff(
                    indexing_threshold=indexing_threshold,
                    memmap_threshold=memmap_threshold,
                ),
            )
            logger.info("索引配置更新成功")
            return True
        except Exception as e:
            logger.error(f"索引配置更新失败: {e}")
            return False

    def trigger_optimization(self) -> bool:
        """
        触发索引优化（重建索引）

        Returns:
            是否成功
        """
        logger.info("触发索引优化...")

        try:
            # 通过更新优化器配置触发重建
            self.client.update_collection(
                collection_name=self.collection_name,
                optimizers_config=OptimizersConfigDiff(
                    indexing_threshold=0,  # 立即触发索引
                ),
            )
            logger.info("索引优化已触发")
            return True
        except Exception as e:
            logger.error(f"触发索引优化失败: {e}")
            return False

    def wait_for_optimization(self, timeout: int = 300) -> bool:
        """
        等待优化完成

        Args:
            timeout: 超时时间（秒）

        Returns:
            是否完成
        """
        logger.info(f"等待索引优化完成（超时: {timeout}秒）...")

        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                info = self.client.get_collection(self.collection_name)
                status = info.optimizer_status.status.value if info.optimizer_status else "unknown"

                if status == "ok":
                    logger.info("索引优化完成")
                    return True

                logger.debug(f"优化状态: {status}")
                time.sleep(2)
            except Exception as e:
                logger.error(f"检查优化状态失败: {e}")
                time.sleep(5)

        logger.warning("索引优化超时")
        return False

    def warmup_index(self, sample_queries: int = 100) -> dict:
        """
        预热索引（通过执行示例查询）

        Args:
            sample_queries: 示例查询数量

        Returns:
            预热统计
        """
        import numpy as np

        logger.info(f"开始预热索引（{sample_queries} 次查询）...")

        stats = {
            "queries": 0,
            "total_time": 0,
            "avg_time": 0,
            "min_time": float('inf'),
            "max_time": 0,
        }

        try:
            # 从集合配置获取向量维度
            info = self.get_collection_info()
            vector_size = info.get("config", {}).get("vector_size")
            if not vector_size:
                logger.warning("无法获取向量维度，跳过预热")
                return stats

            for i in range(sample_queries):
                # 生成随机查询向量
                query_vector = np.random.rand(vector_size).tolist()

                start = time.time()
                self.client.search(
                    collection_name=self.collection_name,
                    query_vector=query_vector,
                    limit=10,
                )
                elapsed = time.time() - start

                stats["queries"] += 1
                stats["total_time"] += elapsed
                stats["min_time"] = min(stats["min_time"], elapsed)
                stats["max_time"] = max(stats["max_time"], elapsed)

                if (i + 1) % 20 == 0:
                    logger.debug(f"预热进度: {i + 1}/{sample_queries}")

            stats["avg_time"] = stats["total_time"] / stats["queries"] if stats["queries"] > 0 else 0
            stats["min_time"] = stats["min_time"] if stats["min_time"] != float('inf') else 0

            logger.info(f"索引预热完成: 平均延迟 {stats['avg_time']*1000:.2f}ms")
            return stats

        except Exception as e:
            logger.error(f"索引预热失败: {e}")
            return stats

    def get_optimization_recommendations(self) -> list:
        """
        获取优化建议

        Returns:
            建议列表
        """
        recommendations = []

        try:
            info = self.get_collection_info()

            if not info:
                return ["无法获取集合信息，请检查 Qdrant 连接"]

            vectors_count = info.get("vectors_count", 0)

            # 基于向量数量的建议
            if vectors_count < 1000:
                recommendations.append(
                    "向量数量较少（<1000），建议使用 'default' 配置"
                )
            elif vectors_count < 100000:
                recommendations.append(
                    "向量数量中等（1k-100k），建议使用 'balanced' 配置"
                )
            elif vectors_count < 1000000:
                recommendations.append(
                    "向量数量较多（100k-1M），建议使用 'high_recall' 配置并启用内存映射"
                )
            else:
                recommendations.append(
                    "向量数量很大（>1M），建议使用分片部署和 'fast_search' 配置"
                )

            # 索引状态建议
            if info.get("status") != "green":
                recommendations.append(
                    f"集合状态异常: {info.get('status')}，建议检查 Qdrant 日志"
                )

            if info.get("optimizer_status") != "ok":
                recommendations.append(
                    "索引优化未完成，建议等待优化完成后再进行查询"
                )

            # 通用建议
            recommendations.append(
                "建议定期执行索引预热以提升首次查询性能"
            )

            return recommendations

        except Exception as e:
            logger.error(f"获取优化建议失败: {e}")
            return [f"获取建议失败: {e}"]

    def full_optimization(self, profile: str = "balanced") -> dict:
        """
        执行完整优化流程

        Args:
            profile: 优化配置

        Returns:
            优化结果
        """
        logger.info("=" * 50)
        logger.info("开始完整优化流程")
        logger.info("=" * 50)

        result = {
            "success": True,
            "steps": [],
            "recommendations": [],
        }

        # 1. 获取当前状态
        info = self.get_collection_info()
        result["before"] = info
        logger.info(f"当前状态: {info}")

        # 2. 应用 HNSW 优化
        if self.optimize_hnsw(profile):
            result["steps"].append("HNSW 参数优化成功")
        else:
            result["steps"].append("HNSW 参数优化失败")
            result["success"] = False

        # 3. 优化索引配置
        if self.optimize_indexing():
            result["steps"].append("索引配置优化成功")
        else:
            result["steps"].append("索引配置优化失败")

        # 4. 触发优化
        if self.trigger_optimization():
            result["steps"].append("索引优化已触发")

            # 5. 等待优化完成
            if self.wait_for_optimization(timeout=120):
                result["steps"].append("索引优化完成")
            else:
                result["steps"].append("索引优化超时")

        # 6. 预热索引
        warmup_stats = self.warmup_index(sample_queries=50)
        result["warmup"] = warmup_stats
        result["steps"].append(f"索引预热完成，平均延迟: {warmup_stats['avg_time']*1000:.2f}ms")

        # 7. 获取优化后状态
        result["after"] = self.get_collection_info()

        # 8. 获取建议
        result["recommendations"] = self.get_optimization_recommendations()

        logger.info("=" * 50)
        logger.info("优化流程完成")
        logger.info("=" * 50)

        return result


# 便捷函数
def optimize_vector_index(profile: str = "balanced") -> dict:
    """
    优化向量索引（便捷函数）

    Args:
        profile: 优化配置 (default, high_recall, fast_search, balanced)

    Returns:
        优化结果
    """
    optimizer = VectorIndexOptimizer()
    return optimizer.full_optimization(profile)


def get_index_stats() -> dict:
    """获取索引统计信息"""
    optimizer = VectorIndexOptimizer()
    return optimizer.get_collection_info()


if __name__ == "__main__":
    # 测试优化器
    optimizer = VectorIndexOptimizer()

    print("当前集合信息:")
    print(optimizer.get_collection_info())

    print("\n优化建议:")
    for rec in optimizer.get_optimization_recommendations():
        print(f"  - {rec}")
