"""Local lexical retrieval for experiment memories."""
from collections import Counter, defaultdict
import re


def terms(text):
    western = re.findall(r"[a-z0-9][a-z0-9-]+", text.casefold())
    cjk = re.findall(r"[\u3040-\u30ff\u3400-\u9fff]+", text)
    return set(western).union(
        token[i:i + 2] for token in cjk for i in range(len(token) - 1)
    )


class MemoryIndex:
    def __init__(self, texts):
        self.postings = defaultdict(set)
        self.vector = {}
        for key, text in texts.items():
            words = terms(text)
            self.vector[key] = words
            for word in words:
                self.postings[word].add(key)

    def neighbors(self, text, limit=3, exclude=()):
        query = terms(text)
        scores = Counter()
        for word in query:
            matches = self.postings.get(word, ())
            for key in matches:
                scores[key] += 1 / len(matches) ** 0.6
        for key in exclude:
            scores.pop(key, None)
        return sorted(scores, key=lambda key: (
            -scores[key] / (max(len(self.vector[key]), 1) ** 0.5), key
        ))[:limit]
