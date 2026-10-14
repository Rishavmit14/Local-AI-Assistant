# Friday local UI operations

The accepted main worktree at
`~/.codex/worktrees/friday-stage28-live-main/Local-AI-Assistant-terra-integration`
serves the built UI at `http://127.0.0.1:5193` through the enabled user-level
`friday-ui.service`. It serves `frontend/dist` and proxies only
same-origin `/api` and `/health` requests to the configured local Friday API.
The service runs as the owner, binds to loopback, and does not launch or restart
the API, Qwen, Pocket/Anna, voice, or computer-control services.

The service sets `NoNewPrivileges=yes` and a restrictive umask. This host's
user systemd manager does not permit the mount, UTS, or capability namespaces
needed by additional sandbox directives, so the installed unit omits those
settings instead of failing to start. Friday's existing API authentication,
CSRF, Owner-task authorization, and restore boundary remain enforced by the
backend and local UI proxy.

## Install or update

1. Build the accepted main checkout with `npm run build --prefix frontend`.
2. Copy `frontend/systemd/friday-ui.service` and
   `frontend/systemd/friday-ui-rollback.service` into
   `~/.config/systemd/user/`.
3. Create `~/.config/friday/friday-ui.env` with mode `0600` from the sanitized
   `frontend/systemd/friday-ui.env.example`. Set the capability-file and
   installation paths to the existing private Friday Owner configuration;
   do not copy the capability value into this file.
4. Run `systemctl --user daemon-reload` and
   `systemctl --user enable --now friday-ui.service`. The rollback unit remains
   disabled unless rollback is needed.
5. Confirm `systemctl --user is-active friday-ui.service`, then read
   `http://127.0.0.1:5193/health` and open the UI. The frontend server's health
   request is proxied to Friday's existing API.

For later builds, stop the UI service while replacing `frontend/dist`, then
start it again. Friday's backend and model services do not need a restart.

## Rollback

The GCA checkout at
`/home/kumar-rishav/.codex/worktrees/friday-general-computer-agency/Local-AI-Assistant-terra-integration`
is preserved for recovery. To return to it, disable and stop the built UI, then
enable and start `friday-ui-rollback.service`. To return to the accepted UI,
disable and stop the rollback unit, build the accepted main frontend, then
enable and start `friday-ui.service`. The units conflict on port ownership and
do not start together. No API or Qwen restart is part of either procedure.

To disable the built UI, run `systemctl --user disable --now friday-ui.service`.
The service reads the capability file but does not own or expose its value;
Owner authorization can be revoked through Friday's existing local capability
administration, independently of the UI service.
