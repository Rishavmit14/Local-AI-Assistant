# Phase 18B — bounded integrated offline operation

**Date:** 2026-09-29
**Product-matrix row:** 58
**E2E:** E2E-018
**Result:** QUALIFIED (bounded integrated normal-use offline operation, Phase 18B)

## Claim and boundary

The disposable Friday candidate had no usable external IP, DNS, or web egress.
It continued to support the tested ordinary local owner paths using the already
installed Qwen model, cached embedding model, local indexes, local runtime
dependencies, and disposable local state. No host firewall, interface, route,
DNS, NetworkManager, or persistent systemd configuration changed. Production
Friday, production Qwen, the existing candidate, and the protected checkout
were not changed or restarted.

This is not a claim that every Friday capability works offline, that Friday can
be installed from scratch without a network, or that the owner’s browser process
was isolated. Owner-authorized web research, GitHub, external APIs, packages and
model downloads, uncached assets, and other online-only capabilities remain
outside this qualification.

## Candidate topology

The candidate Friday API ran in a transient systemd service with
`PrivateNetwork=yes`, `PrivateUsers=no`, `User=kumar-rishav`,
`Group=kumar-rishav`, and `NoNewPrivileges=yes`. It therefore ran at the normal
owner UID/GID, shared the host user namespace, and had a distinct network
namespace. It listened only on a private pathname AF_UNIX socket; it exposed no
candidate API TCP listener.

The candidate-facing Qwen adapter bound only `127.0.0.1:18080` inside that
namespace. It accepted only `POST /v1/chat/completions`, an exact configured
model, bounded JSON chat messages, the candidate Host value, and the local
qualification credential. It rejected other methods/routes, absolute-form
URLs, CONNECT, alternate Host values, destination/proxy headers, malformed or
oversized bodies, and unsupported fields. Its only next hop was a framed
AF_UNIX request with the fixed operation `chat.completions` and no destination
fields. The host relay checked AF_UNIX peer UID and forwarded only that request
to the fixed literal URL
`http://127.0.0.1:8080/v1/chat/completions`, with proxy environment trust and
redirects disabled. The relay was not a general TCP or SOCKS proxy.

The host-only Astra presentation proxy bound `127.0.0.1:8768`, accepted only
the local candidate Astra origin and `/api/v1/*` or `/health`, and connected to
the one candidate API AF_UNIX socket. The API remained inside its isolated
network namespace. The browser used a production-built local frontend served by
a temporary Vite preview at `127.0.0.1:5192`; the browser itself remained in
the normal host namespace. Consequently, this proves no internet dependency
for the tested integrated page/API paths; it does not prove OS-level egress
containment for the browser process.

The actual Bubblewrap helper used by Practice Lab was also available inside
the candidate. Existing `PracticeLabService.availability()` returned available.
No Practice Lab or native sandbox policy was weakened or replaced.

## Evidence

All application and synthetic state lived below the disposable candidate root
in `/tmp`. No owner documents were scanned. One explicitly synthetic text
document and one synthetic Python repository were indexed. The cached BGE
embedding model loaded with `HF_HUB_OFFLINE=1` and
`TRANSFORMERS_OFFLINE=1`; no model or package was downloaded.

- **External controls:** direct TCP to `1.1.1.1:443` failed with
  `connect_ex=101`; DNS for GitHub, Hugging Face, and OpenAI failed; HTTPS
  attempts to GitHub, Hugging Face, and OpenAI failed; `git ls-remote` to a
  public GitHub repository failed because the isolated namespace could not
  resolve GitHub. Candidate access to host loopback ports 8765, 8080, 8766, and
  5191 failed. No routes, firewall rules, DNS configuration, or host network
  interfaces were changed.
- **Local Qwen bridge:** an actual request traversed the candidate adapter,
  private AF_UNIX relay, and the already-running local Qwen model, returning
  HTTP 200 and a real completion. Adversarial route, method, Host, request
  target, body-size, and destination-header attempts were rejected.
- **Conversation:** Astra submitted a real owner-path text turn and displayed
  local Qwen output. After candidate restart, another Astra turn displayed the
  exact requested synthetic confirmation phrase through the same fixed relay.
- **Memory:** Astra explicitly saved synthetic fact
  `The disposable offline qualification sentinel is cobalt otter 17.` The
  active record reappeared in Astra Memory after candidate restart.
- **Career Forge:** Astra displayed the synthetic active
  `Verify Python state and functions` mission and `owner attempt` resume point
  after restart.
- **Private Knowledge:** Astra selected the synthetic indexed note and Qwen
  answered `ochre marshmallow 42` with the retrieved source chunk. The cached
  embedding model had loaded in offline-only mode.
- **Code intelligence:** CodeRAG indexed and reloaded the synthetic repository
  `synthetic-offline-project`; the local Qwen-backed query returned
  `violet comet 42` with the synthetic file and line evidence while offline.
- **Local tool:** actual Astra Practice Lab Test and Run invoked the existing
  Bubblewrap `NetworkPolicy.DENY` learner execution. Both completed. Learner
  probes could not connect to external IP, host Qwen, or the candidate Qwen
  adapter; the normal synthetic code tests passed. `NetworkPolicy.DENY` remained
  enforced by the existing Bubblewrap backend.
- **Restart/reconstruction:** candidate Friday was stopped and started again
  inside the same private-network anchor with the same disposable state root.
  The first stop had an active browser/API stream; Uvicorn waited for that
  connection until systemd's 90-second stop timeout and systemd terminated only
  the disposable candidate process. After restarting the candidate, Memory,
  Career Forge mission, and Knowledge source/index reappeared in the
  post-restart UI; a real post-restart Conversation also traversed the fixed
  Qwen relay. Closing the browser before final candidate shutdown allowed a
  clean stop.
  CodeRAG had been separately loaded and queried while offline
  before restart; its post-restart query was not part of this evidence. The
  temporary transient units were later stopped and removed.
- **Online-only behavior:** no web fetch or GitHub operation was substituted by
  local fixtures. External DNS, HTTPS, and GitHub negative controls failed;
  local owner surfaces remained useful. External-information and acquisition
  actions remain online-only or outside the claim.

The candidate service and its Qwen adapter ran under systemd network
containment; Practice Lab learner processes ran in their own existing
Bubblewrap DENY boundary. The browser was outside those namespaces and used
only local built assets and the constrained loopback presentation proxy for
this scenario. That distinction is part of the claim, not an assumption of
browser containment.

## Regression and cleanup

Validation passed: 17 focused bridge tests; 1,064 Python tests; 105 frontend
tests; ESLint; TypeScript; production build; Ruff; `pip check`; canonical
repository verification (including 1,064 Python tests and tracked-artifact
checks); and `git diff --check`. Existing warnings are the Starlette/AnyIO
deprecation and Vite large-chunk advisory. One earlier full-suite execution had
an unrelated MCP stdio subprocess exceed its 20-second test timeout; the
focused test passed on rerun, followed by a clean full-suite pass and clean
canonical repository verification.

The transient containment, candidate API, Qwen adapter, and relay units were
stopped; the preview, presentation proxy, and relay processes exited; temporary
AF_UNIX paths and candidate state were removed. Only production Friday on
`127.0.0.1:8765` and production Qwen on `127.0.0.1:8080` remained on the
inspected ports. Host networking was not modified. The only qualification
artifacts retained are the scoped harness scripts and their focused tests in
the repository.
