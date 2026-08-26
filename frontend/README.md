# Friday Frontend

Stage 11 presentation client for Friday.

This frontend is intentionally presentation-only. It consumes Friday's
presentation API and runtime event stream and does not own coding-agent,
filesystem, Git, approval, validation, or execution authority.

## Commands

```bash
npm install
npm run test
npm run build
npm run lint
npm run dev
```

The cinematic interface is built on top of the typed runtime client and store
under `src/runtime/`.
