"""
CLI 问答交互
"""
import sys
from pathlib import Path

# 添加父目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from qa.chain import QAChatChain
from utils.logger import logger


def main():
    """CLI 交互主函数"""
    print("=" * 60)
    print("RAG 问答系统 - CLI 模式")
    print("输入 'quit' 或 'exit' 退出")
    print("输入 'clear' 清空对话历史")
    print("=" * 60)
    print()
    
    chain = QAChatChain()
    
    while True:
        try:
            question = input("\n> ").strip()
            
            if not question:
                continue
            
            if question.lower() in ['quit', 'exit', 'q']:
                print("再见！")
                break
            
            if question.lower() == 'clear':
                chain.clear_history()
                print("对话历史已清空")
                continue
            
            # 执行问答
            result = chain.query(question)
            
            # 显示答案
            print("\n[回答]")
            print(result["answer"])
            
            # 显示来源
            if result["sources"]:
                print(f"\n[参考来源 ({result['retrieved_count']} 个)]")
                for i, source in enumerate(result["sources"], 1):
                    print(f"{i}. {source['file_path']} (相似度: {source['score']:.3f})")
                    print(f"   {source['preview']}")
            
        except KeyboardInterrupt:
            print("\n\n再见！")
            break
        except Exception as e:
            logger.error(f"处理问题时出错: {e}")
            print(f"错误: {e}")


if __name__ == "__main__":
    main()
