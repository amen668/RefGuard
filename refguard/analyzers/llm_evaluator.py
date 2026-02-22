"""LLM citation relevance evaluator (optional). Supports DashScope/Qwen."""
import json
import re
from dataclasses import dataclass
from enum import Enum
from typing import Optional

import requests

from refguard.core import settings, get_logger

logger = get_logger(__name__)


class LLMBackend(Enum):
    DASHSCOPE = "dashscope"  # Alibaba Qwen
    OPENAI = "openai"


@dataclass
class EvaluationResult:
    entry_key: str
    relevance_score: int  # 1-5
    is_relevant: bool
    explanation: str
    context_used: str
    abstract_used: str
    error: Optional[str] = None


PROMPT_TEMPLATE = """你是学术写作审查助手。请判断以下引用是否与正文主张相关，并给出JSON结果。

【正文引用上下文】
{context}

【被引文献元数据】
Title: {title}
Authors: {authors}
Year: {year}

【被引文献摘要】
{abstract_or_surrogate}

输出严格JSON：
{{
  "relevance_score": 1-5,
  "is_relevant": true/false,
  "explanation": "不超过120字"
}}
"""


class LLMEvaluator:
    """Evaluate citation relevance only (no integrity/identity decision)."""

    def __init__(
        self,
        backend: LLMBackend = LLMBackend.DASHSCOPE,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
    ) -> None:
        self.backend = backend
        self.api_key = api_key or getattr(settings, "dashscope_api_key", None) or getattr(settings, "DASHSCOPE_API_KEY", None)
        if backend == LLMBackend.DASHSCOPE:
            self.endpoint = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
            self.model = model or "qwen-turbo"
        else:
            self.endpoint = "https://api.openai.com/v1/chat/completions"
            self.model = model or "gpt-3.5-turbo"

    def evaluate(
        self,
        entry_key: str,
        context: str,
        abstract_or_surrogate: str,
        title: str = "",
        authors: str = "",
        year: str = "",
    ) -> EvaluationResult:
        if not context:
            return EvaluationResult(
                entry_key=entry_key,
                relevance_score=0,
                is_relevant=False,
                explanation="Missing context",
                context_used=context,
                abstract_used=abstract_or_surrogate,
                error="missing_context",
            )
        if not abstract_or_surrogate:
            abstract_or_surrogate = f"Title: {title}; Authors: {authors}; Year: {year}"
        prompt = PROMPT_TEMPLATE.format(
            context=context,
            title=title,
            authors=authors,
            year=year,
            abstract_or_surrogate=abstract_or_surrogate or "(no abstract)",
        )
        try:
            if self.backend == LLMBackend.DASHSCOPE:
                text = self._call_dashscope(prompt)
            else:
                text = self._call_openai_compatible(prompt)
            return self._parse_response(entry_key, text, context, abstract_or_surrogate)
        except Exception as e:
            logger.warning("LLM evaluate failed for %s: %s", entry_key, e)
            return EvaluationResult(
                entry_key=entry_key,
                relevance_score=0,
                is_relevant=False,
                explanation="",
                context_used=context,
                abstract_used=abstract_or_surrogate,
                error=str(e),
            )

    def _call_dashscope(self, prompt: str) -> str:
        if not self.api_key:
            raise ValueError("DASHSCOPE_API_KEY required for Qwen")
        r = requests.post(
            self.endpoint,
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            json={"model": self.model, "messages": [{"role": "user", "content": prompt}], "temperature": 0.1, "max_tokens": 500},
            timeout=60,
        )
        r.raise_for_status()
        data = r.json()
        return data.get("choices", [{}])[0].get("message", {}).get("content", "")

    def _call_openai_compatible(self, prompt: str) -> str:
        r = requests.post(
            self.endpoint,
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            json={"model": self.model, "messages": [{"role": "user", "content": prompt}], "temperature": 0.1, "max_tokens": 500},
            timeout=60,
        )
        r.raise_for_status()
        data = r.json()
        return data.get("choices", [{}])[0].get("message", {}).get("content", "")

    def _parse_response(self, entry_key: str, text: str, context: str, abstract: str) -> EvaluationResult:
        try:
            # Extract JSON block
            m = re.search(r"\{[^{}]*\"relevance_score\"[^{}]*\}", text, re.DOTALL)
            if m:
                text = m.group(0)
            data = json.loads(text)
            score = int(data.get("relevance_score", 0))
            score = max(1, min(5, score))
            is_rel = data.get("is_relevant", score >= 3)
            if isinstance(is_rel, str):
                is_rel = is_rel.lower() in ("true", "1", "yes")
            return EvaluationResult(
                entry_key=entry_key,
                relevance_score=score,
                is_relevant=is_rel,
                explanation=str(data.get("explanation", ""))[:500],
                context_used=context,
                abstract_used=abstract,
            )
        except (json.JSONDecodeError, ValueError) as e:
            return EvaluationResult(
                entry_key=entry_key,
                relevance_score=0,
                is_relevant=False,
                explanation="",
                context_used=context,
                abstract_used=abstract,
                error=f"Parse error: {e}",
            )
