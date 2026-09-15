import argparse
from pathlib import Path
from . import core


def main():
    parser = argparse.ArgumentParser(description='InstallTrace: local Windows installation observability')
    sub = parser.add_subparsers(dest='command')
    cap = sub.add_parser('capture'); cap.add_argument('--root', action='append', required=True); cap.add_argument('--hash-mb', type=int, default=16); cap.add_argument('--out', required=True)
    diff = sub.add_parser('compare'); diff.add_argument('before'); diff.add_argument('after'); diff.add_argument('--uninstalled'); diff.add_argument('--out', required=True)
    demo = sub.add_parser('demo'); demo.add_argument('--out', default='demo-report.html')
    smoke = sub.add_parser('self-test'); smoke.add_argument('--out', required=True)
    args = parser.parse_args()
    try:
        if args.command == 'self-test':
            from .selftest import run
            try:
                result = run()
            except Exception as exc:
                core.save(args.out, {'status': 'failed', 'error': str(exc)})
                raise SystemExit(1)
            core.save(args.out, result)
            return
        if not args.command:
            from .ui import run
            run(); return
        if args.command == 'capture':
            from .collect import capture
            core.save(args.out, capture(args.root, args.hash_mb, progress=print)); return
        if args.command == 'demo':
            from .demo import samples
            a,b,_ = samples(); result = core.compare(a,b)
        else:
            a,b = core.load(args.before), core.load(args.after)
            result = core.leftovers(a,b,core.load(args.uninstalled)) if args.uninstalled else core.compare(a,b)
        if Path(args.out).suffix.lower() == '.json': core.save(args.out, result)
        else: Path(args.out).write_text(core.report_html(result), encoding='utf-8')
        print(f'Saved {args.out}: {len(result["changes"])} changes')
    except (ValueError, OSError, RuntimeError) as exc:
        parser.exit(1, f'InstallTrace: {exc}\n')

if __name__ == '__main__': main()
