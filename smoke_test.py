"""End-to-end API smoke test: python smoke_test.py  (uses a throwaway database)."""
import hashlib
import os
import sys
import tempfile

tmp = tempfile.mkdtemp()
os.environ["GRIDMAP_DB"] = os.path.join(tmp, "test.db")
os.environ["GRIDMAP_ADMIN_PASSWORD"] = "gm-password-123"
os.environ["GRIDMAP_LOGIN_POW_BITS"] = "6"

import app as appmod  # noqa: E402
from security import leading_zero_bits  # noqa: E402

A = appmod.app
H = {"X-Requested-With": "GridMap"}
FAILS = []


def check(cond, msg):
    print(("  ok   " if cond else "  FAIL ") + msg)
    if not cond:
        FAILS.append(msg)


def pow_solve(cl):
    ch = cl.get("/api/login/challenge").get_json()
    n = 0
    while leading_zero_bits(hashlib.sha256(f"{ch['challenge']}:{n}".encode()).digest()) < ch["bits"]:
        n += 1
    return ch["challenge"], n


def login(cl, user, pw):
    ch, n = pow_solve(cl)
    return cl.post("/api/login", json={"username": user, "password": pw, "challenge": ch, "counter": n})


def j(r):
    return r.get_json()


gm = A.test_client()
print("GM")
check(login(gm, "admin", "nope").status_code == 401, "wrong GM password rejected")
check(login(gm, "admin", "gm-password-123").status_code == 200, "GM signs in")
cid = j(gm.post("/api/campaigns", json={"name": "Seattle 2081"}, headers=H))["id"]
check(gm.post("/api/campaigns", json={"name": "x"}).status_code == 403, "CSRF header required")
mid = j(gm.post("/api/maps", json={"name": "Warehouse", "campaignId": cid, "width": 10, "height": 8,
                                   "data": {"cells": {f"{c},{r}": {"fill": "#123456"} for c in range(5) for r in range(3)},
                                            "markers": [{"id": "e1", "c": 4, "r": 2, "type": "enemy", "cm": {"pm": 10, "sm": 9, "ov": 3}}]}},
                headers=H))["id"]
inv = j(gm.post(f"/api/games/{cid}/invites", json={"note": "Ana"}, headers=H))
check("/invite/" in inv["url"], "invite link created")

print("Invite")
pl = A.test_client()
check(pl.get(f"/invite/{inv['token']}").status_code == 200, "invite page opens")
ch, n = pow_solve(pl)
r = pl.post(f"/api/invite/{inv['token']}", json={"username": "admin", "password": "longenough", "challenge": ch, "counter": n}, headers=H)
check(r.status_code == 400, "reserved username refused")
ch, n = pow_solve(pl)
r = pl.post(f"/api/invite/{inv['token']}", json={"username": "ana", "password": "runner-pass", "challenge": ch, "counter": n}, headers=H)
check(r.status_code == 200, "player registers through invite")
ch, n = pow_solve(pl)
r = pl.post(f"/api/invite/{inv['token']}", json={"username": "ana2", "password": "runner-pass", "challenge": ch, "counter": n}, headers=H)
check(r.status_code == 410, "invite is single use")
check(pl.get("/api/overview").status_code == 401, "player can't reach GM API")
check(pl.get("/").status_code == 302, "player redirected away from GM home")

st = j(pl.get("/api/me/state"))
pid = st["me"]["id"]
check(st["me"]["status"] == "draft", "new sheet is a draft")
check(st["view"]["map"] is None, "no map until GM places token")

print("Sheet (draft)")
act = lambda **kw: pl.post("/api/me/sheet/action", json=kw, headers=H)  # noqa: E731
r = act(action="set_info", name="Ana Rios", metatype="Elf", role="Street Samurai")
check(r.status_code == 200 and j(r)["char"]["name"] == "Ana Rios", "set name/metatype/role")
r = act(action="set_attribute", attr="Agility", value=5)
check(j(r)["derived"]["attributes"]["Agility"] == 6, "free attribute edit + role bonus")
r = act(action="set_skill", skill="Firearms", rank=5, spec="Pistols")
check(j(r)["char"]["skills"]["Firearms"] == 5, "free skill edit")
r = act(action="buy", category="Weapons", index=0)
check(j(r)["char"]["nuyen"] == 4200, "store purchase deducts price")
r = act(action="buy", category="Cyberware", index=3)
check(r.status_code == 400 and "Not enough nuyen" in j(r)["error"], "can't buy without nuyen")
r = act(action="admin_set", karma=999)
check(r.status_code == 403, "player can't use GM override")
r = act(action="remove_item", category="Weapons", index=0)
check(j(r)["char"]["nuyen"] == 5000, "draft refund on removal")
act(action="buy", category="Weapons", index=0)
act(action="buy", category="Armor", index=0)
r = act(action="add_quality", quality="Lucky")
check(j(r)["char"]["karma"] == 38, "positive quality costs karma")
r = pl.post("/api/me/submit", json={"submit": True}, headers=H)
check(j(r)["player"]["status"] == "waiting", "player submits for approval")
ov = j(gm.get("/api/overview"))
check(ov["games"][0]["waiting"] == 1, "GM sees one sheet waiting")

print("GM review / grants / edge")
r = gm.post(f"/api/players/{pid}/review", json={"decision": "approve"}, headers=H)
check(j(r)["approved"] is True, "GM approves")
edge_max = j(r)["derived"]["edge_max"]
check(j(r)["char"]["current_edge"] == edge_max, "approval fills Edge")
r = act(action="set_attribute", attr="Body", value=6)
check(r.status_code == 400, "approved: free attribute edit blocked")
r = act(action="raise_attribute", attr="Body")
check(r.status_code == 200 and j(r)["char"]["karma"] == 28, "approved: karma raise (1->2 costs 10)")
r = act(action="remove_item", category="Armor", index=0)
check(j(r)["char"]["nuyen"] == 3800, "approved: no refund")
r = gm.post(f"/api/games/{cid}/grant", json={"players": "all", "karma": 5, "nuyen": 1000, "reason": "Session 1"}, headers=H)
check(r.status_code == 200, "GM grants karma+nuyen to all")
sh = j(pl.get("/api/me/sheet"))
check(sh["char"]["karma"] == 33 and sh["char"]["nuyen"] == 4800, "grant landed")
check(any(e["reason"] == "Session 1" for e in sh["ledger"]), "grant in history")

print("Dice & Edge")
r = pl.post("/api/me/roll", json={"key": "skill:Firearms", "wild": True, "threshold": 2}, headers=H)
check(r.status_code == 200, "skill roll")
roll = next(x for x in j(r)["rolls"] if x["id"] == j(r)["rollId"])
check(roll["data"]["pool"] == 11 and roll["data"]["dice"][0].get("w") == 1, "pool 6+5 and wild die present")
r = pl.post(f"/api/me/rolls/{roll['id']}/boost", json={"boost": "buy_hit"}, headers=H)
check(r.status_code == 200 and j(r)["me"]["edge"]["cur"] == edge_max - 3 if edge_max >= 3 else r.status_code == 400, "buy-hit boost spends 3 Edge (or refused if short)")
r = pl.post(f"/api/me/rolls/{roll['id']}/boost", json={"boost": "buy_hit"}, headers=H)
check(r.status_code == 400, "one boost per roll")
gm.post(f"/api/games/{cid}/edge", json={"players": [pid], "action": "refresh"}, headers=H)
check(j(pl.get("/api/me/state"))["me"]["edge"]["cur"] == edge_max, "GM refresh Edge")
r = pl.post("/api/me/roll", json={"key": "spec:Firearms", "push": True}, headers=H)
check(r.status_code == (200 if edge_max >= 4 else 400), "push the limit costs 4 Edge")
r = pl.post("/api/me/initiative", json={}, headers=H)
check(r.status_code == 200 and j(r)["rolls"][0]["kind"] == "init", "initiative roll logged")
r = gm.post(f"/api/games/{cid}/roll", json={"dice": 8, "hidden": True, "label": "Guard perception"}, headers=H)
check(r.status_code == 200, "GM hidden roll")
check(not any(x["data"].get("label") == "Guard perception" for x in j(pl.get("/api/me/state"))["rolls"]), "hidden GM roll invisible to player")

print("Damage")
r = act(action="set_damage", track="stun", value=99)
d = j(r)["derived"]
check(d["stun_damage"] == d["stun_boxes"] and d["physical_damage"] > 0, "stun overflows into physical")
act(action="set_damage", track="stun", value=0)
act(action="set_damage", track="physical", value=0)

print("Map")
r = gm.post(f"/api/players/{pid}/place", json={"mapId": mid, "c": 0, "r": 0}, headers=H)
check(r.status_code == 200, "GM places token")
st = j(pl.get("/api/me/state"))
check(st["view"]["map"] and st["view"]["token"] == {"c": 0, "r": 0}, "player sees map + token")
check(not any(m["id"] == "e1" for m in st["view"]["map"]["markers"]), "unexplored enemy hidden")
r = pl.post("/api/me/move", json={"c": 4, "r": 2}, headers=H)
check(r.status_code == 200 and any(m["id"] == "e1" and m["cm"]["pm"] == 10 for m in j(r)["map"]["markers"]), "move reveals enemy with monitor")
r = gm.post(f"/api/maps/{mid}/marker", json={"id": "e1", "damage": {"track": "stun", "amount": 12}}, headers=H)
check(j(r)["marker"]["cm"]["s"] == 9 and j(r)["marker"]["cm"]["p"] == 3, "enemy stun overflow")
ctx = j(gm.get(f"/api/maps/{mid}/context"))
check(ctx["players"][0]["cm"]["pm"] > 0, "editor context has player monitors")

print("Runs")
r = gm.post(f"/api/games/{cid}/runs", json={"name": "Data steal", "reward": 10000, "assignees": [pid],
                                           "tasks": [{"description": "Get in", "mandatory": True}, {"description": "No alarms"}]}, headers=H)
rid = j(r)["id"]
check(len(j(pl.get("/api/me/runs"))["runs"]) == 1, "assigned player sees run")
check(gm.post(f"/api/runs/{rid}/complete", json={}, headers=H).status_code == 400, "can't complete before mandatory tasks")
gm.put(f"/api/runs/{rid}", json={"tasks": [{"description": "Get in", "mandatory": True, "completed": True}, {"description": "No alarms"}]}, headers=H)
r = gm.post(f"/api/runs/{rid}/complete", json={}, headers=H)
check(j(r)["payout"] == 5000, "payout scales with tasks (1/2)")
check(j(pl.get("/api/me/sheet"))["char"]["nuyen"] == 9800, "runner paid")
check(pl.put(f"/api/runs/{rid}", json={"name": "x"}, headers=H).status_code == 401, "player can't edit runs")

print("Accounts")
pw = j(gm.post(f"/api/players/{pid}/password", headers=H))["password"]
check(pl.get("/api/me/state").status_code == 401, "password reset signs the player out")
check(login(pl, "ana", pw).status_code == 200, "player signs in with new password")
r = pl.post("/api/me/password", json={"current": pw, "new": "brand-new-pass"}, headers=H)
check(r.status_code == 200 and pl.get("/api/me/state").status_code == 200, "player changes password and stays signed in")
check(j(pl.get("/api/catalog"))["wiki"]["topics"].get("Wild Die"), "catalog + wiki served")

print("Review fixes")
r = gm.post(f"/api/runs/{rid}/complete", json={}, headers=H)
check(r.status_code == 400, "a completed run can't be paid twice")
rid2 = j(gm.post(f"/api/games/{cid}/runs", json={"name": "Double click", "reward": 100, "assignees": [pid]}, headers=H))["id"]
before = j(pl.get("/api/me/sheet"))["char"]["nuyen"]
r1 = gm.post(f"/api/runs/{rid2}/complete", json={}, headers=H); r2 = gm.post(f"/api/runs/{rid2}/complete", json={}, headers=H)
check(r1.status_code == 200 and r2.status_code == 400 and j(pl.get("/api/me/sheet"))["char"]["nuyen"] == before + 100, "second completion refused, paid once")
gm.post(f"/api/games/{cid}/edge", json={"players": [pid], "action": "refresh"}, headers=H)
gm.post(f"/api/players/{pid}/sheet/action", json={"action": "admin_set", "current_edge": 7}, headers=H)
rr = j(pl.post("/api/me/roll", json={"dice": 6}, headers=H))["rollId"]
a1 = pl.post(f"/api/me/rolls/{rr}/boost", json={"boost": "buy_hit"}, headers=H)
a2 = pl.post(f"/api/me/rolls/{rr}/boost", json={"boost": "buy_hit"}, headers=H)
check(a1.status_code == 200 and a2.status_code == 400 and j(pl.get("/api/me/state"))["me"]["edge"]["cur"] == 4, "boost charged once")
# a second runner to receive Edge
inv2 = j(gm.post(f"/api/games/{cid}/invites", json={}, headers=H))
p2 = A.test_client(); ch, n = pow_solve(p2)
p2.post(f"/api/invite/{inv2['token']}", json={"username": "bea", "password": "runner-pass", "challenge": ch, "counter": n}, headers=H)
pid2 = j(p2.get("/api/me/state"))["me"]["id"]
gm.post(f"/api/players/{pid2}/sheet/action", json={"action": "admin_set", "current_edge": 7}, headers=H)
r = pl.post("/api/me/edge", json={"key": "give", "to": pid2}, headers=H)
check(r.status_code == 400 and j(pl.get("/api/me/state"))["me"]["edge"]["cur"] == 4, "can't give Edge to an ally at 7")
p2act = lambda **kw: p2.post("/api/me/sheet/action", json=kw, headers=H)  # noqa: E731
p2act(action="set_attribute", attr="Edge", value=3)
gm.post(f"/api/players/{pid2}/sheet/action", json={"action": "admin_set", "current_edge": 1}, headers=H)
p2act(action="set_info", name="Bea")
check(j(p2.get("/api/me/state"))["me"]["edge"]["cur"] == 1, "draft: unrelated edits don't refill Edge")
p2act(action="set_attribute", attr="Edge", value=4)
check(j(p2.get("/api/me/state"))["me"]["edge"]["cur"] == 4, "draft: Edge follows the Edge attribute")
p2act(action="buy", category="Weapons", index=1)
sh = j(p2act(action="edit_item", category="Weapons", index=0, item={"name": "Colt", "Damage": "9P", "Accuracy": "6", "Price": 320}))
check(sh["char"]["gear"]["Weapons"][0].get("_custom") is True, "player-edited stats are flagged custom")
sh = j(p2act(action="buy", category="Weapons", index=1))
sh = j(p2act(action="edit_item", category="Weapons", index=1, item={**sh["char"]["gear"]["Weapons"][1], "name": "My Colt"}))
check(not sh["char"]["gear"]["Weapons"][1].get("_custom"), "renaming an item does not flag it")
ev = A.test_client(); ch, n = pow_solve(ev)
r = ev.post("/api/login", json={"username": "admin", "password": "gm-password-123", "challenge": ch, "counter": n, "next": "/\\evil.com"})
check(j(r)["next"] == "/", "open redirect blocked")

print()
print("FAILED: %d" % len(FAILS) if FAILS else "All checks passed.")
sys.exit(1 if FAILS else 0)
