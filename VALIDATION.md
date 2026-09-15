# Validation record

- Python portable regression tests: 16 passed.
- Windows collector integration test: 1 skipped on the Linux authoring host.
- Python compilation: passed.
- Demo HTML report: generated successfully with 5 synthetic differences.
- Tkinter import: passed; desktop UI not launched (no display server).
- Windows PowerShell collectors: source reviewed, not executed here.
- Standalone Windows EXE: not built; Windows Actions workflow supplied.
- GitHub remote: not created or pushed; available connector exposes no repository-creation operation.

Run `python -m unittest discover -s tests -v` on Windows before relying on live captures.
The generated report is a demonstration, not evidence from a real installation.

Prepared executable-level GUI/collector smoke test and SHA-256 output; execution pending Windows runner.
