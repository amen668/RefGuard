"""报告状态解析规则。"""
from enum import StrEnum

from .comparison import ComparisonResult


class ReportStatus(StrEnum):
    """对外报告使用的稳定状态值。"""

    VERIFIED = "verified"
    WARNING = "warning"
    ERROR = "error"


def resolve_report_status(comparison: ComparisonResult | None) -> ReportStatus:
    """根据核验结果得到唯一的报告状态。"""
    if comparison is None:
        return ReportStatus.ERROR
    if "author_mismatch" in (comparison.issues or []):
        return ReportStatus.ERROR
    if comparison.is_match:
        return ReportStatus.VERIFIED
    if comparison.match_probability >= 0.3:
        return ReportStatus.WARNING
    return ReportStatus.ERROR
