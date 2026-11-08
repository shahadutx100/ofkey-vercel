#!/usr/bin/env python3
"""
Ghost Hack (vsx) auth door — core logic, copied from the live Render
panel (~/workspace/ffmaxind-panel/app5.py, ghost section only).

Protocol (~/workspace/vsx-analysis/response_format.md):
  POST /api/auth1  (alias /api/client/auth)
       JSON {key, hwid, ...} ->
         {"success":true,"expiry":D,"expires_at":D,"seller":S,
          "session_token":T,"file_url":null,"version":null,
          "announcement":null,"is_trial":false}
         {"success":false,"error":"<text shown to the user>"}
       D is the key's expiry date + " 23:59:59" ("yyyy-MM-dd HH:mm:ss").
  GET  /offset     (alias /api/offsets), header X-Session-Token ->
         {"success":true,"cfg":TABLE,"offsets":TABLE} for an issued
         token; an EMPTY body for a missing/unknown token.

Storage is shared with the Render panel: when DATABASE_URL is set (and
psycopg is installed) the same Neon Postgres database is used, so every
Ghost key created in the Render panel works here unchanged, HWID
bindings and login logs included. Without DATABASE_URL a local sqlite
file is used (local testing only — Vercel's filesystem is ephemeral).
SQLITE_DB_PATH may override the sqlite file location for tests.

This package is an auth door only: no admin panel, no OrangeFox routes.
"""
import json, os, secrets, sqlite3
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("SQLITE_DB_PATH", os.path.join(HERE, "panel.db"))
SELLER_DEFAULT = "Shahadut Mod FF"
DATABASE_URL = os.environ.get("DATABASE_URL", "")
USE_PG = False
if DATABASE_URL:
    try:
        import psycopg
        from psycopg.rows import dict_row
        USE_PG = True
    except Exception:
        USE_PG = False

# ---------------------------------------------------------------- storage
class DB:
    def __init__(self):
        if USE_PG:
            self.con = psycopg.connect(DATABASE_URL, row_factory=dict_row, autocommit=True)
        else:
            self.con = sqlite3.connect(DB_PATH)
            self.con.row_factory = sqlite3.Row
        self._ddl()

    def _ddl(self):
        if USE_PG:
            stmts = [
                """CREATE TABLE IF NOT EXISTS ghost_keys(
                    id SERIAL PRIMARY KEY,
                    user_key TEXT UNIQUE NOT NULL,
                    hwid TEXT, expires TEXT NOT NULL,
                    blocked INTEGER NOT NULL DEFAULT 0,
                    seller TEXT DEFAULT '', note TEXT DEFAULT '',
                    created TEXT NOT NULL, last_login TEXT)""",
                """CREATE TABLE IF NOT EXISTS ghost_log(
                    id SERIAL PRIMARY KEY,
                    ts TEXT NOT NULL, user_key TEXT, hwid TEXT,
                    result TEXT NOT NULL, detail TEXT DEFAULT '')""",
                """CREATE TABLE IF NOT EXISTS ghost_tokens(
                    id SERIAL PRIMARY KEY,
                    token TEXT UNIQUE NOT NULL, key_id INTEGER NOT NULL,
                    created TEXT NOT NULL)"""]
        else:
            stmts = [
                """CREATE TABLE IF NOT EXISTS ghost_keys(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_key TEXT UNIQUE NOT NULL,
                    hwid TEXT, expires TEXT NOT NULL,
                    blocked INTEGER NOT NULL DEFAULT 0,
                    seller TEXT DEFAULT '', note TEXT DEFAULT '',
                    created TEXT NOT NULL, last_login TEXT)""",
                """CREATE TABLE IF NOT EXISTS ghost_log(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts TEXT NOT NULL, user_key TEXT, hwid TEXT,
                    result TEXT NOT NULL, detail TEXT DEFAULT '')""",
                """CREATE TABLE IF NOT EXISTS ghost_tokens(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    token TEXT UNIQUE NOT NULL, key_id INTEGER NOT NULL,
                    created TEXT NOT NULL)"""]
        cur = self.con.cursor()
        for s in stmts:
            cur.execute(s)
        self.con.commit()

    def execute(self, sql, params=()):
        if USE_PG:
            sql = sql.replace("?", "%s")
            if sql.startswith("INSERT OR IGNORE"):
                sql = sql.replace("INSERT OR IGNORE", "INSERT") + " ON CONFLICT DO NOTHING"
        cur = self.con.cursor()
        cur.execute(sql, params)
        return cur

    def commit(self):
        self.con.commit()

    def close(self):
        self.con.close()

def db():
    return DB()

def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

# ------------------------------------------------- Ghost Hack (vsx) API
# Captured from the original server's /api/offsets reply (2026-11-08) and
# embedded in the Render panel as GHOST_CFG; 117 keys, served as both the
# cfg and the offsets member, exactly as app5 does.
GHOST_CFG = json.loads('{"_credit": "Server-managed GameCfg offsets \\u2014 client har feature ke offsets yahan se fetch karta hai", "head": 1704, "hip": 1712, "spine": 1720, "root": 1744, "left_ankle": 1760, "right_ankle": 1768, "left_shoulder": 1808, "right_shoulder": 1816, "left_hand": 1832, "right_hand": 1824, "collider": 1752, "main_camera": 904, "follow_camera": 1688, "is_firing": 2008, "aim_info": 3672, "aim_start": 76, "aim_dir": 64, "player_rot": 1460, "game_facade_rva": 181833240, "gf_static": 184, "base_game": 8, "match": 144, "match_running": 204, "local_player": 216, "dictionary": 192, "entity_list": 24, "avatar_mgr": 1912, "cam_comp": 48, "cam_intptr": 16, "cam_matrix": 256, "xf_obj": 16, "xf_index": 64, "xf_matrix": 56, "xf_list": 24, "xf_indices": 32, "xf_stride": 48, "avatar_simple": 312, "avatar_visible": 257, "uma_data": 40, "uma_dead": 129, "enemy_dead": 124, "enemy_knock": 0, "enemy_name": 1184, "enemy_bot": 1192, "knock_comp": 7520, "knock_flag": 16, "hp_c0": 112, "hp_c1": 16, "hp_c2": 32, "hp_val": 24, "time_service": 32, "time_scale": 44, "observe_cur": 256, "observe_player": 48, "ghost_hack": 2068, "dict_count": 32, "dict_array_header": 32, "dict_entry_stride": 24, "dict_entry_value": 16, "player_hed_colider": 1752, "player_col_write": 128, "player_death_info": 8848, "uma_data_skip": 129, "main_camera_fallback": 904, "weapon_instance": 1440, "reload_instance": 1800, "inventory_manager": 1864, "status_struct": 7520, "firing_state": 2056, "view_rotation": 1460, "is_spectating": 124, "head_collider": 1752, "aim_target_write": 128, "client_bot_check": 1192, "name_ptr": 1184, "aiming_info": 3672, "aiming_info_start": 76, "aiming_info_dir": 64, "health_chain1": 112, "health_chain2": 16, "health_chain3": 32, "health_value": 24, "is_dead": 124, "time_service_speed": 44, "weapon_data": 136, "recoil_value": 24, "fast_reload_trigger": 217, "status_data": 32, "state_id": 16, "uma_simple": 312, "is_visible": 257, "avatar_is_dead": 129, "active_item": 160, "weapon_component": 128, "no_recoil": 24, "item_data": 40, "weapon_id": 72, "bone_head": 1704, "bone_chest": 1720, "bone_hip": 1712, "bone_feet": 1744, "bone_lshoulder": 1808, "bone_rshoulder": 1816, "bone_lhand": 1832, "bone_rhand": 1824, "bone_lankle": 1760, "bone_rankle": 1768, "xf_enemy_pos_force": 56, "s_aim2": 3664, "s_aim3": 64, "s_aim4": 208, "player_attributes": 1904, "shoot_no_reload": 273, "base_game_ptr": 184, "cam_object": 48, "xf_index_size": 4}')

def ghost_log(con, key, hwid, result, detail=""):
    con.execute("INSERT INTO ghost_log(ts,user_key,hwid,result,detail) VALUES(?,?,?,?,?)",
                (now_iso(), key or "", hwid or "", result, detail))
    con.commit()

def ghost_auth(payload):
    if not isinstance(payload, dict):
        return {"success": False, "error": "Invalid request"}
    user_key = str(payload.get("key") or "").strip()
    hwid = str(payload.get("hwid") or "").strip()
    con = db()
    try:
        if not user_key:
            ghost_log(con, user_key, hwid, "fail", "empty key")
            return {"success": False, "error": "Invalid Key!"}
        row = con.execute("SELECT * FROM ghost_keys WHERE user_key=?", (user_key,)).fetchone()
        if row is None:
            ghost_log(con, user_key, hwid, "fail", "key not found")
            return {"success": False, "error": "Invalid Key!"}
        if row["blocked"]:
            ghost_log(con, user_key, hwid, "fail", "blocked")
            return {"success": False, "error": "Key blocked"}
        today = datetime.now(timezone.utc).date().isoformat()
        if row["expires"] < today:
            ghost_log(con, user_key, hwid, "fail", "expired")
            return {"success": False, "error": "Key expired"}
        if row["hwid"] and hwid and row["hwid"] != hwid:
            ghost_log(con, user_key, hwid, "fail", "hwid mismatch")
            return {"success": False, "error": "Key used on another device"}
        if not row["hwid"] and hwid:
            con.execute("UPDATE ghost_keys SET hwid=? WHERE id=?", (hwid, row["id"]))
        con.execute("UPDATE ghost_keys SET last_login=? WHERE id=?", (now_iso(), row["id"]))
        token = secrets.token_hex(24)
        con.execute("INSERT INTO ghost_tokens(token,key_id,created) VALUES(?,?,?)",
                    (token, row["id"], now_iso()))
        con.commit()
        ghost_log(con, user_key, hwid, "success")
        exp = row["expires"] + " 23:59:59"
        return {"success": True, "expiry": exp, "expires_at": exp,
                "seller": row["seller"] or SELLER_DEFAULT, "session_token": token,
                "file_url": None, "version": None, "announcement": None,
                "is_trial": False}
    finally:
        con.close()

def ghost_offsets(token):
    """Bytes to return for GET offsets; empty body when token is unknown."""
    if not token:
        return b""
    con = db()
    try:
        row = con.execute("SELECT id FROM ghost_tokens WHERE token=?", (token,)).fetchone()
        if row is None:
            return b""
        return json.dumps({"success": True, "cfg": GHOST_CFG, "offsets": GHOST_CFG}).encode()
    finally:
        con.close()
