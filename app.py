#!/usr/bin/env python3
"""
Ghost Hack auth door — Vercel (Flask) variant.

A SECOND front door to the same Ghost panel that is live on Render
(https://ofkey.onrender.com). It exists so the clients can be pointed at
a different hostname/edge if the Render/Cloudflare path ever misbehaves
for them. All Ghost keys, HWID bindings, tokens and login logs live in
the SAME Neon Postgres database (DATABASE_URL) that the Render panel
uses, so a key created in the Render panel works here unchanged, and a
session token issued here is stored in the shared ghost_tokens table.

Routes (logic in core.py, byte-identical to app5.py on Render):
  POST /api/auth1        Ghost login (JSON {key, hwid, ...})
  POST /api/client/auth  same handler, original-server path alias
  GET  /offset           offsets table for header X-Session-Token
  GET  /api/offsets      same handler, original-server path alias
  GET  /                 plain-text "ok" health check

No admin panel in this package (keys stay managed from the Render
panel) and no OrangeFox routes — auth door only, minimal surface.

Client URL check (the .sh client assembles fixed-length URLs):
  auth    https://ofkey12.vercel.app/api/auth1 = 36 chars
          8 ("https://") + 7 ("ofkey12") + 11 (".vercel.app")
          + 10 ("/api/auth1")
  offsets https://ofkey12.vercel.app/offset    = 33 chars
The Vercel project name MUST be exactly 7 characters (ofkey12).
Env vars to set in Vercel: DATABASE_URL only (same value as Render).
"""
import json
import os

from flask import Flask, request, Response

import core

app = Flask(__name__)


@app.route("/api/auth1", methods=["POST"])
@app.route("/api/client/auth", methods=["POST"])
def ghost_auth_route():
    try:
        payload = json.loads(request.get_data(cache=True).decode("utf-8", "replace"))
    except Exception:
        payload = None
    body = json.dumps(core.ghost_auth(payload)).encode()
    return Response(body, content_type="application/json")


@app.route("/offset", methods=["GET"])
@app.route("/api/offsets", methods=["GET"])
def ghost_offsets_route():
    body = core.ghost_offsets(request.headers.get("X-Session-Token") or "")
    return Response(body, content_type="application/json")


@app.route("/", methods=["GET"])
def health():
    return Response("ok", mimetype="text/plain")


if __name__ == "__main__":
    core.db().close()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8080")))
