"""Exercise the actual frozen Windows executable without touching installed apps."""
import os
import tempfile
from pathlib import Path
from . import core
from .collect import capture


def run():
    if os.name != 'nt':
        raise RuntimeError('Executable smoke test requires Windows.')
    from .ui import App
    app = App()
    try:
        app.withdraw()
        app.demo()
        app.update_idletasks()
        if len(app.tree.get_children()) != 5:
            raise RuntimeError('Desktop demo did not show its five expected changes.')
        app.compare(True)
        if len(app.tree.get_children()) != 1:
            raise RuntimeError('Desktop leftovers view did not show its expected candidate.')
    finally:
        app.destroy()
    with tempfile.TemporaryDirectory(prefix='installtrace-test-') as folder:
        before = capture([folder], 1)
        fixture = Path(folder) / 'fixture.txt'
        fixture.write_text('InstallTrace executable smoke test', encoding='utf-8')
        after = capture([folder], 1)
        changes = [c for c in core.compare(before, after)['changes'] if c['category'] == 'files']
        if len(changes) != 1 or changes[0]['kind'] != 'added':
            raise RuntimeError('Live file collector failed to detect the temporary fixture.')
        for category in ('services', 'tasks'):
            if before['sections'][category]['status'] != 'complete':
                raise RuntimeError(f'{category} collector failed: {before["sections"][category]["errors"]}')
        return {'status': 'passed', 'checks': ['desktop demo', 'desktop leftovers', 'live file comparison', 'services', 'scheduled tasks'],
                'coverage': {k: {'status': v['status'], 'error_count': len(v['errors'])} for k,v in before['sections'].items()}}
