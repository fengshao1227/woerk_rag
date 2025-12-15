# Eval Module

> [Home](../CLAUDE.md) > Eval

## Overview

Evaluation module for measuring retrieval and answer quality.

## Key Files

| File | Description |
|------|-------------|
| `evaluator.py` | Main evaluation framework |
| `test_cases.json` | Evaluation test cases |

## Evaluator (`evaluator.py`)

### Metrics

#### Retrieval Metrics
- **Precision@K**: Relevant docs in top-K results
- **Recall@K**: Coverage of relevant docs
- **MRR**: Mean Reciprocal Rank
- **NDCG**: Normalized Discounted Cumulative Gain

#### Answer Metrics
- **Relevance**: Answer relevance to question
- **Faithfulness**: Grounded in retrieved context
- **Completeness**: Coverage of key points

### Usage

```python
from eval.evaluator import Evaluator

evaluator = Evaluator()
results = evaluator.run(test_cases)
summary = evaluator.summarize(results)
```

### Test Cases Format

```json
{
  "test_cases": [
    {
      "id": "test_001",
      "question": "What is the project about?",
      "expected_keywords": ["RAG", "knowledge base"],
      "relevant_docs": ["README.md"]
    }
  ]
}
```

## Running Evaluation

```bash
python -m eval.evaluator

# With custom test cases
python -m eval.evaluator --test-file my_tests.json
```

## Dependencies

- Retriever module
- LLM client (for answer evaluation)
