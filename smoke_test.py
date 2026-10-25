"""End-to-end API smoke test: python smoke_test.py  (uses a throwaway database)."""
import hashlib
import io
import json
import os
import sys
import tempfile

tmp = tempfile.mkdtemp()
os.environ["SHADOWGRID_DATA"] = tmp
os.environ["SHADOWGRID_DB"] = os.path.join(tmp, "test.db")
os.environ["SHADOWGRID_GAMEMASTER_PASSWORD"] = "gm-password-123"
os.environ["SHADOWGRID_LOGIN_POW_BITS"] = "6"
os.environ["SHADOWGRID_GATE_BITS"] = "8"
os.environ["SHADOWGRID_GATE_PUZZLES"] = "4"

import app as appmod  # noqa: E402
from security import leading_zero_bits  # noqa: E402
from sr import catalog as CAT  # noqa: E402

A = appmod.app
H = {"X-Requested-With": "ShadowGrid"}
FAILS = []


def check(cond, msg, detail=None):
    print(("  ok   " if cond else "  FAIL ") + msg + (f"  [{detail}]" if detail is not None and not cond else ""))
    if not cond:
        FAILS.append(msg)


def gate_counters(ch):
    out = []
    for i in range(ch["puzzles"]):
        n = 0
        while leading_zero_bits(hashlib.sha256(f"{ch['challenge']}:{i}:{n}".encode()).digest()) < ch["bits"]:
            n += 1
        out.append(n)
    return out


def gate_solve(cl):
    import security
    security._buckets.clear()
    ch = cl.get("/api/gate/challenge").get_json()
    return cl.post("/api/gate", json={"challenge": ch["challenge"], "counters": gate_counters(ch)}, headers=H)


def pow_solve(cl):
    r = cl.get("/api/login/challenge")
    if r.status_code == 403:
        gate_solve(cl)
        r = cl.get("/api/login/challenge")
    ch = r.get_json()
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


print("Gate")
import security  # noqa: E402
gt = A.test_client()
r = gt.get("/login")
check(r.status_code == 302 and r.headers["Location"].startswith("/gate?next=/login"), "the sign-in page sends a new browser to the gate")
check(gt.get("/api/login/challenge").status_code == 403 and j(gt.post("/api/login", json={}, headers=H))["gate"], "sign-in API refused without the gate")
check(gt.get("/gate").status_code == 200, "gate page opens")
ch = j(gt.get("/api/gate/challenge"))
check(ch["bits"] == 8 and ch["puzzles"] == 4, "gate difficulty from the environment")
cs = gate_counters(ch)
check(gt.post("/api/gate", json={"challenge": ch["challenge"], "counters": cs[:-1] + ["x"]}, headers=H).status_code == 400, "a wrong answer fails")
check(gt.post("/api/gate", json={"challenge": ch["challenge"], "counters": cs}, headers=H).status_code == 400, "a challenge is single use")
security._buckets.clear()
ch = j(gt.get("/api/gate/challenge")); cs = gate_counters(ch)
r = gt.post("/api/gate", json={"challenge": ch["challenge"], "counters": cs, "next": "//evil.com"}, headers=H)
check(r.status_code == 200 and j(r)["next"] == "/login", "the gate opens and refuses foreign redirects")
check(gt.get("/login").status_code == 200 and gt.get("/gate").status_code == 302, "after the gate the sign-in page opens")
for _ in range(security.GATE_MAX_FAILS):
    login(gt, "gamemaster", "wrong")
check(gt.get("/login").status_code == 302, "too many wrong passwords close the gate again")
gate_solve(gt)
check(login(gt, "gamemaster", "gm-password-123").status_code == 200 and gt.get("/").status_code == 200, "GM signs in after the gate")
check(gt.get("/gate").status_code == 302, "signed in: no gate")
gt.post("/logout", headers=H)
check(gt.get("/login").status_code == 302, "signing out needs the gate again")
gate_solve(gt); login(gt, "gamemaster", "gm-password-123")
with gt.session_transaction() as sess:
    sess["t0"] -= 25 * 3600
check(gt.get("/").status_code == 302, "a sign-in older than SESSION_MAX_HOURS ends")
check(A.permanent_session_lifetime.total_seconds() == 12 * 3600, "sessions last 12 idle hours by default")

gm = A.test_client()
print("GM")
check(login(gm, "gamemaster", "nope").status_code == 401, "wrong GM password rejected")
check(login(gm, "gamemaster", "gm-password-123").status_code == 200, "GM signs in")
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
check(pl.get(f"/invite/{inv['token']}").status_code == 302, "the invite page sends a new browser to the gate")
gate_solve(pl)
check(pl.get(f"/invite/{inv['token']}").status_code == 200, "invite page opens after the gate")
ch, n = pow_solve(pl)
r = pl.post(f"/api/invite/{inv['token']}", json={"username": "gamemaster", "password": "longenough", "challenge": ch, "counter": n}, headers=H)
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
r = act(action="gamemaster_set", karma=999)
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
gm.post(f"/api/players/{pid}/sheet/action", json={"action": "gamemaster_set", "nuyen": 5000}, headers=H)
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
gm.post(f"/api/players/{pid}/sheet/action", json={"action": "gamemaster_set", "nuyen": 500}, headers=H)
gm.post(f"/api/games/{cid}/lifestyle", json={}, headers=H)
check(j(pl.get("/api/me/sheet"))["char"]["nuyen"] == -1500, "lifestyle can push nuyen negative")
gm.post(f"/api/players/{pid}/sheet/action", json={"action": "gamemaster_set", "nuyen": 5000}, headers=H)
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

print("Sixth World Companion")
import security  # noqa: E402
security._buckets.clear()
sw, r = register(j(gm.post(f"/api/games/{cid}/invites", json={}, headers=H))["token"], "swc")
swid = j(sw.get("/api/me/state"))["me"]["id"]
sact = lambda **kw: sw.post("/api/me/sheet/action", json=kw, headers=H)  # noqa: E731
k0 = j(sw.get("/api/me/sheet"))["char"]["karma"]
r = sact(action="set_info", metatype="Minotaur")
d = j(r)["derived"]
check(j(r)["char"]["karma"] == k0 - 5 and d["max"]["Body"] == 10 and d["max"]["Strength"] == 9, "metavariant: Minotaur costs 5 Karma, new maximums")
check(any(w["name"] == "Horns" for w in d["natural_weapons"]) and any(p["key"].startswith("natural:") for p in j(r)["pools"]), "natural weapon from a racial quality")
check(d["physical_boxes"] == 8 + 1 + 2, "Built Tough 2 from the variant")
r = sact(action="set_info", metatype="Human")
check(j(r)["char"]["karma"] == k0, "changing back refunds the variant Karma")
r = sact(action="set_info", metatype="Naga")
check(j(r)["derived"]["defense_rating"] >= 5 and j(r)["derived"]["movement"]["walk"] == 5, "metasapient: Naga armor and movement")
sact(action="set_info", metatype="Human")
r = sact(action="set_infected", infected="Banshee")
check(r.status_code == 400 and "Elf" in j(r)["error"], "Infected need the right base metatype")
r = sact(action="set_infected", infected="Ghoul")
d = j(r)["derived"]
check(r.status_code == 200 and d["essence"] == 5 and d["attributes"]["Magic"] >= 1 and d["max"]["Body"] == 10, "Ghoul: Essence 5, Magic 1, new maximums")
check(d["infected"]["name"] == "Ghoul" and d["lifestyle_mult"] >= 1.3 and any(w["name"] == "Claws" for w in d["natural_weapons"]), "Ghoul powers, weapons and lifestyle")
r = sact(action="set_info", magic_type="Technomancer")
check(r.status_code == 400, "Infected can't be technomancers")
r = sact(action="set_infected", infected="")
check(j(r)["derived"]["infected"] is None and j(r)["derived"]["essence"] == 6, "infection removed")
r = sact(action="add_quality", quality="Shiva Arms", level=2)
d = j(r)["derived"]
check(d["max"]["Body"] == 8 and d["max"]["Strength"] == 8, "Shiva Arms raises Body and Strength maximums")
r = sact(action="add_quality", quality="Bark")
check(j(r)["derived"]["price_markup"][1] > 0.2, "Bark and Shiva Arms raise fitted gear prices")
r = sact(action="add_quality", quality="Gender Transmorphism")
check(r.status_code == 400 or "racial" in str(j(r)), "racial-only traits can't be bought")
gm.post(f"/api/games/{cid}/grant", json={"players": [swid], "nuyen": 400000, "reason": "PACKs"}, headers=H)
store = j(sw.get("/api/me/sheet"))["store"]
check(store["pack-street-samurai-pack"][0], "a creation-legal PACK is on sale")
n0 = j(sw.get("/api/me/sheet"))["char"]["nuyen"]
r = sact(action="buy_pack", ref="pack-ares-predator-vi-quiet-pack")
sh = j(r)
gun = item(sh, "Ares Predator VI")
gel = next((i for i in sh["char"]["inventory"] if i["name"].startswith("Gel rounds (Heavy")), None)
check(r.status_code == 200 and gun and gel and gel["qty"] == 100, "weapon PACK: pistol, accessories and 100 gel rounds")
check(sh["char"]["nuyen"] < n0 and abs((n0 - sh["char"]["nuyen"]) - 1750 * (1 + sh["derived"]["price_markup"][0])) < 2, "PACK charges the PACK price")
r = sact(action="buy_pack", ref="pack-cybereyes-pack-c", grade="Alphaware")
eyes = item(j(r), "Cybereyes 3")
check(r.status_code == 200 and eyes and eyes["grade"] == "Alphaware", "augmentation PACK in Alpha grade")
r = sact(action="save_contact", contact={"name": "Ivy", "type": "Deckmeister", "connection": 6, "loyalty": 2})
check(any(ct["name"] == "Ivy" for ct in j(r)["char"]["contacts"]), "new contact archetypes are contact types")
tpl = j(gm.get(f"/api/maps/{mid}/context"))
names = [t["name"] for t in j(gm.get("/api/catalog"))["npcTemplates"]]
check("Artificer" in names and "Ghoul (Human, Infected)" in names, "Companion contacts and Infected are NPC templates")
wiki = j(gm.get("/api/catalog"))["wiki"]["topics"]
check("Minotaur" in wiki and "Ghoul (Infected)" in wiki and "Street Samurai PACK" in wiki and "Glamour (quality)" in wiki, "wiki covers the Companion")

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
gm.post(f"/api/maps/{mid}/marker", json={"id": "e2", "cm": dict(mk["cm"], p=0, s=0)}, headers=H)      # back on its feet to shoot back
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
gm.post(f"/api/players/{pid}/place", json={"mapId": mid, "c": 1, "r": 0}, headers=H)     # in combat and Prone: the GM moves them
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
gm.post(f"/api/players/{pid}/sheet/action", json={"action": "gamemaster_set", "current_edge": 7}, headers=H)
gm.post(f"/api/players/{mpid}/sheet/action", json={"action": "gamemaster_set", "current_edge": 7}, headers=H)
r = pl.post("/api/me/edge", json={"key": "give", "to": mpid}, headers=H)
check(r.status_code == 400 and j(pl.get("/api/me/state"))["me"]["edge"]["cur"] == 7, "can't give Edge to an ally at 7")
ev = A.test_client()
ch, n = pow_solve(ev)
r = ev.post("/api/login", json={"username": "gamemaster", "password": "gm-password-123", "challenge": ch, "counter": n, "next": "/\\evil.com"})
check(j(r)["next"] == "/", "open redirect blocked")

print("Character files, printing, live updates")
security._buckets.clear()
login(pl, "ana", "brand-new-pass")
r = pl.get("/api/me/sheet/export")
check(r.status_code == 200 and "attachment" in r.headers.get("Content-Disposition", ""), "player exports a character file")
exported = r.get_json()
check(exported["format"] == "shadowgrid-character-3" and exported["character"]["name"], "export holds the character")
r = pl.post("/api/me/sheet/import", data=json.dumps(exported), headers=H)
check(r.status_code == 400 and "approved" in j(r)["error"], "approved players can't import over their sheet")
fresh, _ = register(j(gm.post(f"/api/games/{cid}/invites", json={}, headers=H))["token"], "importer")
r = fresh.post("/api/me/sheet/import", data=json.dumps(exported), headers=H)
check(r.status_code == 200 and j(r)["char"]["name"] == exported["character"]["name"] and j(r)["char"].get("imported_at"), "a draft sheet imports the file")
bad = dict(exported, character=dict(exported["character"], v=1))
check(fresh.post("/api/me/sheet/import", data=json.dumps(bad), headers=H).status_code == 400, "files from another version are refused")
check(fresh.post("/api/me/sheet/import", data="nope", headers=H).status_code == 400, "garbage is refused")
r = gm.post(f"/api/players/{pid}/sheet/import", data=json.dumps(exported), headers=H)
check(r.status_code == 200, "the GM can import over an approved sheet")
check(pl.get("/print/sheet").status_code == 200 and pl.get("/print/blank").status_code == 200, "print pages open for a player")
check(gm.get(f"/print/sheet/{pid}").status_code == 200 and pl.get(f"/print/sheet/{pid}").status_code != 200, "only the GM prints other runners")
check(A.test_client().get("/api/events").status_code == 401, "live updates need a sign-in")

print("Combat rules: actions, interrupts, multiple attacks, sight, Edge")
security._buckets.clear()
login(pl, "ana", "brand-new-pass")
arena_cells = {f"{c},{r}": {"fill": "#123456"} for c in range(10) for r in range(3)}
for r_ in (0, 1, 2):
    arena_cells.pop(f"7,{r_}")                     # a wall across the room at column 7
arena = j(gm.post("/api/maps", json={"name": "Arena", "campaignId": cid, "width": 12, "height": 4, "data": {"cells": arena_cells, "markers": [
    {"id": "g1", "c": 4, "r": 1, "type": "danger", "label": "Ganger 1"}, {"id": "g2", "c": 5, "r": 1, "type": "danger", "label": "Ganger 2"},
    {"id": "g3", "c": 9, "r": 1, "type": "danger", "label": "Behind the wall"},
    {"id": "d0", "c": 3, "r": 2, "type": "danger", "label": "Drone", "cm": {"pm": 9, "sm": 0, "ov": 0, "p": 0, "s": 0}}]}}, headers=H))["id"]
for m_ in ("g1", "g2", "g3"):
    gm.post(f"/api/maps/{arena}/marker", json={"id": m_, "template": "t:6", "relabel": False}, headers=H)
gm.post(f"/api/players/{pid}/place", json={"mapId": arena, "c": 1, "r": 1}, headers=H)
gm.post(f"/api/players/{pid}/sheet/action", json={"action": "set_ammo", "uid": pred["uid"], "rounds": 15}, headers=H)
gm.post(f"/api/players/{pid}/sheet/action", json={"action": "gamemaster_set", "current_edge": 0}, headers=H)
gm.post(f"/api/players/{pid}/sheet/action", json={"action": "set_status", "status": "Prone", "on": False}, headers=H)
gm.post(f"/api/maps/{arena}/status", json={"target": {"kind": "player", "id": pid}, "status": "Prone", "on": False}, headers=H)
gm.post(f"/api/games/{cid}/combat", json={"op": "start", "players": [pid], "mapId": arena, "markers": ["g1", "g2", "g3"], "roll": True}, headers=H)
P, G1, G2, G3, D0 = ({"kind": "player", "id": pid}, {"kind": "marker", "id": "g1"}, {"kind": "marker", "id": "g2"},
                     {"kind": "marker", "id": "g3"}, {"kind": "marker", "id": "d0"})
gun = f"weapon:{pred['uid']}"
def atk(**kw):
    """The GM's attack in the arena; the attacker is patched up first (the out cold can't attack)."""
    a_ = kw.get("attacker") or {}
    if a_.get("kind") == "player":
        for tr_ in ("physical", "stun"):
            gm.post(f"/api/players/{a_['id']}/sheet/action", json={"action": "set_damage", "track": tr_, "value": 0}, headers=H)
    elif a_.get("kind") == "marker":
        mk_ = next((m for m in j(gm.get(f"/api/maps/{arena}"))["data"]["markers"] if m["id"] == a_["id"]), {})
        if mk_.get("cm"):
            gm.post(f"/api/maps/{arena}/marker", json={"id": a_["id"], "cm": dict(mk_["cm"], p=0, s=0)}, headers=H)
    return gm.post(f"/api/maps/{arena}/attack", json=dict({"range": "Near", "mode": "SA"}, **kw), headers=H)
entry = lambda ref: next(e for e in j(gm.get(f"/api/games/{cid}/combat"))["tracker"]["entries"] if e["ref"] == ref)  # noqa: E731
r = atk(attacker=P, weapon=gun, targets=[D0])
check(r.status_code == 200 and entry(pid)["majorLeft"] == 0, "an attack uses the attacker's Major Action")
r = atk(attacker=P, weapon=gun, targets=[D0])
check(r.status_code == 400 and "Major Action" in j(r)["error"], "a second attack in the round is refused")
check(atk(attacker=P, weapon=gun, targets=[D0], ignoreActions=True).status_code == 200, "the GM can override the action limit")
atk(attacker=P, weapon=gun, targets=[D0], ignoreActions=True)
check(j(pl.get("/api/me/state"))["me"]["edge"]["cur"] == 2 and entry(pid)["edgeGained"] == 2, "AR beating DR by 4+ gives Edge, 2 per round at most")
gm.post(f"/api/games/{cid}/combat", json={"op": "round"}, headers=H)
e_ = entry(pid)
check(e_["majorLeft"] == 1 and e_["edgeGained"] == 0, "a new round gives the actions back")
r = atk(attacker=P, weapon=gun, targets=[G1, G2])
res = j(r)["results"]
check(r.status_code == 200 and len(res) == 2 and any("Split among 2" in p[0] for p in res[0]["attack"]["parts"]), "multiple attacks split the pool between targets")
check(entry(pid)["minorLeft"] == e_["minorLeft"] - 1, "multiple attacks cost a Minor Action too")
check(item(j(pl.get("/api/me/sheet")), "Ares Predator VI")["loaded"]["rounds"] == 15 - 2 * 3 - 2 * 2, "each target takes a semi-auto burst of ammo")
r = atk(attacker=G1, weapon="0", targets=[P], defenses={f"player:{pid}": "block"})
check(r.status_code == 400 and "melee" in j(r)["error"], "Block only works against melee")
r = atk(attacker=G1, weapon="0", targets=[P], defenses={f"player:{pid}": "dodge"})
check(r.status_code == 200 and any(p_[0] == "Dodge" for p_ in j(r)["result"]["defense"]["parts"]), "Dodge adds Athletics to the defense")
r = atk(attacker=G2, weapon="0", targets=[P], defenses={f"player:{pid}": "full_defense"})
check(r.status_code == 400 and "Major" in j(r)["error"], "Full Defense needs a Major Action (already used)")
r = atk(attacker=G2, weapon="0", targets=[P], defenses={f"player:{pid}": "full_defense"}, ignoreActions=True)
check(r.status_code == 200 and entry(pid)["fd"], "Full Defense stays on for the round")
r = atk(attacker=G3, weapon="0", targets=[P], ignoreActions=True, ignoreSight=True)
check(any("Full Defense" in p_[0] for p_ in j(r)["result"]["defense"]["parts"]), "later attacks get Full Defense without asking")
gm.post(f"/api/games/{cid}/combat", json={"op": "round"}, headers=H)
r = atk(attacker=G1, weapon="0", targets=[P], defenses={f"player:{pid}": "hit_the_dirt"})
check(r.status_code == 200 and j(pl.get("/api/me/state"))["me"]["statuses"].get("Prone") and entry(pid)["dirt"], "Hit the Dirt: +2 defense, then Prone")
r = atk(attacker=P, weapon=gun, targets=[G2], called="damage")
pp = j(r)["result"]["attack"]["parts"]
check(any(p_[0] == "Hit the Dirt" for p_ in pp) and any(p_[0].startswith("Called shot") and p_[1] == -4 for p_ in pp), "the Hit the Dirt penalty and a called shot's −4 apply")
r = atk(attacker=P, weapon=gun, targets=[G2], called="vitals", ignoreActions=True)
check(r.status_code == 400 and "Edge" in j(r)["error"], "Vitals needs 5 Edge")
r = atk(attacker=P, weapon=gun, targets=[G3], ignoreActions=True)
check(r.status_code == 400 and "line of sight" in j(r)["error"], "no attack through a wall")
sg = j(gm.post(f"/api/maps/{arena}/sight", json={"a": P, "b": G2}, headers=H))["sight"]
check(sg["los"] and sg["cells"] == 4, "clear sight and distance between two combatants")
gm.post(f"/api/maps/{arena}/status", json={"target": G2, "status": "Cover", "on": True, "value": 2}, headers=H)
r = atk(attacker=P, weapon=gun, targets=[G2], ignoreActions=True)
check(j(r)["result"]["cover"] == 2 and j(r)["result"]["dr"] >= 8, "a Cover status adds to the Defense Rating")
gm.post(f"/api/maps/{arena}/status", json={"target": G1, "status": "Burning", "on": True, "value": 4}, headers=H)
r = gm.post(f"/api/games/{cid}/combat", json={"op": "ongoing"}, headers=H)
check("Ongoing" in j(r)["message"] and any("ongoing damage" in x["data"].get("text", "") for x in j(gm.get(f"/api/games/{cid}"))["rolls"]), "ongoing damage resolves at the GM's call")
gm.post(f"/api/maps/{arena}/status", json={"target": P, "status": "Zapped", "on": True}, headers=H)
pl.post("/api/me/initiative", json={}, headers=H)
check(any("from statuses" in x["data"].get("label", "") for x in j(pl.get("/api/me/state"))["rolls"] if x["kind"] == "init"), "statuses lower initiative")
check(any(p_[0] == "Zapped" for p_ in next(x for x in j(pl.get("/api/me/sheet"))["pools"] if x["key"] == "skill:Firearms")["parts"]), "statuses lower the roller's pools")
gm.post(f"/api/games/{cid}/combat", json={"op": "end"}, headers=H)
mg.post("/api/me/sheet/action", json={"action": "learn_spell", "name": "Armor"}, headers=H)
mage_sheet = j(mg.get("/api/me/sheet"))
sus = next((i for i, sp in enumerate(mage_sheet["char"]["spells"]) if sp.get("duration") == "S"), None)
check(sus is not None, "the mage knows a sustained spell")
if sus is not None:
    for _ in range(6):
        mg.post("/api/me/roll", json={"key": f"spell:{sus}", "mod": 20}, headers=H)
        if j(mg.get("/api/me/sheet"))["char"]["sustained"]:
            break
    msh = j(mg.get("/api/me/sheet"))
    check(msh["char"]["sustained"] and msh["derived"]["sustain_penalty"] == -2, "casting a sustained spell starts sustaining it (−2)")
    check(any(p_[0].startswith("Sustaining") for p_ in next(x for x in msh["pools"] if x["key"] == "skill:Perception")["parts"]), "sustaining costs dice on other tests")
    mg.post("/api/me/sheet/action", json={"action": "drop_sustained", "index": 0}, headers=H)
    check(not j(mg.get("/api/me/sheet"))["char"]["sustained"], "dropping the spell ends the penalty")

print("Matrix: actions, Overwatch, convergence, IC")
security._buckets.clear()
dk, _ = register(j(gm.post(f"/api/games/{cid}/invites", json={}, headers=H))["token"], "decker")
dkid = j(dk.get("/api/me/state"))["me"]["id"]
dact = lambda **kw: dk.post("/api/me/sheet/action", json=kw, headers=H)  # noqa: E731
gm.post(f"/api/games/{cid}/grant", json={"players": [dkid], "nuyen": 300000, "reason": "Deck money"}, headers=H)
dact(action="set_info", name="Glitch")
dact(action="set_attribute", attr="Logic", value=6)
dact(action="set_skill", skill="Cracking", rank=6)
dact(action="set_skill", skill="Electronics", rank=5)
r = dact(action="buy", ref="cyberdecks-software-erika-mcd-6")
dsh = j(r)
check(any(p_["key"] == "matrix:brute_force" for p_ in dsh["pools"]), "a deck gives Matrix action pools")
deck = item(dsh, "Erika MCD-6")
dact(action="set_matrix", device=deck["uid"], mode="VR (hot sim)")
r = dk.post("/api/me/roll", json={"key": "matrix:brute_force", "targetRating": 5}, headers=H)
res = next(x for x in j(r)["rolls"] if x["id"] == j(r)["rollId"])["data"]
check(r.status_code == 200 and res["defense"]["pool"] == 10, "an illegal action rolls the target's rating × 2 in defense")
gsh = j(gm.get(f"/api/players/{dkid}/sheet"))
check(gsh["derived"]["matrix"]["os"] == res["defense"]["hits"], "the defender's hits become Overwatch Score (GM view)")
check(j(dk.get("/api/me/sheet"))["derived"]["matrix"]["os"] is None, "players don't see their Overwatch Score")
gm.post(f"/api/players/{dkid}/sheet/action", json={"action": "set_os", "os": 39}, headers=H)
r = gm.post(f"/api/players/{dkid}/sheet/action", json={"action": "set_os", "delta": 2}, headers=H)
gsh = j(r)
check(gsh["message"] == "Convergence!" and gsh["derived"]["matrix"]["os"] == 0, "Overwatch 40: convergence, score reset")
check(item(gsh, "Erika MCD-6")["matrix_damage"] == gsh["derived"]["matrix"]["boxes"], "convergence bricks the deck")
check(gsh["char"]["matrix"]["mode"] == "AR" and gsh["char"]["physical_damage"] + gsh["char"]["stun_damage"] >= 0, "the decker is dumped (dumpshock in hot sim)")
gm.post(f"/api/players/{dkid}/sheet/action", json={"action": "set_matrix", "damage": 0}, headers=H)
gm.post(f"/api/players/{dkid}/sheet/action", json={"action": "set_matrix", "mode": "VR (hot sim)"}, headers=H)
gm.post(f"/api/players/{dkid}/place", json={"mapId": arena, "c": 2, "r": 0}, headers=H)
j(gm.post(f"/api/maps/{arena}/marker", json={"id": "d0", "template": "ic:Killer", "force": 4}, headers=H))
ic = next(m for m in j(gm.get(f"/api/maps/{arena}"))["data"]["markers"] if m["id"] == "d0")
check(ic["npc"]["kind"] == "IC" and ic["npc"]["matrix"]["rating"] == 4 and ic["cm"]["pm"] == 8, "IC templates by host rating (monitor = rating x 2)")
DK = {"kind": "player", "id": dkid}
opts = j(gm.post(f"/api/maps/{arena}/attack-options", json={"who": DK}, headers=H))["options"]
check(any(o["key"] == "matrix:data_spike" for o in opts), "Data Spike is an attack option for the decker")
r = gm.post(f"/api/maps/{arena}/attack", json={"attacker": DK, "weapon": "matrix:data_spike", "targets": [D0], "attackMod": 20}, headers=H)
res = j(r)["result"]
check(r.status_code == 200 and res["track"] == "matrix" and any(p_[0] == "Rating × 2" for p_ in res["defense"]["parts"]), "Data Spike vs IC: Matrix defense and damage")
check(j(gm.get(f"/api/players/{dkid}/sheet"))["derived"]["matrix"]["os"] == res["defense"]["hits"], "attacking IC raises Overwatch")
ic = next(m for m in j(gm.get(f"/api/maps/{arena}"))["data"]["markers"] if m["id"] == "d0")
gm.post(f"/api/maps/{arena}/marker", json={"id": "d0", "cm": dict(ic["cm"], p=0, s=0)}, headers=H)       # the spike may have crashed it
r = gm.post(f"/api/maps/{arena}/attack", json={"attacker": D0, "weapon": "0", "targets": [DK], "attackMod": 20}, headers=H)
res = j(r)["result"]
dsh = j(gm.get(f"/api/players/{dkid}/sheet"))
check(r.status_code == 200 and (not res["damage"] or item(dsh, "Erika MCD-6")["matrix_damage"] > 0), "Killer IC damages the deck")
r = gm.post(f"/api/maps/{arena}/attack", json={"attacker": D0, "weapon": "0", "targets": [DK], "defenses": {f"player:{dkid}": "dodge"}}, headers=H)
check(r.status_code == 400 and "Matrix" in j(r)["error"], "Dodge doesn't work in the Matrix")

print("Rigging: control modes, autosofts, vehicles on the map")
security._buckets.clear()
rg, _ = register(j(gm.post(f"/api/games/{cid}/invites", json={}, headers=H))["token"], "rigger")
rgid = j(rg.get("/api/me/state"))["me"]["id"]
ract = lambda **kw: rg.post("/api/me/sheet/action", json=kw, headers=H)  # noqa: E731
gm.post(f"/api/games/{cid}/grant", json={"players": [rgid], "nuyen": 300000, "reason": "Rigger money"}, headers=H)
ract(action="set_info", name="Wheels")
ract(action="set_skill", skill="Piloting", rank=5)
for ref_ in ("drones-gm-nissan-doberman", "cyberdecks-software-scratch-built-junk-rcc"):
    check(ract(action="buy", ref=ref_).status_code == 200, f"buy {ref_}")
rsh = j(ract(action="buy", ref="cyberware-control-rig", rating=2))
dob = item(rsh, "GM-Nissan Doberman")
keys = {p_["key"] for p_ in rsh["pools"]}
check(f"vehicle:{dob['uid']}:manual" in keys and f"vehicle:{dob['uid']}:remote" not in keys and f"drone:{dob['uid']}:Targeting" in keys,
      "piloting pools at the controls, and the drone's own Targeting pool")
jp = next(p_ for p_ in rsh["pools"] if p_["key"] == f"vehicle:{dob['uid']}:jumped")
check(any(x[0] == "Control rig 2" and x[1] == 2 for x in jp["parts"]), "jumped in: the control rig adds its rating")
soft = item(j(ract(action="buy", ref="cyberdecks-software-autosoft", rating=4)), "Autosoft")
r = ract(action="set_program", uid=soft["uid"], choice="Maneuvering")
dp = next((p_ for p_ in j(r)["pools"] if p_["key"] == f"drone:{dob['uid']}:Maneuvering"), None)
check(dp and dp["value"] == int(dob["pilot"]) + 4, "the drone pilots itself with Pilot + Maneuvering")
check(ract(action="set_program", uid=soft["uid"], choice="Armor").status_code == 400, "autosofts only take autosoft choices")
tl = j(gm.get(f"/api/maps/{arena}/context"))["vehicles"]
check(any(v["key"] == f"pv:{rgid}:{dob['uid']}" for v in tl), "the editor lists the runners' vehicles as templates")
r = gm.post(f"/api/maps/{arena}/marker", json={"id": "g3", "template": f"pv:{rgid}:{dob['uid']}", "relabel": True}, headers=H)
vm = j(r)["marker"]
check(vm["npc"]["kind"] == "Drone" and vm["npc"]["link"]["uid"] == dob["uid"] and vm["cm"]["pm"] == 8 + (int(dob["body"]) + 1) // 2, "a runner's drone on the map, linked to their sheet")
gm.post(f"/api/maps/{arena}/marker", json={"id": "g3", "damage": {"track": "physical", "amount": 3}}, headers=H)
check(item(j(rg.get("/api/me/sheet")), "GM-Nissan Doberman")["damage"] == 3, "damage on the map shows on the owner's sheet")
check(any(t["key"].startswith("v:") and t["kind"] == "Vehicle" for t in j(gm.get("/api/catalog"))["npcTemplates"]), "every vehicle and drone is an NPC template")
gm.post(f"/api/games/{cid}/combat", json={"op": "start", "players": [pid], "mapId": arena, "markers": ["g3"], "roll": True}, headers=H)
stunner = j(gm.post(f"/api/maps/{arena}/marker", json={"id": "g2", "template": "t:6"}, headers=H))["marker"]
r = gm.post(f"/api/maps/{arena}/attack", json={"attacker": G2, "weapon": "0", "targets": [G3], "ignoreSight": True, "ignoreActions": True, "attackMod": -30}, headers=H)
check(r.status_code == 200, "attacks against vehicles resolve")
gm.post(f"/api/games/{cid}/combat", json={"op": "end"}, headers=H)

print("Toxins, drugs, Reputation and Heat")
lib = [{"name": "Test Stunner", "kind": "toxin", "power": 30, "damage": "S", "vectors": ["Injection"], "effects": ["Nausea"]},
       {"name": "Test Jazz", "kind": "drug", "power": 6, "attrs": {"Reaction": 1}, "init_dice": 1, "duration": "10 minutes",
        "crash": {"dv": 3, "damage": "S"}}]
r = gm.put(f"/api/games/{cid}/substances", json={"substances": lib}, headers=H)
subs = j(r)["substances"]
check(r.status_code == 200 and any(x["name"] == "Renfield" and x.get("builtin") for x in subs) and len([x for x in subs if not x.get("builtin")]) == 2, "the GM saves a substance library (Companion ones built in)")
stun_id = next(x["id"] for x in subs if x["name"] == "Test Stunner")
jazz_id = next(x["id"] for x in subs if x["name"] == "Test Jazz")
rsh0 = j(gm.get(f"/api/players/{rgid}/sheet"))
r = gm.post(f"/api/players/{rgid}/expose", json={"id": stun_id}, headers=H)
rsh = j(r)
check(r.status_code == 200 and rsh["char"]["stun_damage"] > rsh0["char"]["stun_damage"] and rsh["char"]["statuses"].get("Nauseated"), "a toxin: resisted, the rest is Stun and Nausea")
check(rg.post("/api/me/dose", json={"id": jazz_id}, headers=H).status_code == 400, "you can't take a drug you don't carry")
gm.post(f"/api/players/{rgid}/sheet/action", json={"action": "give", "item": {"name": "Test Jazz", "cat": "Medical", "qty": 2}}, headers=H)
before = j(rg.get("/api/me/sheet"))["derived"]
r = rg.post("/api/me/dose", json={"id": jazz_id, "resist": False}, headers=H)
after = j(r)["derived"]
check(r.status_code == 200 and after["attributes"]["Reaction"] == before["attributes"]["Reaction"] + 1 and after["initiative_dice"] == before["initiative_dice"] + 1, "a drug's bonuses apply while it's in effect")
check(item(j(r), "Test Jazz")["qty"] == 1, "taking a dose uses one up")
s0 = j(r)["char"]["stun_damage"]
act_i = next(i for i, t in enumerate(j(r)["char"]["toxins"]) if t["name"] == "Test Jazz")
r = rg.post("/api/me/sheet/action", json={"action": "end_substance", "index": act_i}, headers=H)
check(j(r)["derived"]["attributes"]["Reaction"] == before["attributes"]["Reaction"] and j(r)["char"]["stun_damage"] == min(j(r)["derived"]["stun_boxes"], s0 + 3), "when it wears off, the crash applies")
st_i = next(i for i, t in enumerate(j(r)["char"]["toxins"]) if t["name"] == "Test Stunner")
r = gm.post(f"/api/players/{rgid}/sheet/action", json={"action": "end_substance", "index": st_i}, headers=H)
check(not j(r)["char"]["statuses"].get("Nauseated"), "when a toxin wears off, its statuses end")
r = rg.post("/api/me/sheet/action", json={"action": "set_info", "heat": 3}, headers=H)
check(r.status_code == 400 and "GM" in j(r)["error"], "players can't change their own Heat")
r = gm.post(f"/api/players/{rgid}/sheet/action", json={"action": "set_info", "heat": 3, "reputation": 2}, headers=H)
check(j(r)["char"]["heat"] == 3 and j(r)["char"]["reputation"] == 2, "the GM sets Heat and Reputation")

print("Handouts and sessions")
from PIL import Image as _Img  # noqa: E402


def _img(fmt):
    buf = io.BytesIO()
    _Img.new("RGB", (40, 30), (200, 30, 90)).save(buf, fmt)
    return buf.getvalue()


up = lambda name, data: gm.post(f"/api/games/{cid}/uploads", data={"file": (io.BytesIO(data), name)}, headers=H, content_type="multipart/form-data")  # noqa: E731
r = up("dossier.png", _img("PNG"))
check(r.status_code == 201 and j(r)["image"].endswith(".png"), "the GM uploads a PNG")
img = j(r)["image"]
check(up("photo.jpeg", _img("JPEG")).status_code == 201, "JPEG uploads too")
check(up("evil.svg", b"<svg onload=alert(1)>").status_code == 400, "other file types are refused")
check(up("fake.png", _img("JPEG")).status_code == 400, "a JPEG named .png is refused")
check(up("junk.jpg", b"not an image at all").status_code == 400, "junk named .jpg is refused")
r = gm.post(f"/api/games/{cid}/handouts", json={"title": "Dossier", "body": "# Target\n**Dr. K**", "image": img, "recipients": [pid]}, headers=H)
check(r.status_code == 201, "the GM writes a handout (hidden)")
hid = j(r)["id"]
check(not j(pl.get("/api/me/handouts"))["handouts"] and pl.get(f"/uploads/{img}").status_code == 404, "hidden handouts and their images stay private")
gm.put(f"/api/handouts/{hid}", json={"shown": True}, headers=H)
hs = j(pl.get("/api/me/state"))["handouts"]
check(len(hs) == 1 and hs[0]["image"] == img, "shown: the runner gets it with their state")
r = pl.get(f"/uploads/{img}")
check(r.status_code == 200 and r.mimetype == "image/png" and "sandbox" in r.headers["Content-Security-Policy"], "the runner sees the image (sandboxed)")
check(fresh.get(f"/uploads/{img}").status_code == 404 and not j(fresh.get("/api/me/handouts"))["handouts"], "runners it wasn't given to don't")
gm.delete(f"/api/handouts/{hid}", headers=H)
check(gm.get(f"/uploads/{img}").status_code == 404, "deleting the handout deletes its image")
r = gm.post(f"/api/games/{cid}/sessions", json={"title": "Game night"}, headers=H)
check(r.status_code == 201, "the GM starts a session")
sid = j(r)["id"]
check(gm.post(f"/api/games/{cid}/sessions", json={}, headers=H).status_code == 400, "only one session at a time")
pl.post("/api/me/roll", json={"mode": "free", "dice": 6, "label": "Sneak past"}, headers=H)
gm.post(f"/api/games/{cid}/grant", json={"players": [pid], "karma": 3, "reason": "Session"}, headers=H)
live = next(x for x in j(gm.get(f"/api/games/{cid}"))["sessions"] if x["id"] == sid)
check(live["active"] and live["recap"]["stats"]["rolls"] >= 1 and live["recap"]["stats"]["karma"] == 3, "the live recap counts rolls and awards")
gm.put(f"/api/sessions/{sid}", json={"notes": "The team got in quietly."}, headers=H)
check(gm.post(f"/api/sessions/{sid}/end", headers=H).status_code == 200, "the GM ends the session")
check(not j(pl.get("/api/me/sessions"))["sessions"], "unshared recaps stay with the GM")
gm.put(f"/api/sessions/{sid}", json={"shared": True}, headers=H)
ps = j(pl.get("/api/me/sessions"))["sessions"]
check(len(ps) == 1 and ps[0]["notes"] == "The team got in quietly." and any("Sneak past" in e["text"] for e in ps[0]["recap"]["events"]), "shared: players read the recap")
md = gm.get(f"/api/sessions/{sid}/export")
check(md.status_code == 200 and b"# Game night" in md.data and b"Sneak past" in md.data, "the recap exports as Markdown")
r = gm.post(f"/api/maps/{mid}/sight", json={"a": {"kind": "player", "id": pid}, "b": {"kind": "marker", "id": "e1"}}, headers=H)
check(r.status_code == 200 and "los" in (j(r)["sight"] or {"los": 0}), "line of sight between a runner and a marker")

print("Maps and backups")
dm = j(gm.post("/api/maps", json={"name": "Doomed", "campaignId": cid, "width": 8, "height": 8,
                               "data": {"cells": {"1,1": {}}, "markers": [{"id": "z1", "c": 1, "r": 1, "type": "danger", "label": "Z"}]}}, headers=H))["id"]
gm.post(f"/api/games/{cid}/combat", json={"op": "start", "mapId": dm, "markers": ["z1"], "players": [pid]}, headers=H)
check(gm.delete(f"/api/maps/{dm}", headers=H).status_code == 200 and gm.get(f"/api/maps/{dm}").status_code == 404, "the GM deletes a map")
t = j(gm.get(f"/api/games/{cid}/combat"))["tracker"]
check(not any(e["kind"] == "marker" for e in t["entries"]) and any(e["kind"] == "player" for e in t["entries"]), "its enemies leave the combat tracker")
gm.post(f"/api/games/{cid}/combat", json={"op": "end"}, headers=H)
r = gm.post("/api/backups", headers=H)
check(r.status_code == 201, "the GM makes a backup")
bname = j(r)["name"]
check(pl.get("/api/backups").status_code == 401, "players can't see backups")
zipdata = gm.get(f"/api/backups/{bname}").data
check(zipdata[:2] == b"PK", "the backup downloads as a zip")
j(gm.post(f"/api/games/{cid}/runs", json={"name": "After the backup", "reward": 1}, headers=H))
r = gm.post("/api/backup/restore", data={"file": (io.BytesIO(zipdata), "b.zip")}, headers=H, content_type="multipart/form-data")
check(r.status_code == 200 and j(r)["safety"].startswith("shadowgrid-before-restore"), "a backup file restores (after a safety backup)")
check(gm.get(f"/api/games/{cid}").status_code == 401, "restoring signs everyone out")
login(gm, "gamemaster", "gm-password-123")
check(not any(x["name"] == "After the backup" for x in j(gm.get(f"/api/games/{cid}"))["runs"]), "the game is back to the backup's moment")
r = gm.post("/api/backup/restore", data={"file": (io.BytesIO(b"not a zip"), "x.zip")}, headers=H, content_type="multipart/form-data")
check(r.status_code == 400, "a bad file is refused")
check(gm.get("/api/backups/..%2Fshadowgrid.db").status_code == 404, "no path tricks on backup names")

print("Store stock, core substances, qualities in play, marker details, speed")
login(gm, "gamemaster", "gm-password-123")
login(pl, "ana", "brand-new-pass")
me0 = j(pl.get("/api/me/sheet"))
gun = next(e for e in j(pl.get("/api/catalog"))["store"]["items"] if e["name"] == "Ares Predator VI")
r = gm.put(f"/api/games/{cid}/stock", json={"ids": [gun["id"], "nope"], "inStock": False}, headers=H)
check(r.status_code == 200 and j(r)["outOfStock"] == [gun["id"]], "the GM marks an item out of stock (unknown ids ignored)")
sh = j(pl.get("/api/me/sheet"))
check(not sh["store"][gun["id"]][0] and sh["store"][gun["id"]][1].startswith("Out of stock"), "players see it out of stock")
r = pl.post("/api/me/sheet/action", json={"action": "buy", "ref": gun["id"]}, headers=H)
check(r.status_code == 400 and "out of stock" in j(r)["error"], "and can't buy it")
packs_with = [e["id"] for e in j(pl.get("/api/catalog"))["packs"] if not sh["store"][e["id"]][0] and "Ares Predator VI" in sh["store"][e["id"]][1]]
check(packs_with, "PACKs with it inside are out of stock too")
gm.put(f"/api/games/{cid}/stock", json={"ids": [gun["id"]], "inStock": True}, headers=H)
check(j(pl.get("/api/me/sheet"))["store"][gun["id"]][1] == me0["store"][gun["id"]][1], "back in stock")
check(j(gm.get(f"/api/games/{cid}"))["game"]["settings"]["outOfStock"] == [], "the game settings list what is out")
subs = j(gm.get(f"/api/players/{pid}/sheet"))["substances"]
names = {x["name"] for x in subs}
check({"Narcoject", "Neuro-Stun X", "Seven-7", "Jazz", "Kamikaze", "Novacoke", "Psyche", "Zen", "Long Haul"} <= names, "the core book's toxins and drugs are built in")
dose = next(e for e in j(pl.get("/api/catalog"))["store"]["items"] if e.get("substance") == "nitro")
gm.post(f"/api/players/{pid}/sheet/action", json={"action": "buy", "ref": dose["id"], "qty": 2}, headers=H)
pool0 = next(p for p in j(pl.get("/api/me/sheet"))["pools"] if p["key"] == "skill:Perception")
r = pl.post("/api/me/dose", json={"id": "nitro", "resist": False}, headers=H)
sh = j(r)
pool1 = next(p for p in sh["pools"] if p["key"] == "skill:Perception")
check(r.status_code == 200 and pool1["value"] == pool0["value"] + 2, "a dose bought in the store works (Nitro: +2 Perception)")
i = next(i for i, t in enumerate(sh["char"]["toxins"]) if t["name"] == "Nitro")
sh = j(pl.post("/api/me/sheet/action", json={"action": "end_substance", "index": i}, headers=H))
pool2 = next(p for p in sh["pools"] if p["key"] == "skill:Perception")
check(any(t["name"] == "Nitro crash" for t in sh["char"]["toxins"]) and pool2["value"] == max(0, pool0["value"] - 2), "its crash: −2 dice for a while")
r = gm.post(f"/api/players/{pid}/expose", json={"id": "seven-7", "resist": False}, headers=H)
check(j(r)["char"]["statuses"].get("Blinded") == 1 and j(r)["char"]["statuses"].get("Nauseated"), "Seven-7: Blinded I and Nauseated")
approved = j(gm.get(f"/api/players/{pid}/sheet"))["approved"]
if not approved:
    gm.post(f"/api/players/{pid}/review", json={"decision": "approve"}, headers=H)
k0 = j(pl.get("/api/me/sheet"))["char"]["karma"]
r = pl.post("/api/me/sheet/action", json={"action": "add_quality", "quality": "Distinctive Style"}, headers=H)
check(r.status_code == 200 and j(r)["char"]["karma"] == k0 and any(q["name"] == "Distinctive Style" for q in j(r)["char"]["qualities"]), "after approval a runner takes a negative quality (no Karma)")
check(any("Distinctive Style" in (x.get("data") or {}).get("text", "") for x in j(gm.get(f"/api/games/{cid}"))["rolls"]), "and the GM sees it in the table log")
r = gm.post(f"/api/maps/{mid}/marker", json={"id": "e1", "info": "A tall troll in a long coat."}, headers=H)
check(r.status_code == 200 and j(r)["marker"]["info"] == "A tall troll in a long coat.", "the GM writes what players see on a marker")
st = j(pl.get("/api/me/state"))
mk = [m for m in (st["view"]["map"] or {}).get("markers", []) if m["id"] == "e1"]
check(not mk or mk[0].get("info") == "A tall troll in a long coat.", "players get the description with the marker")
if st["view"]["map"]:
    sig = st["view"]["map"]["cellsSig"]
    again = j(pl.get(f"/api/me/state?cells={sig}"))["view"]["map"]
    check(again["cells"] is None and again["cellsSig"] == sig, "unchanged map cells aren't sent again")
r = pl.get("/api/catalog", headers={"Accept-Encoding": "gzip"})
check(r.headers.get("Content-Encoding") == "gzip" and r.headers.get("ETag"), "the catalog comes compressed, with an ETag")
check(pl.get("/api/catalog", headers={"If-None-Match": r.headers["ETag"]}).status_code == 304, "and is not sent again when unchanged")
r = pl.get("/api/me/sheet", headers={"Accept-Encoding": "gzip"})
check(r.headers.get("Content-Encoding") == "gzip", "API answers are compressed")
shell = pl.get("/play")
check(b"data-shell" in shell.data and b'id="app"' in shell.data and "Sec-Fetch-Dest" in shell.headers.get("Vary", ""),
      "a top-level visit gets the persistent frame that keeps the music playing")
check(b"play.js" in pl.get("/play", headers={"Sec-Fetch-Dest": "iframe"}).data, "the frame loads the screen itself")
check(pl.get("/play").headers["X-Frame-Options"] == "SAMEORIGIN" and "frame-ancestors 'self'" in pl.get("/play").headers["Content-Security-Policy"],
      "only the app itself may frame its pages")
page = pl.get("/play?embed=1").data.decode()
check("/static/play.js?v=" in page and 'name="sg-catalog"' in page, "pages link versioned scripts")
r = pl.get(page.split('src="')[1].split('"')[0] if 'src="/static/' in page else "/static/api.js?v=x")
check("immutable" in r.headers.get("Cache-Control", ""), "versioned scripts are cached for good")

print("Combat options: Take Aim, Trip, Wrest, Tactical Roll, grappling, dispelling")
security._buckets.clear()
gun = f"weapon:{pred['uid']}"
gm.post(f"/api/games/{cid}/combat", json={"op": "end"}, headers=H)
for m_ in ("g1", "g2"):
    gm.post(f"/api/maps/{arena}/marker", json={"id": m_, "template": "t:6", "relabel": False}, headers=H)
    gm.post(f"/api/maps/{arena}/marker", json={"id": m_, "statuses": {}}, headers=H)
for st_ in list(j(pl.get("/api/me/state"))["me"]["statuses"]):
    gm.post(f"/api/maps/{arena}/status", json={"target": P, "status": st_, "on": False}, headers=H)
gm.post(f"/api/players/{pid}/sheet/action", json={"action": "set_ammo", "uid": pred["uid"], "rounds": 15}, headers=H)
gm.post(f"/api/players/{pid}/sheet/action", json={"action": "set_damage", "physical": 0, "stun": 0}, headers=H)
gm.post(f"/api/players/{pid}/place", json={"mapId": arena, "c": 3, "r": 1}, headers=H)
gm.post(f"/api/games/{cid}/combat", json={"op": "start", "players": [pid, mpid], "mapId": arena, "markers": ["g1", "g2"], "roll": True}, headers=H)
cop = lambda **kw: gm.post(f"/api/games/{cid}/combat", json=kw, headers=H)  # noqa: E731
r = cop(op="aim", id=entry(pid)["id"])
check(r.status_code == 200 and entry(pid)["aim"] == 1, "Take Aim: +1 die, a Minor Action")
check(cop(op="aim", id=entry(pid)["id"]).status_code == 400, "only once per round")
cop(op="round")
cop(op="aim", id=entry(pid)["id"])
check(entry(pid)["aim"] == 2, "the aim builds up over rounds")
r = atk(attacker=P, weapon=gun, targets=[G2], ignoreSight=True)
check(any(p_ == ["Take Aim", 2] for p_ in j(r)["result"]["attack"]["parts"]) and entry(pid)["aim"] == 0, "the next ranged attack uses it up")
cop(op="aim", id=entry(pid)["id"], force=True)
cop(op="round")
cop(op="turn", id=entry(pid)["id"])
cop(op="next")
check(entry(pid)["aim"] == 0, "a turn with neither Take Aim nor an attack loses it")
r = atk(attacker=P, weapon=gun, targets=[G1], trip=True, ignoreSight=True, ignoreActions=True)
check(r.status_code == 400 and "melee" in j(r)["error"], "Trip is for melee attacks")
tripped = None
for _ in range(8):
    cop(op="round")
    r = atk(attacker=P, weapon="weapon:unarmed", targets=[G1], range="Close", trip=True, attackMod=25, soakMod=40, ignoreSight=True, ignoreActions=True)
    if j(r)["result"].get("trip"):
        tripped = j(r)["result"]
        break
check(tripped and tripped["trip"]["threshold"] == tripped["dv"] and tripped["trip"]["prone"] == (tripped["trip"]["hits"] < tripped["dv"]),
      "Trip: on a hit the target rolls Athletics + Agility against the DV or goes Prone")
unarmed_dv = next(o for o in j(gm.post(f"/api/maps/{arena}/attack-options", json={"who": P}, headers=H))["options"] if o["key"] == "weapon:unarmed")["dv"]
check(tripped and tripped["dv"] == max(0, int(unarmed_dv[:-1]) - 2) + max(0, tripped["net"]), "and the base DV is 2 lower")
gm.post(f"/api/maps/{arena}/marker", json={"id": "g1", "statuses": {}}, headers=H)
cop(op="round")
gm.post(f"/api/players/{pid}/sheet/action", json={"action": "gamemaster_set", "current_edge": 5}, headers=H)
check(atk(attacker=G1, weapon="-1", targets=[P], range="Close", wrest={f"player:{pid}": True}, ignoreSight=True).status_code == 400,
      "Wrest needs a Block")
r = atk(attacker=G1, weapon="-1", targets=[P], range="Close", defenses={f"player:{pid}": "block"}, wrest={f"player:{pid}": True},
        defenseMod=30, ignoreSight=True, ignoreActions=True)
w_ = j(r).get("result", {}).get("wrest")
check(r.status_code == 200 and w_ and w_["threshold"] >= 1 and any("Wrest" in n_ or "wrests" in n_ for n_ in j(r)["result"]["notes"]),
      "Wrest after a successful Block: Close Combat + Agility vs Strength, 2 Edge")
r = atk(attacker=G2, weapon="0", targets=[P], defenses={f"player:{pid}": "hit_the_dirt"}, tactical={f"player:{pid}": True}, ignoreSight=True)
check(r.status_code == 400 and "Edge" in j(r)["error"], "one Edge expenditure per round (Wrest already spent it)")
cop(op="round")
r = atk(attacker=G2, weapon="0", targets=[P], defenses={f"player:{pid}": "hit_the_dirt"}, tactical={f"player:{pid}": True}, ignoreSight=True, ignoreActions=True)
check(r.status_code == 200 and entry(pid)["troll"] == j(gm.get(f"/api/games/{cid}/combat"))["tracker"]["round"], "Tactical Roll with Hit the Dirt (1 Edge)")
r = atk(attacker=P, weapon="weapon:unarmed", targets=[G1], range="Close", ignoreSight=True, ignoreActions=True)
check(not any(p_[0].startswith("Prone") for p_ in j(r)["result"]["attack"]["parts"]), "Tactical Roll: no Prone penalty on a melee attack that round")
r = atk(attacker=G1, weapon="-1", targets=[P], range="Close", ignoreSight=True, ignoreActions=True)
check(not any(p_[0] == "Prone" for p_ in j(r)["result"]["defense"]["parts"]), "nor the −2 against Close attacks while Prone")
gm.post(f"/api/maps/{arena}/status", json={"target": P, "status": "Prone", "on": False}, headers=H)
gm.post(f"/api/maps/{arena}/marker", json={"id": "g1", "statuses": {}}, headers=H)
check(atk(attacker=P, weapon=gun, targets=[G1], grapple=True, ignoreSight=True, ignoreActions=True).status_code == 400, "grappling is unarmed")
held = None
for _ in range(10):
    cop(op="round")
    r = atk(attacker=P, weapon="weapon:unarmed", targets=[G1], range="Close", grapple=True, attackMod=30, ignoreSight=True, ignoreActions=True)
    if (j(r)["result"].get("grapple") or {}).get("held"):
        held = j(r)["result"]
        break
g1m = lambda: next(m for m in j(gm.get(f"/api/maps/{arena}"))["data"]["markers"] if m["id"] == "g1")  # noqa: E731
check(held and held["damage"] == 0 and g1m()["statuses"].get("Restrained") and j(pl.get("/api/me/state"))["me"]["statuses"].get("Grappling")
      and entry(pid)["grapple"]["role"] == "grappler" and entry("g1")["grapple"]["role"] == "held",
      "grapple: Strength + net hits vs Strength instead of damage; Restrained and Grappling")
e0 = R_edge = next(m for m in j(gm.get(f"/api/maps/{arena}"))["data"]["markers"] if m["id"] == "g2").get("edge_cur")
r = atk(attacker=G2, weapon="0", targets=[G1], ignoreSight=True, ignoreActions=True, attackMod=10)
rr = j(r)["results"]
check(any(p_ == ["Restrained", -4] for p_ in rr[0]["defense"]["parts"]), "a restrained target defends at −4")
check(any("against a restrained target" in n_ for n_ in rr[0]["notes"]), "and the attacker gains Edge on them")
stray = None
for _ in range(10):
    r = atk(attacker=G2, weapon="0", targets=[G1], ignoreSight=True, ignoreActions=True, attackMod=-30)
    rr = j(r)["results"]
    if not rr[0]["hit"]:
        stray = rr[1] if len(rr) > 1 else None
        break
check(stray and stray.get("stray") and stray["target"] == j(pl.get("/api/me/state"))["me"]["name"] and stray["attack"]["dice"] == rr[0]["attack"]["dice"],
      "a missed attack on a restrained target goes at the grappler with the same roll")
r = cop(op="grapple", id=entry(pid)["id"], action="damage", force=True)
check(r.status_code == 200 and "Squeeze" in j(gm.get(f"/api/games/{cid}"))["rolls"][0]["data"]["text"], "grapple follow-ups are Major Actions")
check(cop(op="grapple", id=entry(pid)["id"], action="break").status_code == 400, "only the one held can break free")
cop(op="end")
check(not g1m().get("statuses", {}).get("Restrained") and not j(pl.get("/api/me/state"))["me"]["statuses"].get("Grappling"), "the grapple ends with the fight")

# dispelling a sustained spell
mage = j(gm.get(f"/api/players/{mpid}/sheet"))
sp_ = next((s_ for s_ in mage["char"]["spells"] if s_.get("duration") == "S"), None)
gm.post(f"/api/players/{mpid}/sheet/action", json={"action": "sustain", "name": sp_["name"], "hits": 2}, headers=H)
lst = j(gm.get(f"/api/games/{cid}/sustained"))["spells"]
check(lst and lst[0]["name"] == sp_["name"] and lst[0]["dv"] >= 1 and lst[0]["hits"] == 2, "the GM sees every sustained spell, with its hits and Drain Value")
cop(op="start", players=[pid, mpid], mapId=arena, markers=[], roll=True)
gone = False
for _ in range(12):
    cop(op="dispel", id=entry(mpid)["id"], target={"pid": mpid, "index": 0}, force=True)
    now_ = j(gm.get(f"/api/players/{mpid}/sheet"))["char"]["sustained"]
    if not now_ or now_[0]["hits"] < 2:
        gone = True
        break
check(gone, "dispelling: Sorcery + Magic vs Drain Value × 2, net hits cancel the spell's hits")
r = cop(op="dispel", id=entry(mpid)["id"], target={"name": "Enemy Mana Barrier", "dv": 4, "hits": 3}, force=True)
check(r.status_code == 200 and "Enemy Mana Barrier" in j(gm.get(f"/api/games/{cid}"))["rolls"][0]["data"]["text"], "dispel a spell the GM describes")
check(cop(op="dispel", id=entry(pid)["id"], target={"name": "x", "dv": 3, "hits": 1}).status_code == 400, "only magicians dispel")
cop(op="end")

print("Rigging: speed, weapon mounts, drones firing")
security._buckets.clear()
for name_ in ("Standard Weapon Mount", "Heavy Weapon Mount", "HK-227", "Panther XXL"):
    gm.post(f"/api/players/{rgid}/sheet/action", json={"action": "give", "ref": ref(name_)}, headers=H)
rsh = j(rg.get("/api/me/sheet"))
dob, smt, hmt = item(rsh, "GM-Nissan Doberman"), item(rsh, "Standard Weapon Mount"), item(rsh, "Heavy Weapon Mount")
hk, pan = item(rsh, "HK-227"), item(rsh, "Panther XXL")
r = ract(action="install_mount", uid=hmt["uid"], vehicle=dob["uid"])
check(r.status_code == 400 and "room for 1" in j(r)["error"], "Body 4: one weapon mount, a heavy one needs two")
check(ract(action="install_mount", uid=smt["uid"], vehicle=dob["uid"]).status_code == 200, "a standard mount goes on the drone")
r = ract(action="mount_weapon", mount=smt["uid"], weapon=pan["uid"])
check(r.status_code == 400 and "heavy" in j(r)["error"], "a standard mount takes an assault rifle or smaller")
r = ract(action="mount_weapon", mount=smt["uid"], weapon=hk["uid"])
keys = {p_["key"] for p_ in j(r)["pools"]}
check(r.status_code == 200 and f"vgun:{hk['uid']}:gunner" in keys and not any(k.endswith(hk["uid"]) and k.startswith("weapon:") for k in keys),
      "a mounted gun: fired by a gunner (Engineering + Logic), no longer carried")
r = ract(action="vehicle_speed", uid=dob["uid"], change=20)
check(r.status_code == 400 and "Acceleration" in j(r)["error"], "speed changes by at most the Acceleration per round")
r = ract(action="vehicle_speed", uid=dob["uid"], change=10)
check(item(j(r), "GM-Nissan Doberman")["speed"] == 10 and item(j(r), "GM-Nissan Doberman")["moved"] == 5, "distance = speed at the start + half the change")
r = ract(action="vehicle_speed", uid=dob["uid"], set=31)
mp = next(p_ for p_ in j(r)["pools"] if p_["key"] == f"vehicle:{dob['uid']}:manual")
check(any(p_[0].startswith("Speed 31") and p_[1] == -2 for p_ in mp["parts"]), "−1 die per Speed Interval passed (31 m with interval 15: −2)")
gm.post(f"/api/players/{rgid}/sheet/action", json={"action": "set_ammo", "uid": hk["uid"], "rounds": 30}, headers=H)
hk_rounds = item(j(rg.get("/api/me/sheet")), "HK-227")["loaded"]["rounds"]
gm.post(f"/api/maps/{arena}/marker", json={"id": "g3", "template": f"pv:{rgid}:{dob['uid']}"}, headers=H)
opts = j(gm.post(f"/api/maps/{arena}/attack-options", json={"who": G3}, headers=H))["options"]
check(any(o["key"] == f"mount:{hk['uid']}" for o in opts), "the drone on the map can fire its mounted gun")
r = gm.post(f"/api/maps/{arena}/attack", json={"attacker": G3, "weapon": f"mount:{hk['uid']}", "mode": "SA", "range": "Near", "targets": [G1],
                                               "ignoreSight": True, "ignoreActions": True}, headers=H)
pp = j(r)["result"]["attack"]["parts"]
check(r.status_code == 200 and pp[0] == ["Sensor", 3] and any(p_[0] == "No Targeting autosoft" for p_ in pp) and any(p_[0].startswith("Speed 31") for p_ in pp),
      "the drone fires with Sensor (− 1 without a Targeting autosoft) and the speed penalty")
check(item(j(rg.get("/api/me/sheet")), "HK-227")["loaded"]["rounds"] == hk_rounds - 2, "and uses the owner's ammo")
r = gm.post(f"/api/maps/{arena}/marker", json={"id": "g2", "template": "v:drones-gm-nissan-doberman"}, headers=H)
r = gm.post(f"/api/maps/{arena}/marker", json={"id": "g2", "mount": {"ref": "ranged-hk-227", "autosoft": 3}}, headers=H)
mw = j(r)["marker"]["npc"]["weapons"][-1]
check(r.status_code == 200 and mw["name"] == "HK-227" and mw["pool"] == 6 and mw["mount"] == "standard", "an NPC drone gets a mounted HK-227: Sensor 3 + Targeting 3")
r = gm.post(f"/api/maps/{arena}/marker", json={"id": "g2", "mount": {"ref": "ranged-hk-227", "autosoft": 3}}, headers=H)
check(r.status_code == 400 and "Room for 1" in j(r)["error"], "and no more than Body / 3 mounts")
gm.post(f"/api/maps/{arena}/marker", json={"id": "g2", "vehicleSpeed": {"set": 30}}, headers=H)
r = gm.post(f"/api/maps/{arena}/attack", json={"attacker": G2, "weapon": "0", "targets": [G1], "range": "Close", "ignoreSight": True, "ignoreActions": True}, headers=H)
check(j(r)["result"]["weapon"] == "Ram" and any(p_ == ["Speed Intervals", -2] for p_ in j(r)["result"]["attack"]["parts"])
      and any("+2 DV" in n_ for n_ in j(r)["result"]["notes"]), "ramming at speed: −2 dice and +2 DV at two Speed Intervals")

print("Matrix programs")
security._buckets.clear()
for kind_ in ("basic", "basic", "hacking", "hacking", "hacking"):
    dact(action="buy", ref=f"cyberdecks-software-cyberprogram-{kind_}")
progs = [it_ for it_ in j(dk.get("/api/me/sheet"))["char"]["inventory"] if (it_.get("ref") or "").startswith("cyberdecks-software-cyberprogram")]
basics = [p_ for p_ in progs if "basic" in p_["ref"]]
hacks = [p_ for p_ in progs if "hacking" in p_["ref"]]
dact(action="set_program", uid=basics[-2]["uid"], choice="Browse", running=True)
r = dact(action="set_program", uid=hacks[-2]["uid"], choice="Decryption", running=True)
pools_ = {p_["key"]: p_ for p_ in j(r)["pools"]}
check(any(p_[0] == "Decryption" and p_[1] == 2 for p_ in pools_["matrix:crack_file"]["parts"]), "Decryption: +2 dice on Crack File")
r = dk.post("/api/me/roll", json={"key": "matrix:matrix_search"}, headers=H)
rr = j(r)["rolls"][0]
check(rr["data"].get("free_edge") == 1, "Browse: 1 Edge for that Matrix Search only")
edge0 = j(dk.get("/api/me/state"))["me"]["edge"]["cur"]
r = dk.post(f"/api/me/rolls/{rr['id']}/boost", json={"boost": "reroll", "dice": [0]}, headers=H)
check(r.status_code == 200 and j(dk.get("/api/me/state"))["me"]["edge"]["cur"] == edge0, "the program's Edge pays for a boost on that roll")
dact(action="set_program", uid=hacks[-2]["uid"], running=False)
r = dact(action="set_program", uid=hacks[-3]["uid"], choice="Overclock", running=True)
check(next(p_ for p_ in j(r)["pools"] if p_["key"] == "matrix:brute_force").get("wild"), "Overclock: one of its dice is the Wild Die")
r = dk.post("/api/me/roll", json={"key": "matrix:brute_force"}, headers=H)
check(any(d_.get("w") for d_ in j(r)["rolls"][0]["data"]["dice"]), "and the roll has it")
dact(action="set_program", uid=hacks[-3]["uid"], running=False)
dact(action="set_matrix", noise=5)
p5 = next(p_ for p_ in j(dk.get("/api/me/sheet"))["pools"] if p_["key"] == "matrix:brute_force")
check(any(p_ == ["Noise", -5] for p_ in p5["parts"]), "noise: −1 per point on Matrix tests")
r = dact(action="set_program", uid=basics[-1]["uid"], choice="Signal Scrubber", running=True)
p3 = next(p_ for p_ in j(r)["pools"] if p_["key"] == "matrix:brute_force")
check(any(p_ == ["Noise", -3] for p_ in p3["parts"]), "Signal Scrubber: noise −2")
dact(action="set_program", uid=basics[-1]["uid"], running=False)
dact(action="set_matrix", noise=0)
dm = j(dk.get("/api/me/sheet"))["derived"]["matrix"]
r = dact(action="set_matrix", swap=["attack", "firewall"])
dm2 = j(r)["derived"]["matrix"]
check(dm2["attack"] == dm["firewall"] and dm2["firewall"] == dm["attack"], "Reconfigure: swap two Matrix attributes")
check(dact(action="set_matrix", config="save").status_code == 400, "saving a setup needs Configurator")
dact(action="set_matrix", config="reset")
gm.post(f"/api/players/{dkid}/sheet/action", json={"action": "set_os", "os": 7}, headers=H)
check(j(dk.get("/api/me/sheet"))["derived"]["matrix"]["os"] != 7, "the Overwatch Score stays secret")
dact(action="set_program", uid=basics[-2]["uid"], choice="Baby Monitor", running=True)
check(j(dk.get("/api/me/sheet"))["derived"]["matrix"]["os"] == 7, "Baby Monitor shows it")

print("Music")
import subprocess, time as _t  # noqa: E402,E401
import music as MU  # noqa: E402
ff = MU.find_ffmpeg()
check(ff, "ffmpeg with Opus found")
tone = os.path.join(tmp, "theme.mp3")
subprocess.run([ff, "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i", "sine=frequency=440:duration=12", "-f", "lavfi", "-i", "anoisesrc=d=12:a=0.05",
                "-filter_complex", "amix=inputs=2", "-ac", "2", "-b:a", "192k", tone], check=True)
with open(tone, "rb") as f:
    mp3 = f.read()
r = gm.post(f"/api/games/{cid}/music", data={"file": (io.BytesIO(mp3), "Club Penumbra.mp3")}, headers=H, content_type="multipart/form-data")
check(r.status_code == 202 and j(r)["tracks"][0]["status"] == "processing", "GM uploads a track; it is compressed in the background")
tid = j(r)["id"]
check(pl.post(f"/api/games/{cid}/music", data={"file": (io.BytesIO(mp3), "x.mp3")}, headers=H, content_type="multipart/form-data").status_code == 401, "players can't upload music")
r = gm.post(f"/api/games/{cid}/music", data={"file": (io.BytesIO(b"#EXTM3U\nfile:///etc/passwd\n"), "evil.m3u")}, headers=H, content_type="multipart/form-data")
check(r.status_code == 400, "playlists and other files are refused")
r = gm.post(f"/api/games/{cid}/music", data={"file": (io.BytesIO(b"not audio at all" * 100), "fake.mp3")}, headers=H, content_type="multipart/form-data")
bad = j(r)["id"]
for _ in range(200):
    ts = {t["id"]: t for t in j(gm.get(f"/api/games/{cid}/music"))["tracks"]}
    if ts[tid]["status"] != "processing" and ts[bad]["status"] != "processing":
        break
    _t.sleep(0.2)
t = ts[tid]
check(t["status"] == "ready" and 11 < (t["duration"] or 0) < 13, "the track is ready with its length " + (str(t) if t["status"] != "ready" else ""))
check(t["size"] < t["srcSize"] / 2.5 and t["aacSize"], f"compressed to Opus ({t['srcSize']} -> {t['size']} bytes) with an AAC fallback")
check(ts[bad]["status"] == "failed" and ts[bad]["error"], "a file that isn't audio fails cleanly")
check(not any(f.startswith("upload-") for f in os.listdir(MU.MUSIC_DIR)), "originals are deleted after compressing")
check(j(pl.get("/api/music/now"))["playing"] is None, "nothing playing yet")
check(pl.get(f"/music/{tid}.webm").status_code == 200, "players of the game can fetch the track")
r = gm.post(f"/api/games/{cid}/music/play", json={"track": tid, "loop": False}, headers=H)
now_ = j(pl.get("/api/music/now"))
check(now_["playing"]["trackId"] == tid and not now_["playing"]["loop"] and abs(now_["playing"]["startedAt"] - now_["serverNow"]) < 2,
      "playing a track shares its start time with the players")
r = pl.get(now_["playing"]["src"]["opus"], headers={"Range": "bytes=100-199"})
check(r.status_code == 206 and len(r.data) == 100 and r.mimetype == "audio/webm", "audio is served in ranges (streaming and seeking)")
check(pl.get(now_["playing"]["src"]["aac"]).mimetype == "audio/mp4", "AAC fallback for browsers without Opus")
check(pl.post(f"/api/games/{cid}/music/stop", json={}, headers=H).status_code == 401, "players can't stop the music")
r = gm.post(f"/api/games/{cid}/music", data={"file": (io.BytesIO(mp3), "Combat.mp3")}, headers=H, content_type="multipart/form-data")
t2 = j(r)["id"]
for _ in range(200):
    if {t["id"]: t for t in j(gm.get(f"/api/games/{cid}/music"))["tracks"]}[t2]["status"] == "ready":
        break
    _t.sleep(0.2)
gm.post(f"/api/games/{cid}/music/play", json={"track": t2}, headers=H)
check(j(pl.get("/api/music/now"))["playing"]["trackId"] == t2 and j(pl.get("/api/music/now"))["playing"]["loop"], "starting another track replaces the first (one at a time)")
gm.post(f"/api/games/{cid}/music/play", json={"loop": False}, headers=H)
check(not j(pl.get("/api/music/now"))["playing"]["loop"] and j(pl.get("/api/music/now"))["playing"]["trackId"] == t2, "looping can be switched without restarting")
g2 = j(gm.post("/api/campaigns", json={"name": "Other table"}, headers=H))["id"]
inv2 = j(gm.post(f"/api/games/{g2}/invites", json={}, headers=H))
other, r = register(inv2["token"], "outsider")
check(other.get(f"/music/{t2}.webm").status_code == 404 and j(other.get("/api/music/now"))["playing"] is None, "players of another game can't hear it")
check(j(gm.get(f"/api/music/now?map={mid}"))["playing"]["trackId"] == t2, "the editor finds the game's music from the map")
bk = j(gm.post("/api/backups", json={}, headers=H))["name"]
import zipfile  # noqa: E402
names = zipfile.ZipFile(os.path.join(tmp, "backups", bk)).namelist()
check(f"music/{t2}.webm" in names and f"music/{tid}.m4a" in names, "manual backups include the music")
import backup as BK  # noqa: E402
auto = BK.make_backup("auto")
check(not any(n.startswith("music/") for n in zipfile.ZipFile(os.path.join(tmp, "backups", auto)).namelist()), "daily backups leave the music out")
r = gm.post(f"/api/backups/{auto}/restore", json={}, headers=H)
check(r.status_code == 200 and os.path.exists(os.path.join(MU.MUSIC_DIR, f"{t2}.webm")), "restoring a backup without music keeps the music files")
gm = A.test_client(); gate_solve(gm); login(gm, "gamemaster", "gm-password-123")
check(j(gm.get(f"/api/games/{cid}/music"))["tracks"][0]["status"] == "ready", "and the tracks still play after the restore")
gm.post(f"/api/games/{cid}/music/play", json={"track": t2}, headers=H)
r = gm.delete(f"/api/music/{t2}", headers=H)
check(r.status_code == 200 and j(r)["playing"] is None and not os.path.exists(os.path.join(MU.MUSIC_DIR, f"{t2}.webm")), "deleting the playing track stops it and removes its files")
gm.delete(f"/api/campaigns/{g2}", headers=H)

# ---------------------------------------------------------------- sight, derive memo, minified assets, server mode
print("\n== sight and speed")
import geometry as GEO  # noqa: E402
sc = {f"{c},{r}": {"fill": "#123"} for c in range(0, 20) for r in range(0, 8) if c != 10 or r == 4}
sc["9,4"]["doors"] = {"1": {"color": "#fff", "open": False}}
sc["15,1"]["secret"] = True
gsq = {"gridType": "square", "width": 20, "height": 8}
vis = GEO.visible_cells(gsq, sc, (4, 4), 8)
check("8,4" in vis and "11,4" not in vis, "a closed door blocks sight")
sc["9,4"]["doors"]["1"]["open"] = True
vis = GEO.visible_cells(gsq, sc, (4, 4), 8)
check("11,4" in vis and "12,4" in vis and "12,0" not in vis, "an open door lets sight through, the wall beside it doesn't")
check(all(GEO.cell_distance("square", (4, 4), tuple(map(int, k.split(",")))) <= 8 for k in vis), "sight stops at its radius")
vis = GEO.visible_cells({"gridType": "square", "width": 20, "height": 8}, sc, (14, 1), 6)
check("15,1" not in vis, "secret cells are never revealed by sight")
smap = j(gm.post("/api/maps", json={"name": "Sight test", "campaignId": cid, "width": 20, "height": 8, "data": {"cells": sc, "markers": [], "rooms": []}}, headers=H))["id"]
gm.post(f"/api/players/{pid}/place", json={"mapId": smap, "c": 2, "r": 4}, headers=H)
def explored_of(mid_):
    ps = j(gm.get(f"/api/maps/{mid_}/context"))["players"]
    return set(next(x for x in ps if x["id"] == pid)["state"]["maps"][mid_]["explored"])
check("8,4" not in explored_of(smap), "without the setting, only the reveal radius is explored")
m = j(gm.get(f"/api/maps/{smap}"))
r = gm.put(f"/api/maps/{smap}", json={"settings": dict(m["settings"], sightReveal=True, sightRadius=99)}, headers=H)
check(j(gm.get(f"/api/maps/{smap}"))["settings"]["sightRadius"] == 20, "the sight radius is clamped")
gm.post(f"/api/players/{pid}/place", json={"mapId": smap, "c": 3, "r": 4}, headers=H)
ex = explored_of(smap)
check("8,4" in ex and "3,0" in ex and "13,4" in ex and "12,0" not in ex, "with 'reveal what runners can see', what is in sight is explored (through the open door), not behind the wall")
check("15,1" not in ex, "and secret cells stay hidden")
gm.delete(f"/api/maps/{smap}", headers=H)
from sr import rules as RR  # noqa: E402
pc = RR.new_character()
d0 = RR.derive(pc)
with RR.derive_memo():
    d1 = RR.derive(pc); d2 = RR.derive(pc)
    c2 = json.loads(json.dumps(pc)); RR.remember_source(c2, "same-json"); RR.remember_source(pc, "same-json")
check(d1 is d2 and json.dumps(d1, sort_keys=True, default=str) == json.dumps(d0, sort_keys=True, default=str), "the derive memo returns the same values, computed once")
check(RR.derive(pc) is not RR.derive(pc), "outside the memo every derive is fresh")
import core as CORE  # noqa: E402
if CORE.MINIFY:
    r = gm.get("/static/play.js")
    raw = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "play.js"), "rb").read()
    check(r.status_code == 200 and len(r.data) < len(raw) * 0.95 and b"(()=>{" in r.data[:20], "static JS is served minified")
    r = gm.get("/static/style.css")
    check(r.status_code == 200 and b"\n\n" not in r.data, "and so is the CSS")
import aio as AIO  # noqa: E402
check(AIO.offload(lambda a, b=0: a + b, 2, b=3) == 5, "offload runs work directly outside gevent")

print("\n== light, vision, hidden enemies, movement and areas")
gm.post(f"/api/games/{cid}/combat", json={"op": "end"}, headers=H)
lc = {f"{c},{r}": {"fill": "#123"} for c in range(0, 16) for r in range(0, 6)}
lc["10,2"]["light"] = "dark"
lmap = j(gm.post("/api/maps", json={"name": "Dark test", "campaignId": cid, "width": 16, "height": 6, "data": {"cells": lc, "markers": [
    {"id": "d1", "c": 10, "r": 2, "type": "danger", "label": "Lurker"}, {"id": "d2", "c": 6, "r": 2, "type": "danger", "label": "Guard"},
    {"id": "x1", "c": 10, "r": 3, "type": "loot"}], "rooms": []}}, headers=H))["id"]
gm.post(f"/api/players/{pid}/place", json={"mapId": lmap, "c": 2, "r": 2}, headers=H)
for tr_ in ("physical", "stun"):
    gm.post(f"/api/players/{pid}/sheet/action", json={"action": "set_damage", "track": tr_, "value": 0}, headers=H)
gm.post(f"/api/players/{pid}/sheet/action", json={"action": "gamemaster_set", "current_edge": 0}, headers=H)
gm.post(f"/api/maps/{lmap}/reveal", json={"players": [pid], "cells": list(lc), "action": "reveal"}, headers=H)
pc = j(pl.get("/api/me/sheet"))["char"]
for it in list(pc["inventory"]):
    if it["name"].startswith(("Glasses", "Thermographic", "Low-Light", "Flashlight")):
        gm.post(f"/api/players/{pid}/sheet/action", json={"action": "remove_item", "uid": it["uid"]}, headers=H)
eyes0 = j(pl.get("/api/me/state"))["view"]["eyes"]["vision"]
v = j(pl.get("/api/me/state"))["view"]
seen = {m["id"] for m in v["map"]["markers"]}
if not ({"Thermographic", "Ultrasound"} & set(eyes0)):
    check("d2" in seen and "d1" not in seen and "x1" in seen, "an enemy in a dark cell is hidden from normal eyes; loot stays on the map", (eyes0, seen))
check(v["map"]["cells"]["10,2"].get("light") == "dark" and v["map"]["settings"]["cellMeters"] == 2, "players get the light of their cells and the map's scale")
gm.post(f"/api/players/{pid}/sheet/action", json={"action": "give", "ref": "tools-sensors-glasses", "rating": 2}, headers=H)
gm.post(f"/api/players/{pid}/sheet/action", json={"action": "give", "ref": "tools-sensors-thermographic-vision"}, headers=H)
v = j(pl.get("/api/me/state"))["view"]
check("Thermographic" in v["eyes"]["vision"], "glasses with a thermographic enhancement give thermographic vision")
check("d1" in {m["id"] for m in v["map"]["markers"]}, "thermographic vision sees the enemy in the dark")
gm.post(f"/api/maps/{lmap}/light", json={"cells": ["4,2"], "smoke": "thermal"}, headers=H)
v = j(pl.get("/api/me/state"))["view"]
check(v["map"]["cells"]["4,2"].get("smoke") == "thermal", "smoke painted by the GM reaches the players")
m_ = j(gm.get(f"/api/maps/{lmap}"))
gm.put(f"/api/maps/{lmap}", json={"data": dict(m_["data"], cells={k: {kk: vv for kk, vv in c.items() if kk not in ("light", "smoke")} for k, c in m_["data"]["cells"].items()})}, headers=H)
check(j(gm.get(f"/api/maps/{lmap}"))["data"]["cells"]["4,2"].get("smoke") == "thermal", "an editor autosave keeps live light and smoke")
gm.post(f"/api/maps/{lmap}/light", json={"cells": ["4,2"], "smoke": ""}, headers=H)
sg = j(gm.post(f"/api/maps/{lmap}/sight", json={"a": {"kind": "player", "id": pid}, "b": {"kind": "marker", "id": "d2"}}, headers=H))["sight"]
check(sg["meters"] == 8 and sg["band"] == "Near", "sight gives the distance in meters and the range band (2 m cells)")
# darkness everywhere: the runner (thermographic) sees the guard, the guard (normal eyes) can't see the runner
gm.post(f"/api/maps/{lmap}/light", json={"cells": list(lc), "light": "dark"}, headers=H)
r = gm.post(f"/api/maps/{lmap}/attack", json={"attacker": {"kind": "marker", "id": "d2"}, "weapon": "0", "range": "auto", "target": {"kind": "player", "id": pid}}, headers=H)
check(r.status_code == 400 and "can't see" in j(r)["error"], "an attacker who can't see the target in the dark fails", j(r).get("error"))
gm.post(f"/api/maps/{lmap}/marker", json={"id": "d2", "npc": {"attrs": {"Body": 3, "Agility": 3, "Reaction": 3, "Strength": 3, "Willpower": 3, "Logic": 3, "Intuition": 3, "Charisma": 3}, "dr": 3,
                                                              "weapons": [{"name": "Knife", "skill": "Close Combat", "dv": 2, "ar": [6, None, None, None, None]}]}, "cm": {"pm": 10, "sm": 10}}, headers=H)
pc = j(pl.get("/api/me/sheet"))
wkey = next(p_["key"] for p_ in pc["pools"] if p_["key"].startswith("weapon:") and p_["key"] != "weapon:unarmed")
gm.post(f"/api/players/{pid}/sheet/action", json={"action": "set_ammo", "uid": wkey[7:], "rounds": 15}, headers=H)
r = gm.post(f"/api/maps/{lmap}/attack", json={"attacker": {"kind": "player", "id": pid}, "weapon": wkey, "mode": "SA", "range": "auto", "target": {"kind": "marker", "id": "d2"}}, headers=H)
res = j(r).get("result") or {}
check(r.status_code == 200 and res.get("range") == "Near", "range 'auto' takes the band from the map", j(r).get("error"))
check(any("sees better" in n for n in res.get("notes") or []) or res.get("vision_edge"), "seeing in the dark while the target can't gives 1 Edge", res.get("notes"))
gm.post(f"/api/maps/{lmap}/light", json={"cells": list(lc), "light": ""}, headers=H)
gm.post(f"/api/maps/{lmap}/light", json={"cells": ["4,2", "5,2"], "smoke": "smoke"}, headers=H)
gm.post(f"/api/players/{pid}/sheet/action", json={"action": "remove_item", "uid": next(i["uid"] for i in j(pl.get("/api/me/sheet"))["char"]["inventory"] if i["name"].startswith("Thermographic"))}, headers=H)
r = gm.post(f"/api/maps/{lmap}/attack", json={"attacker": {"kind": "player", "id": pid}, "weapon": wkey, "mode": "SA", "range": "auto", "target": {"kind": "marker", "id": "d2"}}, headers=H)
parts = (j(r).get("result") or {}).get("attack", {}).get("parts") or []
if not ({"Thermographic", "Ultrasound"} & set(eyes0)):
    check(any(p_[0].startswith("Smoke") and p_[1] == -3 for p_ in parts), "shooting through smoke: Blinded I, −3 dice", parts)
gm.post(f"/api/maps/{lmap}/light", json={"cells": ["4,2", "5,2"], "smoke": ""}, headers=H)
# movement in combat (the guard back on its feet: the attacks above may have dropped it)
gm.post(f"/api/maps/{lmap}/marker", json={"id": "d2", "cm": {"pm": 10, "sm": 10, "p": 0, "s": 0}}, headers=H)
gm.post(f"/api/maps/{lmap}/status", json={"target": {"kind": "player", "id": pid}, "status": "Prone", "on": False}, headers=H)
tr = j(gm.post(f"/api/games/{cid}/combat", json={"op": "start", "players": [pid], "mapId": lmap, "markers": ["d2"], "roll": True, "visible": True}, headers=H))["tracker"]
pl.post("/api/me/initiative", json={}, headers=H)
me_e = next(e for e in j(gm.get(f"/api/games/{cid}/combat"))["tracker"]["entries"] if e["ref"] == pid)
gm.post(f"/api/games/{cid}/combat", json={"op": "turn", "id": me_e["id"]}, headers=H)
mv = j(pl.get("/api/me/state"))["view"]["movement"]
check(mv["yourTurn"] and mv["walk"] == 10 and mv["sprint"] == 15, "the movement overlay: 10 m walking, 15 m sprinting", mv)
r = pl.post("/api/me/move", json={"c": 6, "r": 3}, headers=H)
check(r.status_code == 200 and j(r)["token"] == {"c": 6, "r": 3}, "a 10 m move spends the Move (a Minor Action)", j(r).get("error"))
r = pl.post("/api/me/move", json={"c": 7, "r": 3}, headers=H)
check(r.status_code == 400 and "Sprint can't follow a Move" in j(r)["error"], "the Move covers 10 m; a Sprint can't follow it")
gm.post(f"/api/games/{cid}/combat", json={"op": "round"}, headers=H)
gm.post(f"/api/games/{cid}/combat", json={"op": "turn", "id": me_e["id"]}, headers=H)
r = pl.post("/api/me/move", json={"c": 15, "r": 3}, headers=H)
check(r.status_code == 200 and j(r)["token"]["c"] >= 13, "a longer move becomes a Sprint (15 m plus hits)", j(r).get("token"))
check(any("Sprint" in (x["data"].get("label") or "") for x in j(gm.get(f"/api/games/{cid}"))["rolls"][:3]), "the Sprint test goes to the table log")
gm.post(f"/api/games/{cid}/combat", json={"op": "next"}, headers=H)
r = pl.post("/api/me/move", json={"c": 10, "r": 3}, headers=H)
check(r.status_code == 400 and "turn" in j(r).get("error", ""), "runners move on their own turn", (r.status_code, j(r).get("error"), j(r).get("token")))
r = gm.post(f"/api/players/{pid}/place", json={"mapId": lmap, "c": 2, "r": 2}, headers=H)
check(r.status_code == 200, "the GM moves anyone any time")
gm.post(f"/api/maps/{lmap}/status", json={"target": {"kind": "player", "id": pid}, "status": "Prone", "on": True}, headers=H)
gm.post(f"/api/games/{cid}/combat", json={"op": "round"}, headers=H)
gm.post(f"/api/games/{cid}/combat", json={"op": "turn", "id": me_e["id"]}, headers=H)
mv = j(pl.get("/api/me/state"))["view"]["movement"]
check(mv["walk"] == 2 and mv["sprint"] == 0 and "Prone" in mv["why"], "Prone: 2 m and no Sprint", mv)
gm.post(f"/api/maps/{lmap}/status", json={"target": {"kind": "player", "id": pid}, "status": "Prone", "on": False}, headers=H)
gm.post(f"/api/games/{cid}/combat", json={"op": "end"}, headers=H)
import movement as MVM  # noqa: E402
a_ = MVM.allowance([10, 15, 1], {"Hobbled": True, "Fatigued": 3}, "OK")
check(a_["walk"] == 3 and MVM.sprint_cap(a_, 4) == 7, "Hobbled halves (round up) and Fatigued III slows to 5/10 m", a_)
check(not MVM.allowance([10, 15, 1], {"Immobilized": True}, "OK")["canMove"] and not MVM.allowance([10, 15, 1], {}, "Unconscious")["canMove"], "Immobilized or out cold: no movement")
# areas
gm.post(f"/api/players/{pid}/sheet/action", json={"action": "give", "ref": "ammo-explosives-fragmentation-grenade"}, headers=H)
gid = next(i["uid"] for i in j(pl.get("/api/me/sheet"))["char"]["inventory"] if i["name"].startswith("Fragmentation Grenade"))
r = pl.post("/api/me/templates", json={"op": "add", "source": {"type": "item", "uid": gid}, "c": 6, "r": 2}, headers=H)
t_ = (j(r).get("templates") or [{}])[-1]
check(r.status_code == 200 and t_.get("radius") == 20 and t_.get("dv") == ["16P", "12P", "8P"], "a runner places their grenade's blast", t_)
for _ in range(3):
    r = pl.post("/api/me/templates", json={"op": "add", "source": {"type": "custom", "radius": 3}, "c": 3, "r": 3}, headers=H)
check(r.status_code == 400, "runners have 3 areas at most")
r = gm.post(f"/api/maps/{lmap}/templates", json={"op": "add", "template": {"kind": "smoke", "radius": 2, "name": "Smoke"}, "c": 12, "r": 2}, headers=H)
tid = j(r)["templates"][-1]["id"]
r = gm.post(f"/api/maps/{lmap}/templates", json={"op": "smoke", "id": tid, "smoke": "thermal"}, headers=H)
sm_cells = [k for k, c in j(gm.get(f"/api/maps/{lmap}"))["data"]["cells"].items() if c.get("smoke") == "thermal"]
check(r.status_code == 200 and {"12,2", "13,2", "12,1"} <= set(sm_cells) and "14,2" not in sm_cells, "the GM fills a cloud with smoke (2 m around, 2 m cells)", sorted(sm_cells))
r = pl.post("/api/me/templates", json={"op": "remove", "id": tid}, headers=H)
check(r.status_code == 400, "runners can't remove the GM's areas")
gm.post(f"/api/maps/{lmap}/templates", json={"op": "clear"}, headers=H)
check(not j(gm.get(f"/api/maps/{lmap}"))["data"]["templates"], "the GM clears the areas")
# flashlight
gm.post(f"/api/maps/{lmap}/light", json={"cells": list(lc), "light": "dark", "smoke": ""}, headers=H)
r = pl.post("/api/me/flashlight", json={"on": True}, headers=H)
check(r.status_code == 400, "no flashlight, no light")
gm.post(f"/api/players/{pid}/sheet/action", json={"action": "give", "ref": "survival-flashlight"}, headers=H)
v = j(pl.post("/api/me/flashlight", json={"on": True}, headers=H))
check(v["flashlight"]["on"] and not v["map"]["cells"]["3,2"].get("light") and v["map"]["cells"]["12,2"].get("light") == "dark",
      "a flashlight lights the cells around its holder (10 m)")
pl.post("/api/me/flashlight", json={"on": False}, headers=H)
# stealth
gm.post(f"/api/maps/{lmap}/light", json={"cells": list(lc), "light": "", "smoke": ""}, headers=H)
gm.post(f"/api/players/{pid}/place", json={"mapId": lmap, "c": 2, "r": 2}, headers=H)
gm.post(f"/api/maps/{lmap}/marker", json={"id": "d2", "cm": {"pm": 10, "sm": 10, "p": 0, "s": 0}}, headers=H)
v = j(pl.post("/api/me/stealth", json={"on": True}, headers=H))
check(v["stealth"]["on"] and "hits" not in v["stealth"], "ticking Stealth starts sneaking (the GM keeps the rolls by default)", v.get("stealth"))
gst = next(p_ for p_ in j(gm.get(f"/api/maps/{lmap}/context"))["players"] if p_["id"] == pid)["state"].get("stealth") or {}
check(gst.get("on") and isinstance(gst.get("hits"), int) and {"d1", "d2"} <= set(gst.get("checked") or []), "every enemy in view rolls Perception against the Stealth hits", gst)
prolls = j(pl.get("/api/me/state"))["rolls"]
check(not any("Stealth" in (x["data"].get("label") or x["data"].get("text") or "") for x in prolls), "players don't see stealth rolls unless the GM shows them")
check(any("sneaks past" in (x["data"].get("text") or "") for x in j(gm.get(f"/api/games/{cid}"))["rolls"][:5]), "the GM sees the Perception tests")
gm.post(f"/api/maps/{lmap}/marker", json={"id": "d2", "npc": {"attrs": {"Body": 3, "Agility": 3, "Reaction": 3, "Strength": 3, "Willpower": 3, "Logic": 3, "Intuition": 12, "Charisma": 3},
                                                              "skills": {"Perception": 30}, "dr": 3}}, headers=H)
r = gm.post(f"/api/players/{pid}/stealth", json={"op": "check"}, headers=H)
gst = j(r)["player"]["state"]["stealth"]
check(r.status_code == 200 and "d2" in gst["spotted"], "the GM has everyone roll again: a sharp-eyed guard notices the runner", gst)
v = j(pl.get("/api/me/state"))["view"]
check("d2" in v["stealth"].get("watchers", []), "the runner sees which enemies in view have eyes on them", v["stealth"])
gm.post(f"/api/maps/{lmap}/light", json={"cells": list(lc), "light": "dark"}, headers=H)
if not ({"Thermographic", "Ultrasound"} & set(eyes0)):
    v = j(pl.get("/api/me/state"))["view"]
    check("d2" not in v["stealth"].get("watchers", []), "in the dark, a guard with normal eyes can't see the runner", v["stealth"])
gm.post(f"/api/maps/{lmap}/light", json={"cells": list(lc), "light": ""}, headers=H)
r = gm.post(f"/api/players/{pid}/stealth", json={"op": "end"}, headers=H)
check(not j(r)["player"]["state"].get("stealth"), "the GM ends a runner's stealth")
gm.put(f"/api/games/{cid}/settings", json={"stealthRolls": True}, headers=H)
v = j(pl.post("/api/me/stealth", json={"on": True}, headers=H))
check(isinstance(v["stealth"].get("hits"), int), "with stealth rolls shown, the runner sees their hits", v["stealth"])
check(any((x["data"].get("label") or "").startswith("Stealth + Agility") for x in j(pl.get("/api/me/state"))["rolls"][:5]), "and the table log shows the Stealth test")
gm.put(f"/api/games/{cid}/settings", json={"stealthRolls": False}, headers=H)
gm.post(f"/api/players/{pid}/sheet/action", json={"action": "set_ammo", "uid": wkey[7:], "rounds": 15}, headers=H)
r = gm.post(f"/api/maps/{lmap}/attack", json={"attacker": {"kind": "player", "id": pid}, "weapon": wkey, "mode": "SA", "range": "auto", "target": {"kind": "marker", "id": "d2"}}, headers=H)
check(r.status_code == 200 and not j(pl.get("/api/me/state"))["view"]["stealth"]["on"], "attacking ends stealth", j(r).get("error"))
pl.post("/api/me/stealth", json={"on": True}, headers=H)
v = j(pl.post("/api/me/stealth", json={"on": False}, headers=H))
check(not v["stealth"]["on"], "unticking Stealth stops sneaking")
import stealth as STM  # noqa: E402
check(STM.perception_parts({"npc": {"attrs": {"Intuition": 4}, "skills": {"Perception": 3}}}, 1)[-1] == ["Blinded 1", -3], "smoke between them: −3 to the guard's Perception")
# per-map legend
m_ = j(gm.get(f"/api/maps/{lmap}"))
gm.put(f"/api/maps/{lmap}", json={"settings": dict(m_["settings"], legendVisible=False)}, headers=H)
check(j(pl.get("/api/me/state"))["view"]["map"]["settings"]["legendVisible"] is False, "the GM hides the legend from players on a map")
gm.delete(f"/api/maps/{lmap}", headers=H)
# shared contacts
r = gm.post(f"/api/games/{cid}/contacts", json={"op": "save", "contact": {"name": "Mr. Johnson", "type": "Fixer", "connection": 6, "loyalty": 2}}, headers=H)
shared = j(r)["settings"]["contacts"]
check(r.status_code == 200 and len(shared) == 1 and shared[0]["connection"] == 6, "the GM gives every runner a contact", j(r))
cts = j(pl.get("/api/me/sheet"))["char"]["contacts"]
gct = next((x for x in cts if x.get("game")), None)
check(gct and gct["name"] == "Mr. Johnson" and gct["verified"], "the shared contact shows on the runner's sheet, confirmed", cts)
gi = cts.index(gct)
r = pl.post("/api/me/sheet/action", json={"action": "remove_contact", "index": gi}, headers=H)
check(r.status_code == 400, "runners can't remove a shared contact")
r = pl.post("/api/me/sheet/action", json={"action": "save_contact", "index": gi, "contact": {"name": "Mr. J", "connection": 12}}, headers=H)
check(r.status_code == 400, "or change it")
gm.post(f"/api/games/{cid}/contacts", json={"op": "save", "contact": dict(shared[0], loyalty=4)}, headers=H)
check(next(x for x in j(pl.get("/api/me/sheet"))["char"]["contacts"] if x.get("game"))["loyalty"] == 4, "the GM's edit reaches every sheet")
from sr import catalog as CATM  # noqa: E402
check(CATM.access({"contacts": [gct]}, 4, "", "Weapons", True)[0], "a shared Fixer sources gear like any contact")
gm.post(f"/api/games/{cid}/contacts", json={"op": "remove", "id": shared[0]["id"]}, headers=H)
check(not any(x.get("game") for x in j(pl.get("/api/me/sheet"))["char"]["contacts"]), "removing it takes it from every sheet")
# runners hand things to each other
dk_id = j(dk.get("/api/me/state"))["me"]["id"]
dk_ok = j(gm.get(f"/api/players/{dk_id}/sheet"))["approved"]
gm.post(f"/api/players/{dk_id}/review", json={"decision": "reopen"}, headers=H)
dk_ok = False
if not dk_ok:
    r = pl.post("/api/me/transfer", json={"to": dk_id, "nuyen": 10}, headers=H)
    check(r.status_code == 400 and "approved" in j(r)["error"], "nothing goes to a runner whose sheet isn't approved", j(r))
gm.post(f"/api/players/{dk_id}/review", json={"decision": "approve"}, headers=H)
gm.post(f"/api/players/{pid}/sheet/action", json={"action": "gamemaster_set", "nuyen": 5000}, headers=H)
n_dk = j(dk.get("/api/me/sheet"))["char"]["nuyen"]
r = pl.post("/api/me/transfer", json={"to": dk_id, "nuyen": 1200}, headers=H)
check(r.status_code == 200 and j(r)["sheet"]["char"]["nuyen"] == 3800 and j(dk.get("/api/me/sheet"))["char"]["nuyen"] == n_dk + 1200, "a runner hands nuyen to another", j(r))
check(any(x.get("reason") == "Given to " + j(dk.get("/api/me/sheet"))["player"]["name"] or "Given to" in (x.get("reason") or "") for x in j(pl.get("/api/me/sheet"))["ledger"][:3]), "it shows in both ledgers")
r = pl.post("/api/me/transfer", json={"to": dk_id, "nuyen": 999999}, headers=H)
check(r.status_code == 400, "no more than they have")
r = pl.post("/api/me/transfer", json={"to": pid, "nuyen": 5}, headers=H)
check(r.status_code == 400, "not to themselves")
gm.post(f"/api/players/{pid}/sheet/action", json={"action": "give", "ref": "ammo-explosives-fragmentation-grenade", "qty": 4}, headers=H)
sg = next(i for i in j(pl.get("/api/me/sheet"))["char"]["inventory"] if i["name"].startswith("Fragmentation Grenade"))
r = pl.post("/api/me/transfer", json={"to": dk_id, "uid": sg["uid"], "qty": 1}, headers=H)
got = [i for i in j(dk.get("/api/me/sheet"))["char"]["inventory"] if i["name"].startswith("Fragmentation Grenade")]
left = next((i for i in j(pl.get("/api/me/sheet"))["char"]["inventory"] if i["uid"] == sg["uid"]), None)
check(r.status_code == 200 and got and got[0]["qty"] == 1 and left and left["qty"] == sg["qty"] - 1, "part of a stack changes hands", (j(r), got, left))
wpn_ = next(i for i in j(pl.get("/api/me/sheet"))["char"]["inventory"] if i["cat"] == "Ranged")
r = pl.post("/api/me/transfer", json={"to": dk_id, "uid": wpn_["uid"]}, headers=H)
check(r.status_code == 200 and any(i["name"] == wpn_["name"] for i in j(dk.get("/api/me/sheet"))["char"]["inventory"])
      and not any(i["uid"] == wpn_["uid"] for i in j(pl.get("/api/me/sheet"))["char"]["inventory"]), "a weapon changes hands, loaded as it was")
imp = next((i for i in j(pl.get("/api/me/sheet"))["char"]["inventory"] if i.get("implant")), None)
if imp:
    r = pl.post("/api/me/transfer", json={"to": dk_id, "uid": imp["uid"]}, headers=H)
    check(r.status_code == 400 and "installed" in j(r)["error"], "implants stay in the body")
check(any("gives" in (x["data"].get("text") or "") for x in j(gm.get(f"/api/games/{cid}"))["rolls"][:4]), "the table log says who gave what")
# walls for the first-person view, and locked doors
wm = j(gm.post("/api/maps", json={"name": "Walls", "campaignId": cid, "width": 6, "height": 4, "data": {"cells": {
    "1,1": {"fill": "#123", "doors": {"1": {"color": "#fff", "open": False, "locked": True}}}, "2,1": {"fill": "#123", "doors": {"3": {"color": "#fff", "open": False}}},
    "3,1": {"fill": "#123"}, "1,2": {"fill": "#123", "secret": True}}, "markers": [], "rooms": []}}, headers=H))["id"]
gm.post(f"/api/players/{pid}/place", json={"mapId": wm, "c": 2, "r": 1}, headers=H)
gm.post(f"/api/maps/{wm}/reveal", json={"players": [pid], "cells": ["1,1", "2,1"], "action": "reveal"}, headers=H)
gm.post(f"/api/maps/{wm}/reveal", json={"players": [pid], "cells": ["3,1"], "action": "hide"}, headers=H)
pc_ = j(pl.get("/api/me/state"))["view"]["map"]["cells"]
check(pc_["1,1"]["w"] == (1 | 4 | 8) and pc_["2,1"]["w"] == (1 | 4), "explored cells say which edges are walls (an unfound secret cell counts as one)", (pc_["1,1"], pc_["2,1"]))
check("3,1" not in pc_, "unexplored rooms stay unknown")
r = pl.post("/api/me/door", json={"edge": 3}, headers=H)
check(r.status_code == 400 and "locked" in j(r)["error"], "a door locked on the other side's copy stays shut")
r = pl.post("/api/me/move", json={"c": 1, "r": 1}, headers=H)
check(r.status_code == 400, "and nobody walks through it")
gm.post(f"/api/players/{pid}/place", json={"mapId": mid, "c": 2, "r": 2}, headers=H)
gm.delete(f"/api/maps/{wm}", headers=H)
# a runner's own turn: attack, actions, condition, ending the turn
for tr_ in ("physical", "stun"):
    gm.post(f"/api/players/{pid}/sheet/action", json={"action": "set_damage", "track": tr_, "value": 0}, headers=H)
for st_ in ("Prone", "Blinded", "Restrained", "Panicked", "Petrified", "Stilled"):
    gm.post(f"/api/maps/{mid}/status", json={"target": {"kind": "player", "id": pid}, "status": st_, "on": False}, headers=H)
cm_ = {f"{c},{r}": {"fill": "#123"} for c in range(1, 8) for r in range(1, 4)}
am = j(gm.post("/api/maps", json={"name": "Arena", "campaignId": cid, "width": 9, "height": 5, "data": {"cells": cm_, "markers": [
    {"id": "foe", "c": 3, "r": 2, "type": "danger", "label": "Foe", "cm": {"pm": 10, "sm": 10, "p": 0, "s": 0},
     "npc": {"attrs": {"Body": 3, "Agility": 3, "Reaction": 3, "Strength": 3, "Willpower": 3, "Logic": 3, "Intuition": 3, "Charisma": 3}, "dr": 2, "skills": {}}}], "rooms": []}}, headers=H))["id"]
gm.post(f"/api/players/{pid}/place", json={"mapId": am, "c": 2, "r": 2}, headers=H)
gm.post(f"/api/maps/{am}/reveal", json={"players": [pid], "cells": list(cm_), "action": "reveal"}, headers=H)
gm.post(f"/api/players/{pid}/sheet/action", json={"action": "give", "ref": "melee-combat-axe"}, headers=H)
axe = next(i for i in j(pl.get("/api/me/sheet"))["char"]["inventory"] if i["name"] == "Combat Axe")
r = pl.post("/api/me/attack", json={"targets": [{"kind": "marker", "id": "foe"}], "weapon": "weapon:" + axe["uid"]}, headers=H)
check(r.status_code == 400 and "combat" in j(r)["error"], "outside combat, runners don't resolve attacks", j(r))
gm.post(f"/api/games/{cid}/combat", json={"op": "start", "players": [pid], "mapId": am, "markers": ["foe"], "roll": True, "visible": True}, headers=H)
cv = j(pl.get("/api/me/state"))["view"]["combat"]
check(cv["inCombat"] and not cv["rolled"], "in combat, the runner rolls initiative first", cv)
pl.post("/api/me/initiative", json={}, headers=H)
ents = j(gm.get(f"/api/games/{cid}/combat"))["tracker"]["entries"]
me_e = next(e for e in ents if e["ref"] == pid)
foe_e = next(e for e in ents if e["ref"] == "foe")
gm.post(f"/api/games/{cid}/combat", json={"op": "turn", "id": foe_e["id"]}, headers=H)
cv = j(pl.get("/api/me/state"))["view"]["combat"]
check(cv["rolled"] and not cv["myTurn"], "the runner waits for their turn", cv)
r = pl.post("/api/me/attack", json={"targets": [{"kind": "marker", "id": "foe"}], "weapon": "weapon:" + axe["uid"]}, headers=H)
check(r.status_code == 400 and "not your turn" in j(r)["error"], "no attacking out of turn", j(r))
r = pl.post("/api/me/end-turn", json={}, headers=H)
check(r.status_code == 400, "nor ending someone else's turn")
gm.post(f"/api/games/{cid}/combat", json={"op": "turn", "id": me_e["id"]}, headers=H)
cv = j(pl.get("/api/me/state"))["view"]["combat"]
check(cv["myTurn"] and cv["canAttack"], "on their turn the attack unlocks", cv)
ao = j(pl.get("/api/me/attack-options"))
check(any(t_["ref"]["id"] == "foe" and t_["los"] for t_ in ao["targets"]) and "dr" not in ao, "the attack dialog lists who they can see (not the enemy's stats)", ao.get("targets"))
r = pl.post("/api/me/roll", json={"key": "weapon:" + axe["uid"]}, headers=H)
check(r.status_code == 400 and "Attack button" in j(r)["error"], "in combat, a weapon isn't rolled bare from the dice panel", j(r))
r = pl.post("/api/me/attack", json={"targets": [{"kind": "marker", "id": "nobody"}], "weapon": "weapon:" + axe["uid"]}, headers=H)
check(r.status_code == 400, "only targets the runner can see")
r = pl.post("/api/me/attack", json={"targets": [{"kind": "marker", "id": "foe"}], "weapon": "weapon:" + axe["uid"]}, headers=H)
res = j(r).get("result") or {}
check(r.status_code == 200 and res.get("summary") and "attack" in res, "the runner attacks: defense and damage rolled at once", j(r))
check(not any(x.get("hidden") for x in j(r)["rolls"]), "and gets the players' log back, not the GM's")
cv = j(pl.get("/api/me/state"))["view"]["combat"]
check(cv["majorLeft"] == 0 and not cv["canAttack"] and "Major" in cv["why"], "the Major Action is spent: no second attack", cv)
r = pl.post("/api/me/attack", json={"targets": [{"kind": "marker", "id": "foe"}], "weapon": "weapon:" + axe["uid"]}, headers=H)
check(r.status_code == 400 and "Major" in j(r)["error"], "the server agrees", j(r))
r = gm.post(f"/api/maps/{am}/attack", json={"attacker": {"kind": "player", "id": pid}, "weapon": "weapon:" + axe["uid"], "target": {"kind": "marker", "id": "foe"}}, headers=H)
check(r.status_code == 400 and "Major" in j(r)["error"], "the GM can't attack with them either", j(r))
r = gm.post(f"/api/maps/{am}/attack", json={"attacker": {"kind": "player", "id": pid}, "weapon": "weapon:" + axe["uid"], "target": {"kind": "marker", "id": "foe"}, "ignoreActions": True, "apply": False}, headers=H)
check(r.status_code == 200, "unless the GM ignores the action limits")
r = pl.post("/api/me/end-turn", json={}, headers=H)
t_ = j(gm.get(f"/api/games/{cid}/combat"))["tracker"]
check(r.status_code == 200 and t_["current"] != me_e["id"], "the runner ends their turn", t_.get("current"))
gm.post(f"/api/maps/{am}/marker", json={"id": "foe", "cm": {"pm": 10, "sm": 10, "p": 0, "s": 10}}, headers=H)
r = gm.post(f"/api/maps/{am}/attack", json={"attacker": {"kind": "marker", "id": "foe"}, "weapon": "-1", "target": {"kind": "player", "id": pid}}, headers=H)
check(r.status_code == 400 and "unconscious" in j(r)["error"], "an unconscious enemy can't attack", j(r))
gm.post(f"/api/maps/{am}/marker", json={"id": "foe", "cm": {"pm": 10, "sm": 10, "p": 0, "s": 0}}, headers=H)
gm.post(f"/api/games/{cid}/combat", json={"op": "round"}, headers=H)
gm.post(f"/api/games/{cid}/combat", json={"op": "turn", "id": me_e["id"]}, headers=H)
gm.post(f"/api/maps/{am}/status", json={"target": {"kind": "player", "id": pid}, "status": "Stilled", "on": True}, headers=H)
cv = j(pl.get("/api/me/state"))["view"]["combat"]
check(not cv["canAttack"] and "Stilled" in cv["why"], "Stilled: no attack", cv)
gm.post(f"/api/maps/{am}/status", json={"target": {"kind": "player", "id": pid}, "status": "Stilled", "on": False}, headers=H)
gm.post(f"/api/games/{cid}/combat", json={"op": "end"}, headers=H)
gm.post(f"/api/players/{pid}/place", json={"mapId": mid, "c": 2, "r": 2}, headers=H)
gm.delete(f"/api/maps/{am}", headers=H)
from sr import npc6e as N6  # noqa: E402
from sr import combat as X  # noqa: E402
check(X.npc_vision(X.parse_template(next(t for t in N6.NPC_TEMPLATES if t["name"].startswith("Sons of Sauron")))) == ["Low-light"], "an ork NPC sees in low light")
check(X.npc_vision({}, {"vision": ["Ultrasound"], "label": "Ork"}) == ["Ultrasound"], "the GM's word on an NPC's eyes wins")

m_ = j(gm.get(f"/api/maps/{mid}"))
gm.put(f"/api/maps/{mid}", json={"settings": dict(m_["settings"], playerView="fp")}, headers=H)
check(j(gm.get(f"/api/maps/{mid}"))["settings"]["playerView"] == "fp", "the GM fixes how players see a map")
gm.put(f"/api/maps/{mid}", json={"settings": dict(m_["settings"], playerView="sideways")}, headers=H)
check(j(gm.get(f"/api/maps/{mid}"))["settings"]["playerView"] == "choose", "an unknown view falls back to the players' choice")
gm.put(f"/api/maps/{mid}", json={"settings": dict(m_["settings"], playerView="choose")}, headers=H)

print()
print("FAILED: %d" % len(FAILS) if FAILS else "All checks passed.")
sys.exit(1 if FAILS else 0)
