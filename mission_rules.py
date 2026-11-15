"""Deterministic gameplay rules. Credits, energy and observations are game units."""
from math import ceil

from co2_practice import scan as practice_scan, scenario
from scientific_instruments import INSTRUMENTS, payload, supported_collections

COST_PER_DAY = 65
TRANSMIT_COST = 20
REWARD_PER_PACKET = 35
SUCCESS_BONUS = 250
PACKET_GB = 2
ADJUST_ENERGY = 10
ADJUST_COST = 90
POWER_DEPLETION = "Power Depletion"
DURATIONS = (3, 7, 14, 21, 30)
ORBITS = {"LEO": "General low Earth orbit", "SSO": "Sun-synchronous low Earth orbit"}
def plan(satellite, target, settings, environment):
    specs = satellite["specs"]
    selected = set(settings.get('collection', ('Atmospheric CO₂',)))
    if 'collection' in settings and not selected <= supported_collections(satellite):
        raise ValueError('Selected collection requires an installed instrument.')
    active = [key for key in satellite.get('instruments', ()) if INSTRUMENTS[key].collection in selected]
    scan_draw = sum(INSTRUMENTS[key].energy for key in active)
    days, orbit = settings["duration"], settings["orbit"]
    # Surface irradiance is used only as a scenario proxy for reflected-light
    # opportunities. It does not model orbital illumination or retrieval quality.
    accuracy = specs["Data Accuracy"]
    nominal = 2 + int(accuracy >= 50) + int(orbit == "SSO")
    reflected = {'Atmospheric CO₂', 'Land and Vegetation', 'Additional atmospheric measurements'}
    opportunities = [
        (nominal if 'Surface Temperature' in selected else 0)
        + len(selected & reflected) * (max(0, nominal - (2 if light < 1 else 1 if light < 2.5 else 0))
                                       if light is not None else 0)
        for light in (environment["series"] if environment else [3] * days)
    ]
    body = satellite["components"]["body"]
    return dict(days=days, operating_cost=days * COST_PER_DAY, mass=payload(body, satellite.get('instruments', ()))[0],
                storage=specs["Data Capacity"], power=specs["Power"], scan_energy=12 + scan_draw, tx_energy=8,
                opportunities=opportunities,
                downlink={"basic": 3, "advanced": 6, "high_bandwidth": 10}.get(satellite["components"].get("communication"), 6),
                recovery={"basic": 14, "standard": 18, "advanced": 22, "high_efficiency": 26}.get(satellite["components"].get("solar_panels"), 18),
                goal=max(2, ceil(days * .9)),
                credits=satellite["budget"] - satellite["total_cost"])


def readiness(resources):
    if resources["credits"] < resources["operating_cost"] + TRANSMIT_COST:
        return "Configuration Invalid", "Budget must cover operations and at least one transmission."
    if resources["storage"] < PACKET_GB or resources["power"] < resources["scan_energy"] + resources["tx_energy"]:
        return "Configuration Invalid", "The satellite lacks storage or power for a scan and transmission."
    if sum(resources["opportunities"][:-1]) < resources["goal"]:
        return "High Risk", "The modeled opportunities before the final downlink may fall short."
    if sum(resources["opportunities"]) * PACKET_GB > resources["storage"]:
        return "Caution", "Plan intermediate downlinks to avoid filling onboard storage."
    return "Ready", "Reserve time and power for the final downlink."


def initialize(config, resources):
    if "Atmospheric CO₂" in config.get("collection", ()):
        config = dict(config, co2_scenario=scenario(config), co2_transmitted=[])
    return dict(config=config, resources=resources, day=0, energy=resources["power"],
                credits=resources["credits"] - resources["operating_cost"], stored=0,
                transmitted=0, outcome=None, reason="", events=[], adjusted=False)


def action_energy(resources, action):
    return {"scan": resources["scan_energy"], "transmit": resources["tx_energy"],
            "adjust": ADJUST_ENERGY}.get(action, 0)


def action_error(state, action):
    if state["outcome"] or state["energy"] <= 0:
        return "The mission has ended."
    r = state["resources"]
    if action == "scan":
        if state["stored"] >= r["storage"] // PACKET_GB:
            return "Storage is full. Transmit before scanning."
    if action == "transmit":
        if not state["stored"] or state["credits"] < TRANSMIT_COST:
            return "Downlink requires stored packets and credits."
    if action == "adjust":
        if state.get("adjusted") or state["credits"] < ADJUST_COST or state["day"] + 1 >= r["days"]:
            return "Adjustment requires an unused maneuver, 90 credits and a future turn."
    return ""


def step(state, action):
    if state["outcome"]:
        return state
    if state["energy"] <= 0:
        return dict(state, energy=0, outcome="Mission Failure", reason=POWER_DEPLETION)
    if action not in {"scan", "transmit", "conserve", "adjust"}:
        raise ValueError("Unknown mission action")
    if error := action_error(state, action):
        raise ValueError(error)
    result = dict(state)
    r = result["resources"]
    packets = 0
    cost = action_energy(r, action)
    result["energy"] = max(0, min(r["power"], state["energy"] - cost))
    depleted = result["energy"] == 0
    if depleted:
        result["credits"] -= {"transmit": TRANSMIT_COST, "adjust": ADJUST_COST}.get(action, 0)
        message = f"{action.capitalize()} attempted. Satellite power depleted."
    elif action == "scan":
        room = r["storage"] // PACKET_GB - result["stored"]
        opportunity = r["opportunities"][result["day"]]
        if opportunity and result.get("adjusted"):
            opportunity += 1
        packets = min(room, opportunity)
        result["stored"] += packets
        if result["config"].get("co2_scenario") and packets:
            samples = practice_scan(result["config"], result["day"], packets)
            result["co2_buffer"] = [*result.get("co2_buffer", []), *samples]
        message = f"Scan stored {packets} simulated packets." if packets else "Scan found no usable gameplay opportunity."
    elif action == "transmit":
        packets = min(result["stored"], r.get("downlink", 6))
        reward = packets * REWARD_PER_PACKET - TRANSMIT_COST
        result["credits"] += reward
        result["transmitted"] += packets
        result["stored"] -= packets
        if result["config"].get("co2_scenario"):
            buffer = result.get("co2_buffer", [])
            delivered = [row for row in buffer[:packets] if row is not None]
            result["co2_buffer"] = buffer[packets:]
            config = result["config"]
            result["config"] = dict(config, co2_transmitted=[*config["co2_transmitted"], *delivered])
        message = f"Transmitted {packets} packets. Net +{reward} simulated credits."
    elif action == "adjust":
        result["adjusted"] = True
        result["credits"] -= ADJUST_COST
        message = "Simulated orbit adjustment: +1 packet on future usable scans."
    else:
        result["energy"] = min(r["power"], result["energy"] + r.get("recovery", 18))
        message = f"Skipped observation and recovered {result['energy'] - state['energy']} power."
    environment = state["config"].get("environment")
    source_day = state["day"]
    event = dict(day=source_day + 1, action=action, packets=packets, message=message,
                 power_change=result["energy"] - state["energy"], credit_change=result["credits"] - state["credits"])
    if action == "scan" and environment and not depleted:
        event["environment"] = dict(source=environment["source"], start=environment["start"],
                                    offset=source_day, irradiance=environment["series"][source_day],
                                    units=environment["units"])
    result["events"] = [*state.get("events", []), event]
    result["day"] += 1
    if depleted:
        result.update(outcome="Mission Failure", reason=POWER_DEPLETION)
    elif result["transmitted"] >= r["goal"]:
        result.update(outcome="Mission Success", reason="The packet objective was transmitted within resource limits.")
        result["credits"] += SUCCESS_BONUS
    elif result["day"] >= r["days"]:
        reason = "The deadline passed before the science objective was met."
        outcome = "Partial Success" if result["transmitted"] else "Mission Failure"
        result.update(outcome=outcome, reason=reason)
    return result