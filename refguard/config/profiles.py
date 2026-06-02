"""核验配置档预设。"""
from dataclasses import dataclass
from typing import Literal

ProfileName = Literal["strict", "balanced", "lenient", "adaptive"]
PROFILE_NAMES: list[str] = ["strict", "balanced", "lenient", "adaptive"]


@dataclass
class ProfileConfig:
    match_threshold: float
    top_k: int
    gap_threshold: float = 0.05
    # 是否启用证据自适应阈值（按 DOI 解析、多源佐证、文献类型等动态调整判定阈值）。
    adaptive: bool = False
    # 自适应阈值的上下限与各因子幅度，仅 adaptive=True 时生效。
    adapt_floor: float = 0.45
    adapt_ceil: float = 0.90
    w_doi_match: float = 0.12        # 引用 DOI 解析到同一候选 → 证据强，降阈值
    w_full_agree: float = 0.08       # 题名+年份+作者全一致 → 降阈值
    w_evidence: float = 0.05         # 多个独立数据源同时命中 → 降阈值
    w_nonstd: float = 0.05           # 非标准文献（书籍/学位/报告）且题名强匹配 → 适度降阈值
    w_author_penalty: float = 0.10   # 作者严重不符 → 升阈值
    evidence_min_sources: int = 3    # 触发多源佐证所需的不同数据源数


PROFILES: dict[str, ProfileConfig] = {
    "strict": ProfileConfig(
        match_threshold=0.95,
        top_k=5,
        gap_threshold=0.05,
    ),
    "balanced": ProfileConfig(
        match_threshold=0.85,
        top_k=8,
        gap_threshold=0.05,
    ),
    "lenient": ProfileConfig(
        match_threshold=0.70,
        top_k=10,
        gap_threshold=0.05,
    ),
    # 证据自适应档：以 0.70 为基准阈值，按可获得证据强度上下浮动。
    "adaptive": ProfileConfig(
        match_threshold=0.70,
        top_k=10,
        gap_threshold=0.05,
        adaptive=True,
    ),
}


def get_profile(name: str) -> ProfileConfig:
    if name not in PROFILES:
        return PROFILES["balanced"]
    return PROFILES[name]
