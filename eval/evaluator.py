"""
RAG 系统评估器 - 支持高级评估指标
"""
import json
import sys
import math
from pathlib import Path
from typing import List, Dict, Optional, Set
from datetime import datetime

# 添加父目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from qa.chain import QAChatChain
from retriever.vector_store import VectorStore
from utils.logger import logger


def compute_precision_at_k(relevant_items: Set[str], retrieved_items: List[str], k: int) -> float:
    """
    计算 Precision@K

    Args:
        relevant_items: 相关项集合（期望文件）
        retrieved_items: 检索结果列表（按排名顺序）
        k: 截断位置

    Returns:
        Precision@K 值 (0-1)
    """
    if k <= 0:
        return 0.0

    top_k = retrieved_items[:k]
    relevant_in_top_k = sum(1 for item in top_k if any(rel in item for rel in relevant_items))
    return relevant_in_top_k / k


def compute_recall_at_k(relevant_items: Set[str], retrieved_items: List[str], k: int) -> float:
    """
    计算 Recall@K

    Args:
        relevant_items: 相关项集合
        retrieved_items: 检索结果列表
        k: 截断位置

    Returns:
        Recall@K 值 (0-1)
    """
    if not relevant_items:
        return 0.0

    top_k = retrieved_items[:k]
    relevant_in_top_k = sum(1 for item in top_k if any(rel in item for rel in relevant_items))
    return relevant_in_top_k / len(relevant_items)


def compute_mrr(relevant_items: Set[str], retrieved_items: List[str]) -> float:
    """
    计算 MRR (Mean Reciprocal Rank)

    找到第一个相关文档的排名，计算其倒数

    Args:
        relevant_items: 相关项集合
        retrieved_items: 检索结果列表

    Returns:
        MRR 值 (0-1)
    """
    for rank, item in enumerate(retrieved_items, start=1):
        if any(rel in item for rel in relevant_items):
            return 1.0 / rank
    return 0.0


def compute_ndcg_at_k(relevant_items: Set[str], retrieved_items: List[str], k: int) -> float:
    """
    计算 NDCG@K (Normalized Discounted Cumulative Gain)

    使用二元相关性（相关=1，不相关=0）

    Args:
        relevant_items: 相关项集合
        retrieved_items: 检索结果列表
        k: 截断位置

    Returns:
        NDCG@K 值 (0-1)
    """
    if k <= 0 or not relevant_items:
        return 0.0

    # 计算 DCG@K
    dcg = 0.0
    for i, item in enumerate(retrieved_items[:k], start=1):
        rel = 1.0 if any(rel_item in item for rel_item in relevant_items) else 0.0
        dcg += rel / math.log2(i + 1)

    # 计算 IDCG@K（理想排序的 DCG）
    # 假设所有相关文档都排在前面
    num_relevant = min(len(relevant_items), k)
    idcg = sum(1.0 / math.log2(i + 1) for i in range(1, num_relevant + 1))

    if idcg == 0:
        return 0.0

    return dcg / idcg


def compute_map(relevant_items: Set[str], retrieved_items: List[str]) -> float:
    """
    计算 MAP (Mean Average Precision)

    Args:
        relevant_items: 相关项集合
        retrieved_items: 检索结果列表

    Returns:
        AP (Average Precision) 值 (0-1)
    """
    if not relevant_items:
        return 0.0

    relevant_count = 0
    precision_sum = 0.0

    for rank, item in enumerate(retrieved_items, start=1):
        if any(rel in item for rel in relevant_items):
            relevant_count += 1
            precision_sum += relevant_count / rank

    if relevant_count == 0:
        return 0.0

    return precision_sum / len(relevant_items)


class RAGEvaluator:
    """RAG 评估器"""
    
    def __init__(self):
        self.qa_chain = QAChatChain()
        self.vector_store = VectorStore()
        self.results = []
    
    def load_test_cases(self, file_path: Path = None) -> List[Dict]:
        """加载测试用例"""
        if file_path is None:
            file_path = Path(__file__).parent / "test_cases.json"
        
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def evaluate_retrieval(self, test_case: Dict, retrieved_results: List[Dict], top_k: int = 5) -> Dict:
        """
        评估检索质量 - 包含高级指标

        Args:
            test_case: 测试用例
            retrieved_results: 检索结果
            top_k: 用于计算 @K 指标的 K 值

        Returns:
            包含基础和高级检索指标的字典
        """
        expected_files = set(test_case.get("expected_files", []))
        expected_keywords = test_case.get("expected_keywords", [])

        # 检索到的文件路径列表（按排名顺序）
        retrieved_files = [r.get("file_path", "") for r in retrieved_results]

        # 基础指标：文件命中
        file_hits = []
        for exp_file in expected_files:
            matched = [f for f in retrieved_files if exp_file in f]
            if matched:
                file_hits.append({"expected": exp_file, "matched": matched[0]})

        file_recall = len(file_hits) / len(expected_files) if expected_files else 0

        # 检查关键词覆盖
        all_content = " ".join([r.get("content", "") for r in retrieved_results])
        keyword_hits = [kw for kw in expected_keywords if kw in all_content]
        keyword_coverage = len(keyword_hits) / len(expected_keywords) if expected_keywords else 0

        # ========== 高级评估指标 ==========

        # MRR (Mean Reciprocal Rank)
        mrr = compute_mrr(expected_files, retrieved_files)

        # Precision@K
        precision_at_1 = compute_precision_at_k(expected_files, retrieved_files, 1)
        precision_at_3 = compute_precision_at_k(expected_files, retrieved_files, 3)
        precision_at_5 = compute_precision_at_k(expected_files, retrieved_files, 5)

        # Recall@K
        recall_at_1 = compute_recall_at_k(expected_files, retrieved_files, 1)
        recall_at_3 = compute_recall_at_k(expected_files, retrieved_files, 3)
        recall_at_5 = compute_recall_at_k(expected_files, retrieved_files, 5)

        # NDCG@K
        ndcg_at_3 = compute_ndcg_at_k(expected_files, retrieved_files, 3)
        ndcg_at_5 = compute_ndcg_at_k(expected_files, retrieved_files, 5)
        ndcg_at_10 = compute_ndcg_at_k(expected_files, retrieved_files, 10)

        # MAP (Mean Average Precision)
        average_precision = compute_map(expected_files, retrieved_files)

        return {
            # 基础指标
            "file_recall": file_recall,
            "file_hits": file_hits,
            "keyword_coverage": keyword_coverage,
            "keyword_hits": keyword_hits,
            "retrieved_count": len(retrieved_results),
            "avg_score": sum(r.get("score", 0) for r in retrieved_results) / len(retrieved_results) if retrieved_results else 0,

            # 高级指标
            "mrr": mrr,
            "precision_at_1": precision_at_1,
            "precision_at_3": precision_at_3,
            "precision_at_5": precision_at_5,
            "recall_at_1": recall_at_1,
            "recall_at_3": recall_at_3,
            "recall_at_5": recall_at_5,
            "ndcg_at_3": ndcg_at_3,
            "ndcg_at_5": ndcg_at_5,
            "ndcg_at_10": ndcg_at_10,
            "map": average_precision,
        }
    
    def evaluate_answer(self, test_case: Dict, answer: str) -> Dict:
        """评估答案质量"""
        expected_keywords = test_case.get("expected_keywords", [])
        
        # 检查答案中是否包含期望的关键词
        keyword_hits = [kw for kw in expected_keywords if kw in answer]
        keyword_coverage = len(keyword_hits) / len(expected_keywords) if expected_keywords else 0
        
        # 检查是否拒绝回答（没有找到相关信息）
        refusal_phrases = ["无法找到", "没有找到", "不确定", "无法回答"]
        is_refusal = any(phrase in answer for phrase in refusal_phrases)
        
        return {
            "keyword_coverage": keyword_coverage,
            "keyword_hits": keyword_hits,
            "is_refusal": is_refusal,
            "answer_length": len(answer)
        }
    
    def evaluate_test_case(self, test_case: Dict) -> Dict:
        """评估单个测试用例"""
        question = test_case["question"]
        logger.info(f"评估问题: {question}")
        
        # 执行检索
        retrieved_results = self.vector_store.search(question, top_k=5)
        
        # 评估检索质量
        retrieval_metrics = self.evaluate_retrieval(test_case, retrieved_results)
        
        # 执行问答
        qa_result = self.qa_chain.query(question, use_history=False)
        answer = qa_result["answer"]
        
        # 评估答案质量
        answer_metrics = self.evaluate_answer(test_case, answer)
        
        result = {
            "test_case_id": test_case["id"],
            "question": question,
            "category": test_case.get("category", "unknown"),
            "answer": answer,
            "sources": qa_result["sources"],
            "retrieval_metrics": retrieval_metrics,
            "answer_metrics": answer_metrics,
            "timestamp": datetime.now().isoformat()
        }
        
        return result
    
    def evaluate_all(self, output_file: Path = None) -> Dict:
        """评估所有测试用例"""
        test_cases = self.load_test_cases()
        logger.info(f"加载 {len(test_cases)} 个测试用例")
        
        results = []
        for test_case in test_cases:
            try:
                result = self.evaluate_test_case(test_case)
                results.append(result)
                
                # 打印简要结果
                rm = result['retrieval_metrics']
                print(f"\n问题 {test_case['id']}: {test_case['question']}")
                print(f"  检索质量: 文件召回={rm['file_recall']:.2f}, "
                      f"关键词覆盖={rm['keyword_coverage']:.2f}")
                print(f"  高级指标: MRR={rm['mrr']:.3f}, P@5={rm['precision_at_5']:.3f}, "
                      f"NDCG@5={rm['ndcg_at_5']:.3f}")
                print(f"  答案质量: 关键词覆盖={result['answer_metrics']['keyword_coverage']:.2f}")
                
            except Exception as e:
                logger.error(f"评估测试用例 {test_case['id']} 失败: {e}")
                results.append({
                    "test_case_id": test_case["id"],
                    "error": str(e)
                })
        
        # 计算汇总指标
        valid_results = [r for r in results if "error" not in r]
        n = len(valid_results) if valid_results else 1  # 避免除零

        summary = {
            "total_cases": len(test_cases),
            "successful_cases": len(valid_results),
            "failed_cases": len(results) - len(valid_results),

            # 基础指标
            "avg_file_recall": sum(r["retrieval_metrics"]["file_recall"] for r in valid_results) / n if valid_results else 0,
            "avg_keyword_coverage_retrieval": sum(r["retrieval_metrics"]["keyword_coverage"] for r in valid_results) / n if valid_results else 0,
            "avg_keyword_coverage_answer": sum(r["answer_metrics"]["keyword_coverage"] for r in valid_results) / n if valid_results else 0,
            "refusal_rate": sum(1 for r in valid_results if r["answer_metrics"]["is_refusal"]) / n if valid_results else 0,

            # 高级检索指标
            "mrr": sum(r["retrieval_metrics"]["mrr"] for r in valid_results) / n if valid_results else 0,
            "map": sum(r["retrieval_metrics"]["map"] for r in valid_results) / n if valid_results else 0,
            "precision_at_1": sum(r["retrieval_metrics"]["precision_at_1"] for r in valid_results) / n if valid_results else 0,
            "precision_at_3": sum(r["retrieval_metrics"]["precision_at_3"] for r in valid_results) / n if valid_results else 0,
            "precision_at_5": sum(r["retrieval_metrics"]["precision_at_5"] for r in valid_results) / n if valid_results else 0,
            "recall_at_1": sum(r["retrieval_metrics"]["recall_at_1"] for r in valid_results) / n if valid_results else 0,
            "recall_at_3": sum(r["retrieval_metrics"]["recall_at_3"] for r in valid_results) / n if valid_results else 0,
            "recall_at_5": sum(r["retrieval_metrics"]["recall_at_5"] for r in valid_results) / n if valid_results else 0,
            "ndcg_at_3": sum(r["retrieval_metrics"]["ndcg_at_3"] for r in valid_results) / n if valid_results else 0,
            "ndcg_at_5": sum(r["retrieval_metrics"]["ndcg_at_5"] for r in valid_results) / n if valid_results else 0,
            "ndcg_at_10": sum(r["retrieval_metrics"]["ndcg_at_10"] for r in valid_results) / n if valid_results else 0,
        }
        
        # 保存结果
        if output_file is None:
            output_file = Path(__file__).parent / f"eval_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        output_data = {
            "summary": summary,
            "results": results,
            "timestamp": datetime.now().isoformat()
        }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"评估结果已保存到: {output_file}")
        
        # 打印汇总
        print("\n" + "=" * 60)
        print("评估汇总")
        print("=" * 60)
        print(f"总测试用例: {summary['total_cases']}")
        print(f"成功: {summary['successful_cases']}, 失败: {summary['failed_cases']}")

        print("\n--- 基础指标 ---")
        print(f"平均文件召回率: {summary['avg_file_recall']:.2%}")
        print(f"平均关键词覆盖（检索）: {summary['avg_keyword_coverage_retrieval']:.2%}")
        print(f"平均关键词覆盖（答案）: {summary['avg_keyword_coverage_answer']:.2%}")
        print(f"拒绝回答率: {summary['refusal_rate']:.2%}")

        print("\n--- 高级检索指标 ---")
        print(f"MRR (Mean Reciprocal Rank): {summary['mrr']:.4f}")
        print(f"MAP (Mean Average Precision): {summary['map']:.4f}")
        print(f"Precision@1: {summary['precision_at_1']:.4f}  |  Recall@1: {summary['recall_at_1']:.4f}")
        print(f"Precision@3: {summary['precision_at_3']:.4f}  |  Recall@3: {summary['recall_at_3']:.4f}")
        print(f"Precision@5: {summary['precision_at_5']:.4f}  |  Recall@5: {summary['recall_at_5']:.4f}")
        print(f"NDCG@3: {summary['ndcg_at_3']:.4f}  |  NDCG@5: {summary['ndcg_at_5']:.4f}  |  NDCG@10: {summary['ndcg_at_10']:.4f}")
        print("=" * 60)
        
        return output_data


if __name__ == "__main__":
    evaluator = RAGEvaluator()
    results = evaluator.evaluate_all()
