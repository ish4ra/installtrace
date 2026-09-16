# InstallTrace

**Know what changed.** A local, read-only Windows installation observability app.

Capture before installation, after installation, and after uninstallation. Inspect file,
registry, service and scheduled-task differences, then export an offline report.

**Version 0.2.0 — Midnight Console preview.** The desktop interface has been redesigned with
a modern dark observability-console layout while preserving the existing read-only capture,
comparison, leftover detection and export behavior. Windows regression tests and the standalone
executable smoke test are run automatically before the release is published.

[Download InstallTrace.exe](https://github.com/ish4ra/installtrace/releases/download/v0.2.0/InstallTrace.exe)
— Python is bundled; no Python installation is needed for the EXE.

[Release and checksums](https://github.com/ish4ra/installtrace/releases/tag/v0.2.0) ·
[Build workflow](https://github.com/ish4ra/installtrace/actions/workflows/test-and-build.yml)
No administrator privilege is requested automatically. Use the same account and elevation
for each capture; more restricted coverage is marked explicitly.

## Version 0.2 UI refresh

- Midnight Console dark theme with a cyan/teal observability accent system.
- Dedicated scan-scope and capture-profile panel.
- Three snapshot cards with READY / PARTIAL / SCANNING state chips.
- Redesigned action buttons and comparison command bar.
- Cleaner search/category/change-type filters.
- Color-coded added, modified, removed and uncertain result rows.
- Dedicated inspector panel for before/after evidence and JSON details.
- Improved capture, demo, coverage and comparison status feedback.

## Start on Windows

1. Extract this ZIP into a folder outside the folders you plan to scan.
2. Install Python 3.10 or later from https://www.python.org/downloads/windows/ with Tcl/Tk
   and the Python launcher enabled (the normal Python installer includes these).
3. Double-click **Start-InstallTrace.cmd**, or run `py -3 -m installtrace` from this folder.
4. Click **LOAD DEMO** to explore synthetic changes without scanning.

No pip dependencies are needed for the source app. Linux/macOS can compare snapshots and
create reports; the desktop UI also needs a working Tk installation/display there.

## Capture an installation

1. Set folder scope. Defaults include Program Files, ProgramData and the current user's
   Startup folder. Add the target app's LocalAppData/Roaming folder if relevant. A path
   that does not yet exist can be entered manually and is preserved in the scope.
2. Keep the same folders and hash setting for all captures.
3. Capture **Before install** and save outside the scan roots.
4. Wait for completion. Inspect the coverage/error details. Run your installer separately.
5. Capture **After install**, then **Compare installation**.
6. Optionally uninstall the app normally, capture **After uninstall**, then **Find leftovers**.
7. Search/filter rows, inspect old/new records, or export HTML/JSON.

Unknown installers belong in a disposable VM. InstallTrace is an observer, not a sandbox.
It never launches an installer and never deletes files, registry entries, services or tasks.

## What is collected

| Area | Coverage |
|---|---|
| Files | Files under selected roots, size, mtime, optional SHA-256 |
| Registry | HKCU/HKLM Run, RunOnce and Uninstall trees, both 32/64-bit views |
| Services | Name, binary command, startup mode, account, display name via CIM |
| Tasks | Task identity and exported XML definition; no volatile last-run timestamps |

SHA-256 defaults to files up to 16 MiB. Bigger files are **metadata-only**; same-size,
same-timestamp modifications can therefore be missed. Increase the cap up to 1024 MiB
for a narrow scope. Hashing all of Program Files can be expensive. Symlinks/junctions
are skipped and reported as coverage gaps. Hidden folders are not automatically excluded.
Registry values can contain private commands or paths. Snapshots and reports are local;
there is no telemetry, cloud upload, malware lookup or automatic report redaction.

## Conservative evidence

- Scan errors and missing permissions are reported, not silently treated as deletion.
- If the side needed to prove absence has incomplete coverage, a one-sided record is
  **uncertain**. Coverage is conservative at the whole-category level in this version.
- Captures are not atomic: background updates and changing files can produce noise.
- A difference does not establish that the installer caused it. **Review persistence**
  is a triage label, not a maliciousness verdict.
- Leftovers are identifiers changed during installation that still differ from baseline.
  Unrelated activity on the same identifiers can be included. Items created only after
  the installed snapshot are outside this candidate set. No automatic cleanup is offered.
- Current scope does not include all registry locations, drivers, browser extensions,
  file ACLs/alternate data streams, live process/network activity, or Authenticode checks.
- Machine matching uses hostname/user/elevation, not a hardware identity. Do not compare
  captures across clones or machines sharing the same identity strings.

## CLI

```powershell
py -3 -m installtrace capture --root "C:\Program Files\Example" --hash-mb 32 --out before.json
py -3 -m installtrace capture --root "C:\Program Files\Example" --hash-mb 32 --out after.json
py -3 -m installtrace compare before.json after.json --out changes.html
py -3 -m installtrace compare before.json after.json --uninstalled uninstalled.json --out leftovers.html
py -3 -m installtrace demo --out demo-report.html
py -3 -m unittest discover -s tests -v
```

Use `.json` as the report extension for structured export. HTML output is standalone,
escapes snapshot strings, has a restrictive content security policy and loads no external
scripts, images or fonts. Snapshot imports are limited to 200 MiB.

## Build a standalone Windows EXE

Run on Windows, from this directory:

```powershell
py -3 -m pip install pyinstaller==6.11.1
py -3 -m PyInstaller --noconfirm --clean --onefile --windowed --name InstallTrace launch.py
```

The output is `dist\InstallTrace.exe`. This is unsigned. `Build-Windows.ps1` creates an
isolated Python 3.12 build environment, runs the regression tests, builds the EXE and then
launches the actual executable in self-test mode. GitHub Actions runs the same pipeline and
uploads the EXE, SHA256SUMS.txt and smoke-test.json as an artifact. A successful push to
`main` publishes the tested **v0.2.0** preview when that release does not already exist.

## Publish your repository

Create an empty public `installtrace` repo under your chosen GitHub account. In this folder:

```powershell
git init -b main
git add .
git commit -m "Initial InstallTrace prototype"
git remote add origin https://github.com/YOUR_USERNAME/installtrace.git
git push -u origin main
```

Inspect files before committing: never commit captures from a real machine. The
`snapshots/` folder is ignored, but other arbitrarily named JSON files are not.

## Structure and next milestones

- `installtrace/collect.py`: read-only native collectors and cancellation
- `installtrace/core.py`: validation, comparison, leftover candidates, offline HTML
- `installtrace/ui.py`: threaded dark desktop observability UI
- `tests/`: portable regression tests and Windows integration test

Next: validate on actual Windows machines; Authenticode inspection; narrower per-path
coverage tracking; session history; process-correlated ETW evidence; a signed installer.
These are roadmap items, not implemented features.

## Contributing

Run all tests. Collector changes need a Windows integration test. Keep machine observation
read-only, preserve uncertainty, and avoid collecting secrets unnecessarily. Report bugs
with synthetic/minimized fixtures; redact private paths and command arguments first.

MIT licensed. No affiliation with Microsoft.

## Automated executable validation

`Build-Windows.ps1` creates an isolated build environment, runs tests, builds the EXE,
then launches the actual EXE with `self-test --out dist/smoke-test.json`. The smoke test
checks the desktop demo and leftovers view, captures only a temporary folder, and checks
service/task collection. It does not install software or alter system configuration.
A successful run writes SHA256SUMS.txt beside the EXE. The GitHub workflow uses this same
script and only publishes the release after the Windows build job succeeds.
