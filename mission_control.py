from mission_rules import ADJUST_COST, ADJUST_ENERGY, POWER_DEPLETION, action_energy
from datetime import date, timedelta
from html import escape

import streamlit as st

from mission_rules import PACKET_GB, REWARD_PER_PACKET, SUCCESS_BONUS, TRANSMIT_COST, action_error, step
from mission_setup import art, go, heading
from co2_practice import SOURCE as PRACTICE_SOURCE
from mission_target import GLOBE, picture
from nasa_data import PARAMETER, WEATHER


ACTIONS = {
    "scan": ("◎", "Scan Region", "Collect data from the target area."),
    "transmit": ("⌁", "Transmit Data", "Send stored data to Earth."),
    "conserve": ("ϟ", "Conserve Power", "Skip a scan to recover energy."),
    "adjust": ("◌", "Adjust Orbit", "Improve future usable scans."),
}


def panel(title, content, variant=""):
    st.html(f'<section class="hud-panel {variant}"><h3>{title}</h3>{content}</section>')


def rows(values):
    return "".join(f'<div class="hud-row">{escape(value)}</div>' for value in values)


def bar(label, value, capacity, tone=""):
    percent = round(100 * value / max(capacity, 1))
    return (f'<div class="hud-meter {tone}"><span>{label}</span><b>{percent}% · {value}/{capacity}</b>'
            f'<progress value="{value}" max="{capacity}" aria-label="{label}"></progress></div>')


def execute(action, turn):
    mission = st.session_state.active_mission
    if mission["day"] == turn and not action_error(mission, action):
        result = step(mission, action)
        if result["outcome"]:
            from mission_archive import save
            save(result)
        st.session_state.active_mission = result


def header(mission):
    with st.container(key="hud_header"):
        brand, control, analysis, report, wallet, settings = st.columns([2.15, 1.65, 1.45, 1.5, 1, .35])
        brand.html('<div class="ow-brand"><i>◌</i><b>ORBITWATCH<small>MISSION CARBON</small></b></div>')
        for column, title, page in [
            (control, "✦ MISSION CONTROL", "mission_run"), (analysis, "▥ DATA ANALYSIS", "mission_analysis"),
            (report, "▤ MISSION REPORT", "mission_report"), (settings, "⚙", "mission_settings"),
        ]:
            column.button(title, key=f"ow_nav_{page}", on_click=go, args=(page,), width="stretch",
                          type="primary" if page == "mission_run" else "secondary")
        wallet.html(f'<div class="hud-wallet">◈ {mission["credits"]:,} cr</div>')


def timeline(turn, days, events, ended):
    icons = {"scan": "◎", "transmit": "↑", "adjust": "◌", "conserve": "ϟ"}
    completed = {event["day"]: icons[event["action"]] for event in events}
    nodes = []
    for day in range(1, days + 1):
        status = "past" if day <= turn else "current" if day == turn + 1 and not ended else ""
        nodes.append(f'<div class="{status}"><b>{completed.get(day, "·")}</b><small>{day}</small></div>')
    st.html(f'<div class="hud-timeline"><strong>Day {min(turn+1, days)} / {days}</strong>'
            f'<div class="hud-track">{"".join(nodes)}</div></div>')


def action_tiles(mission):
    r = mission["resources"]
    turn = mission["day"]
    selected = st.session_state.get("mc_selected", "scan")
    packets = min(mission["stored"], r.get("downlink", 6))
    recovery = min(r["power"] - mission["energy"], r.get("recovery", 18))
    costs = {"scan": f"ϟ −{r['scan_energy']}", "transmit": f"ϟ −{r['tx_energy']} · {packets} packets",
             "conserve": f"ϟ +{recovery}", "adjust": f"ϟ −{ADJUST_ENERGY} · −{ADJUST_COST} cr"}
    st.html('<div class="hud-action-title">CHOOSE ACTION</div>')
    with st.container(key="hud_actions"):
        for column, (key, (icon, title, description)) in zip(st.columns(4, gap="small"), ACTIONS.items()):
            with column, st.container(key=f"hud_tile_{key}"):
                st.html(f'<div class="hud-icon">{icon}</div>')
                st.button(title, key=f"mc_pick_{key}", width="stretch",
                          type="primary" if key == selected else "secondary",
                          on_click=st.session_state.__setitem__, args=("mc_selected", key))
                st.html(f'<div class="hud-action-copy">{description}<strong>{costs[key]}</strong></div>')
    notice = action_error(mission, selected)
    caption = notice or "Executing uses one mission day."
    if not notice and selected == "transmit":
        caption = f"Downlink fee {TRANSMIT_COST} cr · net +{packets * REWARD_PER_PACKET - TRANSMIT_COST} cr."
    hint, button = st.columns([1.5, 1])
    if not notice and action_energy(r, selected) >= mission["energy"]:
        hint.warning("Warning: This action will deplete your satellite’s power and end the mission.")
    else:
        hint.caption(caption)
    button.button("EXECUTE ACTION →", key=f"mc_execute_{turn}", width="stretch", type="primary",
                  on_click=execute, args=(selected, turn), disabled=bool(notice))


def control():
    mission = st.session_state.get("active_mission")
    if not mission:
        heading("MISSION CONTROL", "Configure and launch a mission first.")
        st.button("Mission Setup", on_click=go, args=("mission_setup",))
        return
    config, r = mission["config"], mission["resources"]
    target, turn = config["target"], mission["day"]
    days, stored, energy = r["days"], mission["stored"], mission["energy"]
    events = mission.get("events", [])
    ended = mission["outcome"]
    environment = config.get("environment")
    storage = stored * PACKET_GB
    low = energy * 5 < r["power"]
    full = storage * 5 >= r["storage"] * 4
    with st.container(key="hud"):
        header(mission)
        left, scene, right = st.columns([22, 53, 24], gap="small")
        with left:
            category = target["category"] if target["category"] != "custom" else "target"
            panel("MISSION OVERVIEW", f'<div class="hud-target">{picture(category, "hud-thumb")}'
                  f'<div><b>{escape(target["name"])}</b><br>{target["lat"]:.4f}°, {target["lon"]:.4f}°</div></div>'
                  f'<div class="hud-day">▦ Day {min(turn+1, days)} / {days}</div>'
                  + bar("Mission progress", turn, days))
            achieved = mission["transmitted"] >= r["goal"]
            panel("MISSION OBJECTIVES", rows(config.get("collection", []))
                  + bar("✓ Transmit packets" if achieved else "□ Transmit packets", mission["transmitted"], r["goal"]))
            panel("REWARDS <small>(SIMULATED)</small>",
                  rows([f"◈ Transmission · +{REWARD_PER_PACKET} cr / packet", f"✦ Mission success · +{SUCCESS_BONUS} cr"]))
        with scene:
            timeline(turn, days, events, ended)
            with st.container(key="hud_earth"):
                pin = dict(id="custom", icon="◎", name=target["name"], lat=target["lat"], lon=target["lon"])
                GLOBE(key="ow_mission_earth", data=dict(pins=[pin], selected="custom", texture=art("earth")))
            if ended == "Mission Failure" and mission["energy"] == 0:
                from mission_report import new_mission

                collected = sum(e["packets"] for e in events if e["action"] == "scan")
                panel("MISSION FAILED", "<strong>SATELLITE POWER DEPLETED</strong>" + rows([
                    "Your satellite has run out of energy and can no longer continue its mission. Careful energy management is essential for a successful Earth observation mission.",
                    f"Final mission day: {turn} / {days}", "Final satellite energy: 0",
                    f"Data collected: {collected * PACKET_GB} GB",
                    f"Data successfully transmitted: {mission['transmitted'] * PACKET_GB} GB",
                    f"Mission progress: {turn / days:.0%}", f"Reason for failure: {POWER_DEPLETION}",
                ]), "hud-risk critical")
                st.button("RESTART MISSION", on_click=new_mission, type="primary", width="stretch")
            elif ended:
                panel(escape(ended.upper()), rows([mission["reason"]]))
            else:
                action_tiles(mission)
        with right:
            status = "Critical" if low else "Caution" if full else "Nominal"
            panel(f'✦ SATELLITE STATUS <small class="hud-status {status.lower()}">{status}</small>',
                  bar("ϟ Power", energy, r["power"], "red" if low else "")
                  + bar("▱ Storage · GB", storage, r["storage"], "amber" if full else "")
                  + rows([f"⌁ Comm. link · {r.get('downlink', 6)} packets / turn"]))
            light = environment["series"][turn] if environment and turn < days else None
            panel("☁ ENVIRONMENT", rows(["Historical NASA POWER" if environment else "Simulated gameplay conditions",
                  f"Surface irradiance · {light:.2f} kWh/m²/day" if light is not None else "No measurement for this turn"]))
            latest = next((event for event in reversed(events) if event["action"] == "scan"), None)
            co2_status = (f"{PRACTICE_SOURCE} · {len(config['co2_transmitted'])} transmitted soundings"
                          if config.get("co2_scenario") else "CO₂ practice collection was not enabled.")
            panel("◉ LATEST CO₂ DATA", rows([co2_status,
                  latest["message"] if latest else "Awaiting first scan."]))
            with st.expander("View Details"):
                st.caption("Scan packets are simulated gameplay.")
                observation = latest.get("environment") if latest else None
                if observation and observation["irradiance"] is not None:
                    observed_date = date.fromisoformat(observation["start"]) + timedelta(days=observation["offset"])
                    st.write(f"{observed_date} · {observation['irradiance']:.2f} kWh/m²/day surface irradiance")
                if environment:
                    st.link_button("NASA POWER source", environment["source"])
        log, forecast, risks = st.columns(3, gap="small")
        with log:
            panel("▤ MISSION LOG", rows([f"Day {e['day']} · {e['message']}" for e in reversed(events)]
                                       or ["Mission launched. Operating costs paid."]), "hud-log")
        with forecast:
            outlook(mission)
        with risks:
            warnings = []
            if not ended:
                if low:
                    warnings.append("Low power. Consider conserving energy.")
                if full:
                    warnings.append("Storage is nearly full. Plan a downlink.")
                if not r["opportunities"][turn]:
                    warnings.append("No usable scan opportunity this turn.")
                if days - turn <= 2:
                    warnings.append("Deadline approaching. Reserve a downlink turn.")
            panel("⚠ MISSION RISKS", rows(warnings or ["No immediate risks."] if not ended else [mission["reason"]]),
                  "hud-risk critical" if warnings else "hud-risk")

def outlook(mission):
    turn, r = mission["day"], mission["resources"]
    indices = list(range(turn + 1, min(turn + 4, r["days"]))) if not mission["outcome"] else []
    st.html('<div class="hud-panel"><h3>▦ UPCOMING CONDITIONS</h3></div>')
    if not indices:
        st.caption("Mission complete." if mission["outcome"] else "No future mission days.")
        return
    config = mission["config"]
    environment = config.get("environment")
    st.caption("Historical NASA POWER · UTC" if environment else "Simulated gameplay conditions")
    selected = st.session_state.get("outlook_day")
    counts = {}
    for column, index in zip(st.columns(3, gap="small"), indices):
        count = r["opportunities"][index]
        count += int(bool(count and mission.get("adjusted")))
        counts[index] = count
        day = date.fromisoformat(environment["start"]) + timedelta(days=index) if environment else None
        label = f"☀ Day {index + 1}" if count else f"◇ Day {index + 1}"
        with column:
            st.button(label, key=f"outlook_day_{index}", width="stretch",
                      type="primary" if selected == (turn, index) else "secondary",
                      on_click=st.session_state.__setitem__, args=("outlook_day", (turn, index)))
            st.caption(f"{day} · " if day else "")
            st.caption(f"{count} simulated packets · Cloud cover unavailable")
    if not selected or selected[0] != turn or selected[1] not in indices:
        return
    index = selected[1]
    with st.container(border=True):
        st.markdown(f"**DAY {index + 1} · OBSERVATION OUTLOOK**")
        if environment:
            weather = environment.get("weather", {PARAMETER: environment["series"]})
            for key, (label, unit, _) in WEATHER.items():
                values = weather.get(key)
                value = values[index] if values else None
                st.write(f"{label}: {value:.2f} {unit}" if value is not None else f"{label}: unavailable")
            st.link_button("NASA POWER source", environment["source"])
        st.caption("Cloud cover and quality-filtered OCO-2 observations are unavailable. Vegetation and surface temperature datasets are unavailable.")
        active = ", ".join(config.get("collection", [])) or "None"
        count = counts[index]
        storage = count * PACKET_GB
        st.write(f"Active instruments: {active}")
        st.write(f"Simulated outlook: {count} packets · up to {storage} GB · {r['scan_energy']} scan power")
        if storage > r["storage"] - mission["stored"] * PACKET_GB:
            st.warning("Current free storage is below this estimate. Consider transmitting first.")
        elif mission["energy"] < r["scan_energy"]:
            st.warning("Current power is too low for a scan. Consider conserving power.")
        elif not count:
            st.info("No simulated scan opportunity on this day. Consider a downlink or power recovery.")
        elif count > r["opportunities"][turn] + int(bool(r["opportunities"][turn] and mission.get("adjusted"))):
            st.info("This day has more simulated opportunities than today. Consider saving power for it.")
