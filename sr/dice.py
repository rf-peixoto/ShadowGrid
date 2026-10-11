"""Shadowrun 6E dice engine: hits, glitches, the Wild Die and Edge Boosts.

Rules implemented (SR6 core):
- A die showing 5 or 6 is a hit.
- Glitch: more than half of the dice rolled show 1. Critical glitch: a glitch with no hits.
- Wild Die: one die of the pool. On a 5 or 6 it counts as 3 hits; on a 1, none of
  the 5s in the roll count as hits.
- Edge Boosts, one per roll:
    before rolling  4 Edge  add Edge rating to the pool, 6s explode
    after rolling   1 Edge  reroll one die (1 Edge per die rerolled)
                    2 Edge  +1 to one die
                    3 Edge  buy one automatic hit
                    4 Edge  reroll every failed die
- Threshold: success when hits >= threshold (or at least one hit if there is none).

A roll is a dict stored as JSON in the ``rolls`` table so post-roll boosts can
be applied to it later and every player sees the same result.
"""
import secrets

_rng = secrets.SystemRandom()
MAX_POOL = 60
MAX_EXPLOSIONS = 40

POST_BOOSTS = {
    "reroll": (1, "Reroll {n} die"),          # cost per die
    "plus_one": (2, "+1 to a die"),
    "buy_hit": (3, "Bought 1 hit"),
    "reroll_failed": (4, "Rerolled all failed dice"),
}
PUSH_COST = 4


class DiceError(ValueError):
    pass


def d6():
    return _rng.randint(1, 6)


def _explode(dice):
    added = 0
    i = 0
    while i < len(dice) and added < MAX_EXPLOSIONS:
        if dice[i]["v"] == 6 and not dice[i].get("e"):
            dice[i]["e"] = 1                      # this 6 has exploded
            dice.append({"v": d6(), "x": 1})      # extra die from an explosion
            added += 1
        i += 1


def new_roll(pool, wild=False, push_edge=0, threshold=0):
    """Roll ``pool`` dice (+ ``push_edge`` with exploding 6s when Pushing the Limit)."""
    pool = max(0, min(MAX_POOL, int(pool)))
    total = pool + max(0, int(push_edge))
    if total <= 0:
        raise DiceError("The dice pool is empty.")
    dice = [{"v": d6()} for _ in range(min(MAX_POOL, total))]
    if wild:
        dice[0]["w"] = 1
    r = {"dice": dice, "pool": len(dice), "threshold": max(0, min(30, int(threshold or 0))),
         "bought": 0, "boost": None, "explode": bool(push_edge)}
    if push_edge:
        _explode(dice)
        r["boost"] = {"key": "push", "cost": PUSH_COST, "label": f"Pushed the limit (+{push_edge} dice, exploding 6s)"}
    return evaluate(r)


def evaluate(r):
    dice = r["dice"]
    wild = next((d for d in dice if d.get("w")), None)
    wild_one = bool(wild and wild["v"] == 1)
    hits = 0
    for d in dice:
        d.pop("h", None)
        d.pop("c", None)
        if d.get("w"):
            if d["v"] >= 5:
                hits += 3
                d["h"] = 3
        elif d["v"] == 6 or (d["v"] == 5 and not wild_one):
            hits += 1
            d["h"] = 1
        elif d["v"] == 5 and wild_one:
            d["c"] = 1                           # a 5 cancelled by the Wild Die's 1
    hits += r.get("bought", 0)
    base = [d for d in dice if not d.get("x")]
    ones = sum(1 for d in base if d["v"] == 1)
    glitch = bool(base) and ones > len(base) / 2
    r["hits"] = hits
    r["ones"] = ones
    r["glitch"] = glitch
    r["critical"] = glitch and hits == 0
    t = r.get("threshold") or 0
    r["success"] = hits >= t if t else hits > 0
    r["net"] = hits - t if t else None
    r["wildOne"] = wild_one
    return r


def apply_boost(r, key, die_indexes):
    """Apply a post-roll Edge Boost. Returns the Edge cost. Mutates ``r``."""
    if r.get("boost"):
        raise DiceError("Only one Edge Boost per roll.")
    if key not in POST_BOOSTS:
        raise DiceError("Unknown Edge Boost.")
    dice = r["dice"]
    idx = sorted({int(i) for i in (die_indexes or []) if str(i).lstrip("-").isdigit()})
    if any(i < 0 or i >= len(dice) for i in idx):
        raise DiceError("Pick dice from this roll.")
    if key == "reroll":
        if not idx:
            raise DiceError("Select the dice to reroll first.")
        for i in idx:
            dice[i]["v"] = d6()
            dice[i]["r"] = 1
        cost = len(idx)
        label = f"Rerolled {len(idx)} {'die' if len(idx) == 1 else 'dice'}"
    elif key == "plus_one":
        if len(idx) != 1:
            raise DiceError("Select exactly one die to add +1 to.")
        if dice[idx[0]]["v"] >= 6:
            raise DiceError("That die is already a 6.")
        dice[idx[0]]["v"] += 1
        dice[idx[0]]["p"] = 1
        cost, label = 2, "+1 to a die"
    elif key == "buy_hit":
        r["bought"] = r.get("bought", 0) + 1
        cost, label = 3, "Bought 1 automatic hit"
    else:
        failed = [i for i, d in enumerate(dice) if not d.get("h")]
        if not failed:
            raise DiceError("No failed dice to reroll.")
        for i in failed:
            dice[i]["v"] = d6()
            dice[i]["r"] = 1
        cost, label = 4, f"Rerolled {len(failed)} failed {'die' if len(failed) == 1 else 'dice'}"
    if r.get("explode"):
        _explode(dice)
    r["boost"] = {"key": key, "cost": cost, "label": label}
    evaluate(r)
    return cost


def initiative(score, n_dice, plus3=False):
    n_dice = max(1, min(5, int(n_dice)))
    dice = [d6() for _ in range(n_dice)]
    bonus = 3 if plus3 else 0
    return {"score": score, "dice": dice, "bonus": bonus, "total": score + sum(dice) + bonus}
