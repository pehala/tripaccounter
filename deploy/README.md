# Deploy

Podman Quadlet units: a systemd-managed Postgres container plus the app
container (built from the repo root `Dockerfile`), talking over a private
Podman network. Runs as system services (root); see the rootless note below
if you'd rather run them as a regular user.

## 1. Build the image

```bash
podman build -t localhost/tripaccounter:latest -f Dockerfile .
```

Re-run this after every change you want deployed — the `.container` unit
below references the tag, not the build.

## 2. Secrets

```bash
install -d -m700 /etc/tripaccounter
install -m600 deploy/postgres.env.example /etc/tripaccounter/postgres.env
install -m600 deploy/app.env.example      /etc/tripaccounter/app.env
```

Edit both files: pick a real `POSTGRES_PASSWORD` in `postgres.env` and mirror
it in the `TA_DATABASE_URL` password in `app.env`. Never commit these —
`postgres.env`/`app.env` (unlike the `*.env.example` templates) are
gitignored.

## 3. Install the units

```bash
install -m644 deploy/tripaccounter.network deploy/postgres.volume \
              deploy/postgres.container deploy/tripaccounter.container \
              /etc/containers/systemd/
systemctl daemon-reload
systemctl enable --now postgres.service tripaccounter.service
```

Quadlet derives the network/volume services automatically (`tripaccounter-network.service`,
`postgres-volume.service`) from the `Network=`/`Volume=` references in the
`.container` files, and starting `postgres.service`/`tripaccounter.service`
pulls those in.

## 4. Check it

```bash
systemctl status tripaccounter.service
curl http://localhost:8000/api/v1/trips
```

`app.env`'s `TA_DATABASE_URL` points `psycopg` at the `tripaccounter-db`
container by name (both containers share `tripaccounter.network`, which gives
DNS resolution by container name). Migrations run automatically on start via
`make migrate` (see the app's `Dockerfile`/`CMD`) before uvicorn starts.

## Rootless alternative

Same files work as user services: copy them to
`~/.config/containers/systemd/` instead of `/etc/containers/systemd/`, put
secrets wherever `$XDG_RUNTIME_DIR`-adjacent path you prefer (update
`EnvironmentFile=` accordingly), and use `systemctl --user` instead of
`systemctl`. `PublishPort=8000:8000` then binds to an unprivileged port under
your user, so put a reverse proxy in front if you need port 80/443.

## Updating

```bash
podman build -t localhost/tripaccounter:latest -f Dockerfile .
systemctl restart tripaccounter.service
```

Postgres data lives in the `postgres.volume` quadlet volume and survives
container/image updates and `systemctl restart`; only `podman volume rm
systemd-postgres` (or the rootless equivalent) destroys it.
