# deploy/

The Podman Quadlet unit files and env templates. **The runbook is
[`../DEPLOY.md`](../DEPLOY.md)** — build, secrets, units, nginx, TLS, upgrades,
backups. This file only says what each artifact here is.

| File | What it is |
|---|---|
| `tripaccounter.container` | the app container: the locally built image, `Requires=postgres.service`, published on `127.0.0.1:8000` only |
| `postgres.container` | Postgres 17, healthchecked with `pg_isready` |
| `tripaccounter.network` | the private Podman network both containers join; gives DNS by container name, which is how `TA_DATABASE_URL` reaches `tripaccounter-db` |
| `postgres.volume` | the database volume — the only state that must outlive an image rebuild |
| `app.env.example` | template for `/etc/tripaccounter/app.env`: `TA_DATABASE_URL` |
| `postgres.env.example` | template for `/etc/tripaccounter/postgres.env`: user, password, database |

The `.network` and `.volume` units are empty on purpose: Quadlet derives
`tripaccounter-network.service` and `postgres-volume.service` from the `Network=`
and `Volume=` references in the `.container` files, and the defaults are what this
deployment wants.

The `*.env.example` files are templates and carry no real credentials. Their
installed counterparts (`app.env`, `postgres.env`) are gitignored and never belong
in this directory.
