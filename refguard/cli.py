"""CLI entry point: refcheck verify bib | verify project | fusion train."""
import argparse
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="refguard",
        description="RefGuard: Reference Integrity & Citation Quality Checker",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    # verify bib
    verify = sub.add_parser("verify", help="Verify bibliography (bib or project)")
    verify_sub = verify.add_subparsers(dest="subcommand", required=True)
    bib_p = verify_sub.add_parser("bib", help="Mode A: Bib-only")
    bib_p.add_argument("--input", "-i", required=True, help="Input .bib file")
    bib_p.add_argument("--profile", "-p", default="balanced", choices=["strict", "balanced", "lenient"])
    bib_p.add_argument("--sources", "-s", default="crossref,openalex,arxiv,dblp,semanticscholar", help="Comma-separated sources")
    bib_p.add_argument("--out", "-o", default="./report", help="Output directory")
    bib_p.add_argument("--no-duplicates", action="store_true", help="Disable duplicate detection")
    proj_p = verify_sub.add_parser("project", help="Mode B: Bib+TeX")
    proj_p.add_argument("--bib", "-b", required=True, help="Path to .bib file")
    proj_p.add_argument("--tex", "-t", action="append", default=[], help="Path(s) to .tex file(s)")
    proj_p.add_argument("--check-usage", default="on", choices=["on", "off"])
    proj_p.add_argument("--check-relevance", default="off", choices=["on", "off"])
    proj_p.add_argument("--export-only-used-bib", action="store_true", help="Output only_used.bib")
    proj_p.add_argument("--profile", "-p", default="balanced", choices=["strict", "balanced", "lenient"])
    proj_p.add_argument("--out", "-o", default="./report", help="Output directory")
    # fusion train
    fusion = sub.add_parser("fusion", help="Fusion model")
    fusion_sub = fusion.add_subparsers(dest="subcommand", required=True)
    train_p = fusion_sub.add_parser("train", help="Train fusion model (offline)")
    train_p.add_argument("--dataset", required=True, help="Path to labeled_matches.jsonl")
    train_p.add_argument("--model", default="logistic", choices=["logistic"])
    train_p.add_argument("--calibration", default="platt", choices=["platt", "isotonic"])
    train_p.add_argument("--out", "-o", default="./models/fusion", help="Output model directory")
    args = parser.parse_args()
    if args.command == "verify":
        if args.subcommand == "bib":
            run_verify_bib(args)
        else:
            run_verify_project(args)
    elif args.command == "fusion" and args.subcommand == "train":
        run_fusion_train(args)
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
    print(f"Report written to {out_dir}")


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
    print(f"Report written to {out_dir}")


def run_fusion_train(args) -> None:
    from refguard.core import setup_logging
    setup_logging()
    Path(args.out).mkdir(parents=True, exist_ok=True)
    # Stub: write default weights so fusion model can load them
    import json
    from refguard.fusion.feature_builder import FEATURE_NAMES
    from refguard.fusion.fusion_model import DEFAULT_WEIGHTS, DEFAULT_BIAS
    with open(Path(args.out) / "fusion_model.json", "w") as f:
        json.dump({"weights": DEFAULT_WEIGHTS, "bias": DEFAULT_BIAS, "feature_names": FEATURE_NAMES}, f, indent=2)
    print(f"Default fusion model config written to {args.out} (full training script in eval/)")
