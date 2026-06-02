"""用于相似度比较的文本规范化工具。"""
import re
import unicodedata
from unidecode import unidecode


class TextNormalizer:
    LATEX_COMMANDS = [
        (r"\\textbf\{([^}]*)\}", r"\1"),
        (r"\\textit\{([^}]*)\}", r"\1"),
        (r"\\emph\{([^}]*)\}", r"\1"),
        (r"\\textrm\{([^}]*)\}", r"\1"),
        (r"\\texttt\{([^}]*)\}", r"\1"),
        (r"\\url\{([^}]*)\}", r"\1"),
        (r"\\href\{[^}]*\}\{([^}]*)\}", r"\1"),
    ]
    LATEX_CHARS = {
        r"\&": "&", r"\%": "%", r"\$": "$", r"\#": "#", r"\_": "_",
        r"\{": "{", r"\}": "}", r"\~": "~", r"\^": "^", r"``": '"', r"''": '"',
    }
    LATEX_ACCENTS = [
        (r"\\'([aeiouAEIOU])", r"\1"), (r"\\`([aeiouAEIOU])", r"\1"),
        (r'\\"([aeiouAEIOU])', r"\1"), (r"\\~([nNaAoO])", r"\1"),
    ]

    @classmethod
    def normalize_latex(cls, text: str) -> str:
        if not text:
            return ""
        result = text
        for pattern, repl in cls.LATEX_COMMANDS:
            result = re.sub(pattern, repl, result)
        for pattern, repl in cls.LATEX_ACCENTS:
            result = re.sub(pattern, repl, result)
        for latex_char, normal_char in cls.LATEX_CHARS.items():
            result = result.replace(latex_char, normal_char)
        result = re.sub(r"[{}]", "", result)
        return result

    @classmethod
    def normalize_unicode(cls, text: str) -> str:
        if not text:
            return ""
        text = unicodedata.normalize("NFKD", text)
        return unidecode(text)

    @classmethod
    def normalize_whitespace(cls, text: str) -> str:
        if not text:
            return ""
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    @classmethod
    def remove_punctuation(cls, text: str) -> str:
        if not text:
            return ""
        return re.sub(r"[^\w\s]", "", text)

    @classmethod
    def normalize_for_comparison(cls, text: str) -> str:
        if not text:
            return ""
        text = cls.normalize_latex(text)
        text = cls.normalize_unicode(text)
        text = text.lower()
        text = cls.normalize_whitespace(text)
        text = cls.remove_punctuation(text)
        return text

    @classmethod
    def normalize_author_name(cls, name: str) -> str:
        if not name:
            return ""
        name = cls.normalize_latex(name)
        name = cls.normalize_unicode(name)
        name = cls.normalize_whitespace(name)
        if "," in name:
            parts = name.split(",", 1)
            if len(parts) == 2:
                name = f"{parts[1].strip()} {parts[0].strip()}"
        name = name.lower()
        name = cls.remove_punctuation(name)
        return name

    @classmethod
    def normalize_author_list(cls, authors: str) -> list[str]:
        if not authors:
            return []
        parts = re.split(r"\s+and\s+", authors, flags=re.IGNORECASE)
        return [cls.normalize_author_name(a.strip()) for a in parts if a.strip()]

    @classmethod
    def similarity_ratio(cls, text1: str, text2: str) -> float:
        if not text1 or not text2:
            return 0.0
        w1, w2 = set(text1.split()), set(text2.split())
        if not w1 and not w2:
            return 1.0
        if not w1 or not w2:
            return 0.0
        return len(w1 & w2) / len(w1 | w2)

    @classmethod
    def levenshtein_similarity(cls, s1: str, s2: str) -> float:
        if not s1 and not s2:
            return 1.0
        if not s1 or not s2:
            return 0.0
        m, n = len(s1), len(s2)
        dp = [[0] * (n + 1) for _ in range(m + 1)]
        for i in range(m + 1):
            dp[i][0] = i
        for j in range(n + 1):
            dp[0][j] = j
        for i in range(1, m + 1):
            for j in range(1, n + 1):
                if s1[i - 1] == s2[j - 1]:
                    dp[i][j] = dp[i - 1][j - 1]
                else:
                    dp[i][j] = min(dp[i - 1][j], dp[i][j - 1], dp[i - 1][j - 1]) + 1
        return 1.0 - (dp[m][n] / max(m, n))
