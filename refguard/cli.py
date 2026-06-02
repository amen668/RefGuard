"""RefGuard 命令行入口。"""
import argparse
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="refguard",
        description="RefGuard：参考文献身份核验与 LaTeX 引用检查工具",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    verify = sub.add_parser("verify", help="核验参考文献或项目")
    verify_sub = verify.add_subparsers(dest="subcommand", required=True)
    bib_p = verify_sub.add_parser("bib", help="模式 A：只核验 BibTeX")
    bib_p.add_argument("--input", "-i", required=True, help="输入 .bib 文件")
    bib_p.add_argument("--profile", "-p", default="balanced", choices=["strict", "balanced", "lenient"])
    bib_p.add_argument("--sources", "-s", default="crossref,openalex,arxiv,dblp,semanticscholar", help="逗号分隔的数据源名称")
    bib_p.add_argument("--out", "-o", default="./report", help="输出目录")
    bib_p.add_argument("--no-duplicates", action="store_true", help="关闭重复文献检测")
    proj_p = verify_sub.add_parser("project", help="模式 B：核验 BibTeX 并检查 TeX 引用")
    proj_p.add_argument("--bib", "-b", required=True, help=".bib 文件路径")
    proj_p.add_argument("--tex", "-t", action="append", default=[], help=".tex 文件路径，可重复传入")
    proj_p.add_argument("--check-usage", default="on", choices=["on", "off"])
    proj_p.add_argument("--export-only-used-bib", action="store_true", help="输出 only_used.bib")
    proj_p.add_argument("--profile", "-p", default="balanced", choices=["strict", "balanced", "lenient"])
    proj_p.add_argument("--out", "-o", default="./report", help="输出目录")
    args = parser.parse_args()
    if args.command == "verify":
        if args.subcommand == "bib":
            run_verify_bib(args)
        else:
            run_verify_project(args)
    else:
        parser.print_help()


def run_verify_bib(args) -> None:
    from refguard.services import VerificationService
    from refguard.core import setup_logging
    setup_logging()
    path = Path(args.input)
    bib_content = path.read_text(encoding="utf-8") if path.exists() else args.input
    sources = [s.strip() for s in args.sources.split(",")]
    svc = VerificationService(sources=sources, profile_name=args.profile)
    report = svc.verify_bib(bib_content, check_duplicates=not args.no_duplicates)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    report.write_json(out_dir / "report.json")
    report.write_markdown(out_dir / "report.md")
    print(f"报告已写入 {out_dir}")

def run_verify_project(args) -> None:
    from refguard.services import VerificationService
    from refguard.core import setup_logging
    setup_logging()
    bib_path = Path(args.bib)
    bib_content = bib_path.read_text(encoding="utf-8")
    tex_paths = args.tex or []
    svc = VerificationService(profile_name=args.profile)
    report = svc.verify_project(
        bib_content,
        tex_paths=tex_paths if tex_paths else None,
        check_usage=(args.check_usage == "on"),
        check_duplicates=True,
    )
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    report.write_json(out_dir / "report.json")
    report.write_markdown(out_dir / "report.md")
    if args.check_usage == "on" and getattr(args, "export_only_used_bib", False):
        used = svc.tex_parser.get_all_cited_keys()
        report.write_only_used_bib(out_dir / "only_used.bib", svc.bib_parser.entries, used)
    print(f"报告已写入 {out_dir}")
