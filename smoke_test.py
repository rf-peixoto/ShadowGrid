"""End-to-end API smoke test: python smoke_test.py  (uses a throwaway database)."""
import json
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
from sr import catalog as CAT  # noqa: E402

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


def ref(name, cat=None):
    return next(e["id"] for e in CAT.ITEMS if e["name"] == name and (cat is None or e["cat"] == cat))


def item(sheet, name):
    return next((i for i in sheet["char"]["inventory"] if i["name"].startswith(name)), None)


def register(token, user):
    cl = A.test_client()
    ch, n = pow_solve(cl)
    r = cl.post(f"/api/invite/{token}", json={"username": user, "password": "runner-pass", "challenge": ch, "counter": n}, headers=H)
    return cl, r


gm = A.test_client()
print("GM")
check(login(gm, "admin", "nope").status_code == 401, "wrong GM password rejected")
check(login(gm, "admin", "gm-password-123").status_code == 200, "GM signs in")
cid = j(gm.post("/api/campaigns", json={"name": "Seattle 2081"}, headers=H))["id"]
check(gm.post("/api/campaigns", json={"name": "x"}).status_code == 403, "CSRF header required")
cells = {f"{c},{r}": {"fill": "#123456"} for c in range(6) for r in range(3)}
cells["1,0"]["doors"] = {"0": {"color": "#2de2e6", "open": False}}
mid = j(gm.post("/api/maps", json={"name": "Warehouse", "campaignId": cid, "width": 10, "height": 8,
                                   "data": {"cells": cells,
                                            "markers": [{"id": "e1", "c": 4, "r": 2, "type": "enemy", "cm": {"pm": 10, "sm": 9, "ov": 3}},
                                                        {"id": "e2", "c": 5, "r": 2, "type": "enemy", "label": "Cop"}]}},
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
_, r = register(inv["token"], "ana2")
check(r.status_code == 410, "invite is single use")
check(pl.get("/api/overview").status_code == 401, "player can't reach GM API")
check(pl.get("/").status_code == 302, "player redirected away from GM home")
st = j(pl.get("/api/me/state"))
pid = st["me"]["id"]
check(st["me"]["status"] == "draft", "new sheet is a draft")
check(st["view"]["map"] is None, "no map until GM places token")
cat = j(pl.get("/api/catalog"))
check(len(cat["store"]["items"]) > 400 and cat["wiki"]["topics"].get("Wild Die"), "catalog has the core-book store and wiki")

print("Sheet (draft)")
act = lambda **kw: pl.post("/api/me/sheet/action", json=kw, headers=H)  # noqa: E731
r = act(action="set_info", name="Ana Rios", metatype="Elf", role="Street Samurai")
check(r.status_code == 200 and j(r)["char"]["name"] == "Ana Rios", "set name/metatype/role")
check(any(q["name"] == "Low-Light Vision" and q.get("racial") for q in j(r)["derived"]["qualities"]), "elf gets racial low-light vision")
r = act(action="set_attribute", attr="Agility", value=9)
check(j(r)["char"]["attributes"]["Agility"] == 7, "elf Agility capped at metatype maximum 7")
r = act(action="set_attribute", attr="Body", value=9)
check(j(r)["char"]["attributes"]["Body"] == 6, "elf Body capped at 6")
act(action="set_attribute", attr="Reaction", value=4)
act(action="set_attribute", attr="Intuition", value=4)
act(action="set_attribute", attr="Logic", value=3)
act(action="set_attribute", attr="Charisma", value=4)
act(action="set_attribute", attr="Willpower", value=3)
act(action="set_attribute", attr="Edge", value=4)
r = act(action="set_skill", skill="Firearms", rank=9)
check(j(r)["char"]["skills"]["Firearms"] == 6, "creation skill cap 6")
act(action="set_spec", skill="Firearms", spec="Pistols")
r = act(action="set_expertise", skill="Firearms")
check(j(r)["char"]["expertise"].get("Firearms") == "Pistols", "specialization turned into expertise")
r = act(action="set_spec", skill="Firearms", spec="Rifles")
sh = j(r)
pool = next(p for p in sh["pools"] if p["key"] == "exp:Firearms:Pistols")
check(pool["value"] == 7 + 6 + 3, "expertise adds +3")
act(action="set_skill", skill="Biotech", rank=3)
r = act(action="buy", ref=ref("Ares Predator VI"))
check(j(r)["char"]["nuyen"] == 4250, "store purchase deducts price")
r = act(action="buy", ref=ref("Cyberjack 6"))
check(r.status_code == 400, "creation: Availability above 6 refused")
r = act(action="buy", ref=ref("Wired Reflexes 1"))
check(r.status_code == 400 and "Not enough nuyen" in j(r)["error"], "can't buy without nuyen")
r = act(action="admin_set", karma=999)
check(r.status_code == 403, "player can't use GM override")
pred = item(j(act(action="set_info")), "Ares Predator VI")
r = act(action="remove_item", uid=pred["uid"])
check(j(r)["char"]["nuyen"] == 5000, "draft refund on removal")
sh = j(act(action="buy", ref=ref("Ares Predator VI")))
sh = j(act(action="buy", ref=ref("Regular rounds (Heavy Pistol / SMG)"), qty=3))
check(item(sh, "Regular rounds (Heavy")["qty"] == 30, "ammo comes in boxes of 10")
sh = j(act(action="buy", ref=ref("Armor Jacket")))
check(sh["derived"]["defense_rating"] == 6 + 4, "armor adds to Defense Rating")
sh = j(act(action="buy", ref=ref("Medkit"), rating=3))
check(item(sh, "Medkit 3") is not None, "rated item bought at chosen rating")
pred = item(sh, "Ares Predator VI")
sh = j(act(action="reload", uid=pred["uid"]))
check(item(sh, "Ares Predator VI")["loaded"]["rounds"] == 15 and item(sh, "Regular rounds (Heavy")["qty"] == 15, "reload moves rounds into the gun")
r = act(action="add_quality", quality="Analytical Mind")
check(j(r)["char"]["karma"] == 47, "positive quality costs karma")
r = act(action="add_knowledge", name="Seattle Gangs")
check("Seattle Gangs" in j(r)["char"]["knowledge"], "knowledge skill added")
r = act(action="set_language", name="Sperethiel", level="Native")
check(j(r)["char"]["languages"][0]["level"] == "Native", "native language at creation")
r = act(action="save_contact", contact={"name": "Big Mike", "type": "Arms Dealer", "connection": 4, "loyalty": 2, "supply": ["Weapons"]})
check(j(r)["char"]["contacts"][0]["supply"] == ["Weapons"], "contact with supply category")
r = pl.post("/api/me/submit", json={"submit": True}, headers=H)
check(j(r)["player"]["status"] == "waiting", "player submits for approval")
check(j(gm.get("/api/overview"))["games"][0]["waiting"] == 1, "GM sees one sheet waiting")

print("Approval, store access, selling")
r = gm.post(f"/api/players/{pid}/review", json={"decision": "approve"}, headers=H)
check(j(r)["approved"] is True, "GM approves")
edge_max = j(r)["derived"]["edge_max"]
check(j(r)["char"]["current_edge"] == edge_max, "approval fills Edge")
r = act(action="set_attribute", attr="Body", value=5)
check(r.status_code == 400, "approved: free attribute edit blocked")
karma = j(pl.get("/api/me/sheet"))["char"]["karma"]
r = act(action="raise_attribute", attr="Willpower")
check(r.status_code == 200 and j(r)["char"]["karma"] == karma - 20, "approved: raise 3→4 costs 20 Karma")
r = act(action="raise_attribute", attr="Agility")
check(r.status_code == 400, "can't raise past the metatype maximum")
r = act(action="buy", ref=ref("Katana"))
check(r.status_code == 200, "Availability 3 weapon via a Connection 4 weapons contact")
r = act(action="buy", ref=ref("Monofilament Whip"))
check(r.status_code == 400 and "Connection 7" in j(r)["error"], "Availability 6(I) needs Connection 7")
r = act(action="buy", ref=ref("Lined Coat"))
check(r.status_code == 200, "legal Availability 2 needs no contact")
r = act(action="save_contact", contact={"name": "Nails", "type": "Fixer", "connection": 8, "loyalty": 3, "supply": ["Fixer"]})
check(not j(r)["char"]["contacts"][1]["verified"] and j(r)["player"]["pendingContacts"] == 1, "new contact after approval waits for the GM")
r = act(action="buy", ref=ref("Monofilament Whip"))
check(r.status_code == 400 and "once the GM confirms" in j(r)["error"], "unconfirmed contact unlocks nothing, and says why")
gm.post(f"/api/players/{pid}/sheet/action", json={"action": "admin_set", "nuyen": 5000}, headers=H)
r = gm.post(f"/api/players/{pid}/sheet/action", json={"action": "verify_contact", "index": 1}, headers=H)
check(j(r)["char"]["contacts"][1]["verified"], "GM confirms the contact")
r = act(action="buy", ref=ref("Monofilament Whip"))
check(r.status_code == 200, "confirmed fixer unlocks it")
r = gm.post(f"/api/players/{pid}/sheet/action", json={"action": "save_contact", "contact": {"name": "Doc", "type": "Street Doc", "connection": 6, "loyalty": 2}}, headers=H)
sh = j(pl.get("/api/me/sheet"))
check(sh["store"][ref("Medkit")][0] and sh["store"][ref("Cyberjack 1")][0], "a contact's type sources its goods without ticking boxes")
r = act(action="buy_custom", item={"name": "Homebrew gun", "cat": "Ranged", "cost": 1})
check(r.status_code == 400, "no custom purchases after approval")
gm.put(f"/api/games/{cid}/settings", json={"sellPct": 60}, headers=H)
sh = j(pl.get("/api/me/sheet"))
check(sh["sellPct"] == 60, "GM sets the sell percentage")
before = sh["char"]["nuyen"]
r = act(action="sell_item", uid=item(sh, "Katana")["uid"])
check(j(r)["char"]["nuyen"] == before + 210, "sold for 60% of 350¥")
r = gm.post(f"/api/games/{cid}/lifestyle", json={}, headers=H)
sh = j(pl.get("/api/me/sheet"))
check(sh["char"]["nuyen"] == before + 210 - 2000, "monthly lifestyle charged (Low 2,000¥)")
gm.post(f"/api/players/{pid}/sheet/action", json={"action": "admin_set", "nuyen": 500}, headers=H)
gm.post(f"/api/games/{cid}/lifestyle", json={}, headers=H)
check(j(pl.get("/api/me/sheet"))["char"]["nuyen"] == -1500, "lifestyle can push nuyen negative")
gm.post(f"/api/players/{pid}/sheet/action", json={"action": "admin_set", "nuyen": 5000}, headers=H)
r = act(action="add_knowledge", name="Corporate Personalities")
check(r.status_code == 200 and any(e["reason"].startswith("Knowledge") and e["delta"] == -3 for e in j(r)["ledger"]), "approved: knowledge skill costs 3 Karma")

print("Dice, ammo, Edge")
r = pl.post("/api/me/roll", json={"key": "skill:Firearms", "wild": True, "threshold": 2}, headers=H)
check(r.status_code == 200, "skill roll")
roll = next(x for x in j(r)["rolls"] if x["id"] == j(r)["rollId"])
check(roll["data"]["pool"] == 13 and roll["data"]["dice"][0].get("w") == 1, "pool 7+6 and wild die present")
r = pl.post(f"/api/me/rolls/{roll['id']}/boost", json={"boost": "buy_hit"}, headers=H)
check(r.status_code == 200 and j(r)["me"]["edge"]["cur"] == edge_max - 3, "buy-hit boost spends 3 Edge")
r = pl.post(f"/api/me/rolls/{roll['id']}/boost", json={"boost": "buy_hit"}, headers=H)
check(r.status_code == 400, "one boost per roll")
gm.post(f"/api/games/{cid}/edge", json={"players": [pid], "action": "refresh"}, headers=H)
check(j(pl.get("/api/me/state"))["me"]["edge"]["cur"] == edge_max, "GM refresh Edge")
r = pl.post("/api/me/roll", json={"key": f"weapon:{pred['uid']}", "mode": "BF", "range": "Near"}, headers=H)
check(r.status_code == 200 and item(j(pl.get("/api/me/sheet")), "Ares Predator VI")["loaded"]["rounds"] == 11, "burst fire uses 4 rounds")
gm.post(f"/api/players/{pid}/sheet/action", json={"action": "set_ammo", "uid": pred["uid"], "rounds": 1}, headers=H)
r = pl.post("/api/me/roll", json={"key": f"weapon:{pred['uid']}", "mode": "SA"}, headers=H)
check(r.status_code == 400, "not enough rounds for semi-auto")
r = gm.post(f"/api/players/{pid}/sheet/action", json={"action": "give", "ref": ref("Fragmentation Grenade"), "qty": 1}, headers=H)
gren = item(j(r), "Fragmentation Grenade")
r = pl.post("/api/me/roll", json={"key": f"weapon:{gren['uid']}"}, headers=H)
check(r.status_code == 200 and item(j(pl.get("/api/me/sheet")), "Fragmentation Grenade") is None, "throwing the only grenade removes it")
r = pl.post("/api/me/initiative", json={}, headers=H)
check(r.status_code == 200 and j(r)["rolls"][0]["kind"] == "init", "initiative roll logged")
r = gm.post(f"/api/games/{cid}/roll", json={"dice": 8, "hidden": True, "label": "Guard perception"}, headers=H)
check(not any(x["data"].get("label") == "Guard perception" for x in j(pl.get("/api/me/state"))["rolls"]), "hidden GM roll invisible to player")

print("Damage and healing")
r = act(action="set_damage", track="stun", value=99)
d = j(r)["derived"]
check(d["stun_damage"] == d["stun_boxes"] and d["physical_damage"] > 0, "stun overflows into physical")
act(action="set_damage", track="stun", value=4)
r = act(action="set_damage", track="physical", value=0)
check(j(r)["derived"]["wound_modifier"] == -1, "wound modifier -1 per 3 boxes")
r = pl.post("/api/me/heal", json={"method": "first_aid"}, headers=H)
check(r.status_code == 200 and "threshold" in j(r)["message"], "first aid rolled against 5 - Essence")
r = pl.post("/api/me/heal", json={"method": "first_aid"}, headers=H)
check(r.status_code == 400, "first aid only once per set of injuries")
keys = {p["key"]: p for p in j(pl.get("/api/me/sheet"))["pools"]}
check(keys.get("medkit", {}).get("heal") == "medkit" and keys["first_aid"]["heal"] == "first_aid", "healing tests are dice-roller pools")
check(["Wireless medkit", 1] in keys["medkit"]["parts"], "medkit adds +1 (wireless)")
r = pl.post("/api/me/heal", json={"method": "medkit"}, headers=H)
check(r.status_code == 400 and "supplies" in j(r)["error"], "medkit needs supplies")
gm.post(f"/api/players/{pid}/sheet/action", json={"action": "give", "ref": ref("Medkit Supplies"), "qty": 2}, headers=H)
r = pl.post("/api/me/heal", json={"method": "medkit", "push": True}, headers=H)
if r.status_code == 400 and "Nothing to heal" in j(r)["error"]:
    act(action="set_damage", track="stun", value=4)
    r = pl.post("/api/me/heal", json={"method": "medkit", "push": True}, headers=H)
check(r.status_code == 200 and j(r)["rollId"], "medkit heal returns its roll")
sh = j(pl.get("/api/me/sheet"))
check(item(sh, "Medkit Supplies")["qty"] == 1, "medkit uses one set of supplies")
rb = pl.post(f"/api/me/rolls/{j(r)['rollId']}/boost", json={"boost": "buy_hit"}, headers=H)
check(rb.status_code == 400, "no Edge boost after a healing roll")
act(action="set_damage", track="stun", value=4)  # first aid may have healed it all
r = pl.post("/api/me/heal", json={"method": "natural_stun"}, headers=H)
check(r.status_code == 200, "rest heals Stun")
act(action="set_damage", track="stun", value=0)
r = pl.post("/api/me/heal", json={"method": "natural_stun"}, headers=H)
check(r.status_code == 400 and "Nothing to heal" in j(r)["error"], "nothing to heal is refused")

print("Old sheets")
_, r = register(j(gm.post(f"/api/games/{cid}/invites", json={}, headers=H))["token"], "oldie")
oid = j(_.get("/api/me/state"))["me"]["id"]
with A.app_context():
    from core import get_db
    get_db().execute("UPDATE players SET character=?, approved=2 WHERE id=?", (json.dumps({
        "name": "Old", "base_attributes": {"Body": 4}, "contacts": [{"name": "Jo", "type": "Fixer", "connection": 12, "loyalty": 9}],
        "gear": {"Weapons": [{"name": "Ares Predator V"}], "Other": [{"name": "Lucky coin"}]}}), oid))
    get_db().commit()
osh = j(gm.get(f"/api/players/{oid}/sheet"))
check(item(osh, "Ares Predator VI") and item(osh, "Ares Predator VI")["clip"] == 15, "old gear linked to the core-book item")
check(item(osh, "Lucky coin")["_custom"], "unknown old gear stays custom")
check(osh["store"][ref("Erika MCD-6")][0], "old Fixer contact unlocks the store")
r = _.post("/api/me/sheet/action", json={"action": "reload", "uid": item(osh, "Ares Predator VI")["uid"]}, headers=H)
check(r.status_code == 400 and "no ammunition" in j(r)["error"], "old pistol takes Heavy ammo")

print("Magic")
_, r = register(j(gm.post(f"/api/games/{cid}/invites", json={}, headers=H))["token"], "mage")
mg = _
mact = lambda **kw: mg.post("/api/me/sheet/action", json=kw, headers=H)  # noqa: E731
mact(action="set_info", name="Merlin", magic_type="Magician", tradition="Hermetic")
mact(action="set_attribute", attr="Magic", value=5)
mact(action="set_attribute", attr="Logic", value=5)
mact(action="set_attribute", attr="Willpower", value=4)
mact(action="set_skill", skill="Sorcery", rank=5)
mact(action="set_skill", skill="Conjuring", rank=4)
r = mact(action="learn_spell", name="Manabolt")
check(r.status_code == 200 and j(r)["char"]["spells"][0]["drain"] == 4, "learn Manabolt (drain 4)")
r = mg.post("/api/me/roll", json={"key": "spell:0"}, headers=H)
check(r.status_code == 200 and any("drain from Manabolt" in (x["data"].get("text") or "") for x in j(r)["rolls"]), "drain rolled after casting")
r = mact(action="summon", type="Fire", force=3)
check(r.status_code == 200 and any("summoned a Force 3 Fire spirit" in (x["data"].get("text") or "") for x in j(mg.get("/api/me/state"))["rolls"]), "summoning rolled and logged")
r = mact(action="initiate", pick="Centering")
check(j(r)["char"]["initiation_grade"] == 1 and j(r)["derived"]["max"]["Magic"] == 7, "initiation raises the Magic maximum")
mpid = j(mg.get("/api/me/state"))["me"]["id"]

print("Map, tracker, combat")
r = gm.post(f"/api/players/{pid}/place", json={"mapId": mid, "c": 0, "r": 0}, headers=H)
check(r.status_code == 200, "GM places token")
st = j(pl.get("/api/me/state"))
check(st["view"]["map"] and st["view"]["token"] == {"c": 0, "r": 0}, "player sees map + token")
check(not any(m["id"] == "e1" for m in st["view"]["map"]["markers"]), "unexplored enemy hidden")
r = gm.post(f"/api/maps/{mid}/marker", json={"id": "e2", "template": "t:6"}, headers=H)
mk = j(r)["marker"]
check(mk["npc"]["template"] == "Lone Star Patrolman" and mk["cm"]["grunt"] and mk["cm"]["pm"] == 10, "marker gets a grunt template")
r = pl.post("/api/me/move", json={"c": 5, "r": 2}, headers=H)
check(r.status_code == 200 and any(m["id"] == "e2" and "npc" not in m for m in j(r)["map"]["markers"]), "player sees the marker but not its stats")
r = gm.post(f"/api/maps/{mid}/marker", json={"id": "e1", "damage": {"track": "stun", "amount": 12}}, headers=H)
check(j(r)["marker"]["cm"]["s"] == 9 and j(r)["marker"]["cm"]["p"] == 3, "enemy stun overflow")
r = gm.post(f"/api/games/{cid}/combat", json={"op": "start", "players": [pid], "mapId": mid, "markers": ["e1", "e2"], "roll": True}, headers=H)
tr = j(r)["tracker"]
check(tr["active"] and len(tr["entries"]) == 3, "combat started with a runner and two markers")
check(j(pl.get("/api/me/state"))["view"]["tracker"] is None, "tracker hidden from players until shown")
e1 = next(e for e in tr["entries"] if e["ref"] == "e1")
gm.post(f"/api/games/{cid}/combat", json={"op": "set", "id": e1["id"], "hidden": True}, headers=H)
gm.post(f"/api/games/{cid}/combat", json={"op": "show"}, headers=H)
pl.post("/api/me/initiative", json={}, headers=H)
ptr = j(pl.get("/api/me/state"))["view"]["tracker"]
check(ptr and len(ptr["entries"]) == 2 and all(e["ref"] != "e1" for e in ptr["entries"]), "players see the tracker without hidden enemies")
check(next(e for e in ptr["entries"] if e["ref"] == pid)["total"] is not None, "player's initiative roll lands in the tracker")
r = gm.post(f"/api/games/{cid}/combat", json={"op": "next"}, headers=H)
check(r.status_code == 200, "tracker advances")
opts = j(gm.post(f"/api/maps/{mid}/attack-options", json={"who": {"kind": "player", "id": pid}}, headers=H))["options"]
check(any(o["key"] == f"weapon:{pred['uid']}" for o in opts), "attack options list the runner's weapons")
gm.post(f"/api/players/{pid}/sheet/action", json={"action": "set_ammo", "uid": pred["uid"], "rounds": 15}, headers=H)
r = gm.post(f"/api/maps/{mid}/attack", json={"attacker": {"kind": "player", "id": pid}, "weapon": f"weapon:{pred['uid']}", "mode": "SA",
                                             "range": "Near", "target": {"kind": "marker", "id": "e2"}}, headers=H)
res = j(r)["result"]
check(r.status_code == 200 and res["ar"] == 8 and res["dr"] == 6, "GM attack: semi-auto AR 10-2 vs Defense Rating 6")
check(item(j(pl.get("/api/me/sheet")), "Ares Predator VI")["loaded"]["rounds"] == 13, "GM attack spends the runner's ammo")
mk = next(m for m in j(gm.get(f"/api/maps/{mid}"))["data"]["markers"] if m["id"] == "e2")
check(mk["cm"]["p"] == res.get("damage", 0) or mk["cm"]["p"] == mk["cm"]["pm"], "damage applied to the marker monitor")
r = gm.post(f"/api/maps/{mid}/attack", json={"attacker": {"kind": "marker", "id": "e2"}, "weapon": "0", "range": "Near",
                                             "target": {"kind": "player", "id": pid}, "attackMod": 30}, headers=H)
res = j(r)["result"]
dmg_before = j(pl.get("/api/me/sheet"))["derived"]["physical_damage"]
check(r.status_code == 200 and res["hit"], "NPC attacks the runner")
r = gm.post(f"/api/maps/{mid}/attack", json={"attacker": {"kind": "player", "id": mpid}, "weapon": "spell:0", "range": "Near",
                                             "target": {"kind": "marker", "id": "e2"}}, headers=H)
check(r.status_code == 200 and "drain" in j(r)["result"], "GM-resolved combat spell rolls the caster's drain")
r = gm.post(f"/api/maps/{mid}/status", json={"target": {"kind": "player", "id": pid}, "status": "Prone", "on": True}, headers=H)
check(j(pl.get("/api/me/state"))["me"]["statuses"].get("Prone"), "GM sets a status on a runner")
gm.post(f"/api/maps/{mid}/status", json={"target": {"kind": "marker", "id": "e2"}, "status": "Burning", "on": True, "value": 3}, headers=H)
st = j(pl.get("/api/me/state"))
check(next(m for m in st["view"]["map"]["markers"] if m["id"] == "e2").get("statuses", {}).get("Burning") == 3, "players see marker statuses")
check(any(x["kind"] == "attack" for x in st["rolls"]), "attacks appear in the table log")

print("Editor does not overwrite live changes")
m = j(gm.get(f"/api/maps/{mid}"))
stale = m["data"]
pl.post("/api/me/move", json={"c": 1, "r": 0}, headers=H)
pl.post("/api/me/door", json={"edge": 0}, headers=H)
gm.post(f"/api/maps/{mid}/marker", json={"id": "e1", "damage": {"track": "physical", "amount": 1}}, headers=H)
gm.put(f"/api/maps/{mid}", json={"data": stale}, headers=H)
m2 = j(gm.get(f"/api/maps/{mid}"))["data"]
door = (m2["cells"].get("1,0") or {}).get("doors", {}).get("0") or next((c.get("doors", {}).get("2") for k, c in m2["cells"].items() if c.get("doors")), None)
check(door and door["open"], "player-opened door survives an editor autosave")
check(next(x for x in m2["markers"] if x["id"] == "e1")["cm"]["p"] == 4, "marker damage survives an editor autosave")
gm.put(f"/api/maps/{mid}", json={"data": stale, "runtime": {"markers": ["e1"]}}, headers=H)
check(next(x for x in j(gm.get(f"/api/maps/{mid}"))["data"]["markers"] if x["id"] == "e1")["cm"]["p"] == 3, "editor's own monitor edit is kept")

print("Runs")
r = gm.post(f"/api/games/{cid}/runs", json={"name": "Data steal", "reward": 10000, "assignees": [pid],
                                           "tasks": [{"description": "Get in", "mandatory": True}, {"description": "No alarms"}]}, headers=H)
rid = j(r)["id"]
check(len(j(pl.get("/api/me/runs"))["runs"]) == 1, "assigned player sees run")
check(gm.post(f"/api/runs/{rid}/complete", json={}, headers=H).status_code == 400, "can't complete before mandatory tasks")
gm.put(f"/api/runs/{rid}", json={"tasks": [{"description": "Get in", "mandatory": True, "completed": True}, {"description": "No alarms"}]}, headers=H)
before = j(pl.get("/api/me/sheet"))["char"]["nuyen"]
r = gm.post(f"/api/runs/{rid}/complete", json={}, headers=H)
check(j(r)["payout"] == 5000, "payout scales with tasks (1/2)")
check(j(pl.get("/api/me/sheet"))["char"]["nuyen"] == before + 5000, "runner paid")
check(pl.put(f"/api/runs/{rid}", json={"name": "x"}, headers=H).status_code == 401, "player can't edit runs")
check(gm.post(f"/api/runs/{rid}/complete", json={}, headers=H).status_code == 400, "a completed run can't be paid twice")

print("Accounts and Edge")
pw = j(gm.post(f"/api/players/{pid}/password", headers=H))["password"]
check(pl.get("/api/me/state").status_code == 401, "password reset signs the player out")
check(login(pl, "ana", pw).status_code == 200, "player signs in with new password")
r = pl.post("/api/me/password", json={"current": pw, "new": "brand-new-pass"}, headers=H)
check(r.status_code == 200 and pl.get("/api/me/state").status_code == 200, "player changes password and stays signed in")
gm.post(f"/api/players/{pid}/sheet/action", json={"action": "admin_set", "current_edge": 7}, headers=H)
gm.post(f"/api/players/{mpid}/sheet/action", json={"action": "admin_set", "current_edge": 7}, headers=H)
r = pl.post("/api/me/edge", json={"key": "give", "to": mpid}, headers=H)
check(r.status_code == 400 and j(pl.get("/api/me/state"))["me"]["edge"]["cur"] == 7, "can't give Edge to an ally at 7")
ev = A.test_client()
ch, n = pow_solve(ev)
r = ev.post("/api/login", json={"username": "admin", "password": "gm-password-123", "challenge": ch, "counter": n, "next": "/\\evil.com"})
check(j(r)["next"] == "/", "open redirect blocked")

print()
print("FAILED: %d" % len(FAILS) if FAILS else "All checks passed.")
sys.exit(1 if FAILS else 0)
