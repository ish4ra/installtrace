"""Synthetic fixtures; never presented as observations from the user's machine."""
from copy import deepcopy
from .collect import section
from .core import CATEGORIES


def samples():
    a = {'schema': 1, 'created': '2026-09-16T10:00:00+00:00',
         'machine': {'hostname': 'DEMO-PC', 'user': 'DEMO\\User', 'elevated': False},
         'scope': {'roots': [r'C:\Program Files\Example'], 'hash_mb': 16, 'collector_version': 1},
         'sections': {c: section() for c in CATEGORIES}}
    a['sections']['files']['records'][r'c:\program files\example\config.ini'] = {'size': 40, 'sha256': 'demo-before'}
    b = deepcopy(a); b['created'] = '2026-09-16T10:05:00+00:00'
    b['sections']['files']['records'][r'c:\program files\example\config.ini'] = {'size': 60, 'sha256': 'demo-after'}
    b['sections']['files']['records'][r'c:\program files\example\app.exe'] = {'size': 42000, 'sha256': 'demo-binary'}
    b['sections']['registry']['records'][r'hkcu[64]\software\microsoft\windows\currentversion\run\@example'] = {'type': 1, 'value': r'C:\Program Files\Example\app.exe'}
    b['sections']['services']['records']['exampleupdater'] = {'path': r'C:\Program Files\Example\update.exe', 'startMode': 'Auto', 'account': 'LocalSystem'}
    b['sections']['tasks']['records'][r'\example maintenance'] = {'xml': '<Task><Description>Synthetic example</Description></Task>'}
    c = deepcopy(a); c['created'] = '2026-09-16T10:10:00+00:00'
    c['sections']['services'] = deepcopy(b['sections']['services'])
    return a, b, c
