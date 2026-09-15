# Validation record

Build commit: `1ad978342dfd42a9e4cf10f40c22def2d36c1d13`

[Successful GitHub Actions run](https://github.com/ish4ra/installtrace/actions/runs/35028145750)

- Linux: 16 portable tests passed; Windows integration test skipped.
- Windows: all 17 regression/integration tests passed.
- Standalone Windows x64 EXE: built using Python 3.12.10 / PyInstaller 6.11.1.
- Frozen executable smoke test: passed desktop demo, leftovers UI, temporary-file comparison, service and scheduled-task collectors.
- Preview release uploaded with EXE, SHA-256 checksum and smoke-test report.
- Hosted Windows test platform: Windows Server 2025. Consumer Windows 10/11 manual validation remains recommended.
- Executable is unsigned. No installer-attribution, antivirus, or full-machine coverage guarantee.

EXE SHA-256: `228ab617f492f51d985aff634185f9b3ab8c9c713a9f8bab7e8d6453facb4112`

[Download and release notes](https://github.com/ish4ra/installtrace/releases/tag/v0.1.0)
