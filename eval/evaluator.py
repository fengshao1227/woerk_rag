"""
RAG 系统评估器
"""
import json
import sys
from pathlib import Path
from typing import List, Dict
from datetime import datetime

# 添加父目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from qa.chain import QAChatChain
from retriever.vector_store import VectorStore
from utils.logger import logger


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
    
    def evaluate_retrieval(self, test_case: Dict, retrieved_results: List[Dict]) -> Dict:
        """评估检索质量"""
        expected_files = test_case.get("expected_files", [])
        expected_keywords = test_case.get("expected_keywords", [])
        
        # 检查是否检索到期望的文件
        retrieved_files = [r.get("file_path", "") for r in retrieved_results]
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
        
        return {
            "file_recall": file_recall,
            "file_hits": file_hits,
            "keyword_coverage": keyword_coverage,
            "keyword_hits": keyword_hits,
            "retrieved_count": len(retrieved_results),
            "avg_score": sum(r.get("score", 0) for r in retrieved_results) / len(retrieved_results) if retrieved_results else 0
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
                print(f"\n问题 {test_case['id']}: {test_case['question']}")
                print(f"  检索质量: 文件召回={result['retrieval_metrics']['file_recall']:.2f}, "
                      f"关键词覆盖={result['retrieval_metrics']['keyword_coverage']:.2f}")
                print(f"  答案质量: 关键词覆盖={result['answer_metrics']['keyword_coverage']:.2f}")
                
            except Exception as e:
                logger.error(f"评估测试用例 {test_case['id']} 失败: {e}")
                results.append({
                    "test_case_id": test_case["id"],
                    "error": str(e)
                })
        
        # 计算汇总指标
        valid_results = [r for r in results if "error" not in r]
        
        summary = {
            "total_cases": len(test_cases),
            "successful_cases": len(valid_results),
            "failed_cases": len(results) - len(valid_results),
            "avg_file_recall": sum(r["retrieval_metrics"]["file_recall"] for r in valid_results) / len(valid_results) if valid_results else 0,
            "avg_keyword_coverage_retrieval": sum(r["retrieval_metrics"]["keyword_coverage"] for r in valid_results) / len(valid_results) if valid_results else 0,
            "avg_keyword_coverage_answer": sum(r["answer_metrics"]["keyword_coverage"] for r in valid_results) / len(valid_results) if valid_results else 0,
            "refusal_rate": sum(1 for r in valid_results if r["answer_metrics"]["is_refusal"]) / len(valid_results) if valid_results else 0
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
        print(f"平均文件召回率: {summary['avg_file_recall']:.2%}")
        print(f"平均关键词覆盖（检索）: {summary['avg_keyword_coverage_retrieval']:.2%}")
        print(f"平均关键词覆盖（答案）: {summary['avg_keyword_coverage_answer']:.2%}")
        print(f"拒绝回答率: {summary['refusal_rate']:.2%}")
        print("=" * 60)
        
        return output_data


if __name__ == "__main__":
    evaluator = RAGEvaluator()
    results = evaluator.evaluate_all()
