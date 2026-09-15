"""Pydantic schemas: the shape half of the API contract.

`/openapi.json` is generated from these models, `/docs` renders it, and the
committed `openapi.json` at the repo root is a snapshot of that generation
(`make openapi`). The meaning half — what each number stands for, how a split
resolves, which rule yields which code — is `design/API.md`.

Import from the submodule that holds the shape: `fields`, `requests`,
`responses`, `envelopes`, `error_shapes`.
"""
