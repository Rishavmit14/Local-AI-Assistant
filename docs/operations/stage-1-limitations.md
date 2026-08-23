# Stage 1 Known Limitations

- Repair remains deliberately bounded to the single proven attempt. Configurable 1/2/3 repair policies remain in Stage 5.
- Structured events coexist with legacy stdout progress so operators do not lose the current CLI experience. Removing the compatibility output is a future breaking change, not Stage 1 work.
- Code indexing remains full-repository, line-chunk based, and non-incremental. Tree-sitter, symbols, references, callers, and graphs begin only in Stage 2.
- The compatibility wrapper files assume an editable/installed package or `PYTHONPATH=src`; `scripts/bootstrap/bootstrap.sh` installs the package editable.
- The installed MSI services and external data directories are not migrated automatically. A reviewed opt-in profile and renderer are provided.
