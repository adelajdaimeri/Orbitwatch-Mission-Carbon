"""Mission history and credits belonging to the current Streamlit session."""
import os
from copy import deepcopy
from datetime import datetime, timezone
from uuid import uuid4

import streamlit as st

STARTING_CREDITS = 10_000


def _archive():
    if "_player_archive" not in st.session_state:
        # Local preview only. Never enable this environment flag on a public server.
        local = (os.environ.get("ORBITWATCH_LOCAL_PREVIEW") == "1"
                 and st.get_option("server.address") in {"localhost", "127.0.0.1", "::1"})
        st.session_state["_player_archive"] = {"reports": {}, "initial": 50_000 if local else STARTING_CREDITS}
    return st.session_state["_player_archive"]


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def balance():
    player = _archive()
    return player["initial"] + sum(
        report["credit_delta"] + report["reward"] for report in player["reports"].values()
    )


def objective(mission):
    return min(1, mission["transmitted"] / max(1, mission["resources"]["goal"]))


def score(mission):
    resources = mission["resources"]
    result = 65 * objective(mission) + 15 * mission["energy"] / max(1, resources["power"])
    return round(max(0, min(100, result + .2 * mission.get("analysis", {}).get("score", 0))))


def rewards(mission):
    analysis = mission.get("analysis", {}).get("score", 0)
    base = {"Mission Success": 500, "Partial Success": 350, "Mission Failure": 200}
    return {"Completion": base.get(mission["outcome"], 200),
            "Analysis": min(350, max(0, (analysis // 10 - 4) * 70)),
            "Packet objective": round(180 * objective(mission))}


def save(mission):
    if not mission.get("outcome"):
        return
    player = _archive()
    reports = player["reports"]
    mission_id = mission.setdefault("id", str(uuid4()))
    previous = reports.get(mission_id)
    if previous and previous["transmitted"]:
        return
    if previous is None:
        config = mission["config"]
        budget = config.get("satellite", {}).get("budget", player["initial"])
        previous = dict(id=mission_id, number=len(reports) + 1, name=config["target"]["name"],
                        outcome=mission["outcome"], created=now(), transmitted=None, reward=0,
                        version=1, credit_delta=mission["credits"] - budget)
    reports[mission_id] = dict(previous, score=score(mission), snapshot=deepcopy(mission))


def _metadata(report):
    return {key: value for key, value in report.items() if key not in {"snapshot", "credit_delta"}}


def history():
    return [_metadata(report) for report in reversed(_archive()["reports"].values())]


def load(mission_id):
    report = _archive()["reports"][mission_id]
    return dict(_metadata(report), snapshot=deepcopy(report["snapshot"]))


def transmit(mission_id):
    reports = _archive()["reports"]
    report = reports.get(mission_id)
    if not report or report["transmitted"]:
        return False
    mission = report["snapshot"]
    if not mission.get("outcome") or not mission.get("analysis", {}).get("finalized"):
        raise ValueError("Finalize the scientific review first.")
    reports[mission_id] = dict(report, transmitted=now(), reward=sum(rewards(mission).values()))
    return True