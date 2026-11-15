"""Versioned, deterministic XCO₂ practice scenarios."""
from datetime import date, timedelta
from random import Random
from statistics import mean
from uuid import uuid4

SOURCE = "Simulated XCO₂ · Practice data"
VARIABLE = "Simulated XCO₂"
KEY = "SIM_XCO2"
BACKGROUND = 420
OFFSETS = {"forest": -1.5, "urban": 1, "industrial": 2, "agricultural": -.2, "polar": 0, "custom": 0}
BOX_DEGREES = 1


def scenario(config):
    return dict(source=SOURCE, version=1, seed=uuid4().hex,
                category=config["target"].get("category", "custom"),
                start=config.get("start") or date.today().isoformat())


def scan(config, index, packets):
    model = config["co2_scenario"]
    target = config["target"]
    category = model["category"]
    rng = Random(f"{model['seed']}:{model['version']}:{index}")
    gap = rng.random() < (.28 if category == "polar" else .10)
    baseline = BACKGROUND + OFFSETS.get(category, 0) + rng.uniform(-1.3, 1.3)
    day = date.fromisoformat(model["start"]) + timedelta(days=index)
    rows = []
    for packet in range(packets):
        good = rng.random() >= .08
        value = round(baseline + rng.uniform(-2, 2) + (1.1 if category == "industrial" and packet == 2 else 0), 2)
        latitude = max(-90, min(90, target["lat"] + rng.uniform(-BOX_DEGREES, BOX_DEGREES)))
        longitude = (target["lon"] + rng.uniform(-BOX_DEGREES, BOX_DEGREES) + 180) % 360 - 180
        rows.append(None if gap else dict(id=f"D{index+1}-P{packet+1}", day=index+1, date=str(day),
            latitude=round(latitude, 5), longitude=round(longitude, 5), xco2_ppm=value,
            quality="Usable" if good else "Questionable", source=SOURCE))
    return rows


def usable(config):
    return [row for row in config.get("co2_transmitted", []) if row["quality"] == "Usable"]


def series(config):
    model = config["co2_scenario"]
    start = date.fromisoformat(model["start"])
    groups = {}
    for row in usable(config):
        groups.setdefault(row["day"], []).append(row["xco2_ppm"])
    days = [start + timedelta(days=i) for i in range(config["duration"])]
    return days, [mean(groups[i]) if i in groups else None for i in range(1, len(days)+1)]