"""Cross-Encoder 重排序器"""
from typing import List, Dict, Any


class CrossEncoderReranker:
    """基于 Cross-Encoder 的搜索结果重排序"""

    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"):
        self.model_name = model_name
        self._model = None
        self._tokenizer = None

    @property
    def is_available(self) -> bool:
        return self._model is not None

    def _load_model(self):
        """延迟加载模型"""
        if self._model is not None:
            return

        try:
            from sentence_transformers import CrossEncoder
            self._model = CrossEncoder(self.model_name)
            print(f"[CrossEncoderReranker] 模型 {self.model_name} 加载成功")
        except Exception as e:
            print(f"[CrossEncoderReranker] 模型加载失败: {e}")
            self._model = None

    def rerank(
        self,
        query: str,
        documents: List[Dict[str, Any]],
        top_k: int = 5,
        text_key: str = "text",
    ) -> List[Dict[str, Any]]:
        """
        对候选文档进行重排序
        documents: [{text, ...}, ...]
        返回: 按相关性排序的文档列表
        """
        if not documents:
            return []

        self._load_model()
        if not self.is_available:
            # 模型不可用，按原始分数排序
            return sorted(documents, key=lambda x: x.get("score", 0), reverse=True)[:top_k]

        # 准备输入
        texts = [doc.get(text_key, "") for doc in documents]
        pairs = [[query, text] for text in texts]

        try:
            scores = self._model.predict(pairs)

            # 添加重排序分数
            for i, doc in enumerate(documents):
                doc["rerank_score"] = float(scores[i])

            # 按重排序分数排序
            ranked = sorted(documents, key=lambda x: x.get("rerank_score", 0), reverse=True)
            return ranked[:top_k]
        except Exception as e:
            print(f"[CrossEncoderReranker] 重排序失败: {e}")
            return sorted(documents, key=lambda x: x.get("score", 0), reverse=True)[:top_k]
