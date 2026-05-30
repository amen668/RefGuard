"""核验配置档预设。"""
from dataclasses import dataclass
from typing import Literal

ProfileName = Literal["strict", "balanced", "lenient"]
PROFILE_NAMES: list[str] = ["strict", "balanced", "lenient"]


@dataclass
class ProfileConfig:
    match_threshold: float
    top_k: int
    gap_threshold: float = 0.05


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
}


def get_profile(name: str) -> ProfileConfig:
    if name not in PROFILES:
        return PROFILES["balanced"]
    return PROFILES[name]
