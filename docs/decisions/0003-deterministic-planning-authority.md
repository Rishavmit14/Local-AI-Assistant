# ADR 0003: Deterministic facts govern model-assisted planning

Status: Accepted for Stage 3

## Context

Qwen can organize implementation work but cannot reliably establish whether repository files, symbols, imports, calls, tests, or protected paths actually exist. Stage 2 already provides those facts deterministically.

## Decision

Planning is a gated pipeline: deterministic classification signals and Stage 2 scope evidence are assembled first; Qwen receives a bounded evidence packet and returns planning-only JSON; typed parsing and deterministic validation then decide whether the plan can proceed. Qwen cannot create existing-file or existing-symbol facts. New targets must use explicit proposed-new fields.

Deterministic risk floors cannot be lowered by model output. High-risk plans require human review, critical plans remain blocked until explicit approval, and validation errors reject the plan. The Stage 3 approval result gates patch generation but does not replace Stage 1 Git transactions.

## Consequences

Ambiguous tasks remain low-confidence or mixed. Static caller/import relationships are explained as likely impact rather than runtime certainty. Context is bounded to selected symbols, graph provenance, project instructions, and relevant architecture. The general read/act/observe executor loop remains Stage 4 work.
