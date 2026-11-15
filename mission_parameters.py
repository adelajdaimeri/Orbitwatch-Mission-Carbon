import os
from datetime import date, timedelta
from statistics import mean

import streamlit as st

from mission_setup import actions, go, heading, rail
from mission_target import REGIONS, picture
from scientific_instruments import INSTRUMENTS, supported_collections
from mission_rules import DURATIONS, ORBITS, PACKET_GB, initialize, plan, readiness
from co2_practice import SOURCE as PRACTICE_SOURCE
from nasa_data import PARAMETER, WEATHER, power


SIMULATION = "Simulation only"
HISTORICAL = "Historical NASA POWER"


def upgrade():
    st.session_state.satellite_return_page = 'mission_parameters'
    st.session_state.satellite_category = 'instruments'
    go('satellite_builder')


def launch(target, settings, resources):
    s = st.session_state
    if s.get("active_mission"):
        go("mission_run")
        return
    if not settings['collection'] or not set(settings['collection']) <= supported_collections(s.satellite_config):
        return
    if readiness(resources)[0] == "Configuration Invalid":
        return
    s.mission_parameters = settings
    from copy import deepcopy
    from uuid import uuid4
    s.active_mission = initialize(dict(target=target, satellite=deepcopy(s.satellite_config), **settings), resources)
    s.active_mission["id"] = str(uuid4())
    s.mission_step = max(4, s.mission_step)
    go("mission_run")


def parameters():
    s = st.session_state
    satellite, target = s.satellite_config, s.saved_target
    left, main = st.columns([1, 5.6], gap="medium")
    with left:
        completed = {i for i, done in enumerate((bool(satellite.get("components")), bool(target))) if done}
        rail(["Build Satellite", "Mission Target", "Mission Parameters", "Launch Mission",
              "Analyze Data", "Mission Report"], 2, completed)
    with main, st.container(key="ow_parameters"):
        heading("MISSION PARAMETERS", "Configure data collection and operational settings.")
        if not target or not satellite.get("components"):
            st.warning("Save a satellite and a target before configuring the mission.")
            actions("← MISSION SETUP", "mission_setup")
            return
        if s.get("active_mission"):
            st.info("A mission is already initialized for this session.")
            actions("← BACK", "mission_target", "MISSION CONTROL →", lambda: go("mission_run"))
            return
        previous = {**s.mission_parameters, **s.get("parameter_draft", {})}
        balance = satellite["budget"] - satellite["total_cost"]
        st.html(f'<div class="ow-parameter-balance">◈ {balance:,} credits available</div>')
        science, operations, status = st.columns([1.22, 1.15, .9], gap="small")
        with science:
            with st.container(key="ow_param_target", border=True):
                st.html("<b>SELECTED TARGET</b>")
                category = target["category"]
                pic, info = st.columns([1, 1.25], gap="small")
                pic.html(picture(category if category in REGIONS else "target", "ow-parameter-art"))
                with info:
                    st.write(target["name"])
                    st.caption(REGIONS[category][3] if category in REGIONS else "Custom area")
                    st.caption(f"{target['lat']:.4f}°, {target['lon']:.4f}°")
                st.caption("CO₂ observation data not yet loaded.")
                st.button("Change Target", on_click=go, args=("mission_target",))
            with st.container(key="ow_param_collection", border=True):
                st.html("<b>DATA COLLECTION</b>")
                selected = []
                supported_types = supported_collections(satellite)
                for instrument in INSTRUMENTS.values():
                    label = instrument.collection
                    supported = label in supported_types
                    if not supported:
                        s[f'ow_collect_{label}'] = False
                    checked = st.checkbox(label, key=f"ow_collect_{label}", disabled=not supported,
                                   value=supported and label in previous.get("collection", supported_types),
                                   help=None if supported else f"Requires {instrument.name}.")
                    if supported and checked:
                        selected.append(label)
                    if supported:
                        st.caption(PRACTICE_SOURCE if label == 'Atmospheric CO₂' else 'Instrument installed — scientific dataset not currently available.')
                st.button('UPGRADE SATELLITE', on_click=upgrade, width='stretch')
        with operations:
            with st.container(key="ow_param_duration", border=True):
                duration = st.select_slider("Mission Duration", DURATIONS, value=previous.get("duration", 14),
                                            format_func=lambda days: f"{days} days", key="ow_param_days")
            with st.container(key="ow_param_orbit", border=True):
                orbit = st.radio("Orbit Settings", list(ORBITS), index=list(ORBITS).index(previous.get("orbit", "LEO")),
                                 format_func=ORBITS.get, key="ow_param_orbit_choice")
                st.caption("SSO is modeled as a low Earth orbit with more regular observation opportunities. MEO is unavailable for this instrument model.")
            with st.container(key="ow_param_environment", border=True):
                mode = st.radio("Environmental Conditions", (SIMULATION, HISTORICAL),
                                index=int(previous.get("mode") == HISTORICAL), key="ow_param_mode")
                start = None
                if mode == HISTORICAL:
                    start = st.date_input("Historical start (UTC)", value=date.fromisoformat(previous.get("start") or "2023-06-01"),
                                          min_value=date(2001, 1, 1), max_value=date.today() - timedelta(days=duration),
                                          key="ow_param_start")
        lookup = (target["lat"], target["lon"], start, duration)
        environment = None
        power_status = "Simulation only"
        power_detail = ""
        if start:
            power_status = "Not requested for this target and date range"
            with operations:
                if st.button("Load NASA POWER", width="stretch"):
                    try:
                        s.power_result = (lookup, power(*lookup), None)
                    except (OSError, ValueError, KeyError, TypeError) as error:
                        s.power_result = (lookup, None, f"NASA POWER request failed: {error}. Retry or select Simulation only.")
                result = s.get("power_result")
                if result and result[0] == lookup:
                    _, environment, error = result
                    if error:
                        power_status = "Request failed"
                        power_detail = error
                        st.error(error)
                if environment:
                    values = [value for value in environment["series"] if value is not None]
                    if values:
                        power_status = "Loaded"
                        st.metric("Mean surface solar irradiance", f"{mean(values):.2f} kWh/m²/day")
                    else:
                        power_status = "No usable surface irradiance returned"
                    for key, (label, unit, _) in WEATHER.items():
                        if key != PARAMETER:
                            readings = [v for v in environment.get("weather", {}).get(key, []) if v is not None]
                            if readings:
                                st.caption(f"Mean {label.lower()} · {mean(readings):.2f} {unit}")
                    st.caption(f"{len(values)}/{duration} days available. Surface irradiance is a gameplay proxy for reflected-light opportunities.")
                    st.link_button("NASA POWER response", environment["source"])
                else:
                    st.caption("Load data for this location and date range to launch in historical mode.")
        available = bool(environment and any(value is not None for value in environment["series"]))
        settings = dict(duration=duration, orbit=orbit, collection=selected, mode=mode,
                        start=start.isoformat() if start else None, environment=environment)
        s.parameter_draft = {k: v for k, v in settings.items() if k != "environment"}
        resources = plan(satellite, target, settings, environment)
        level, explanation = readiness(resources)
        if start and not available:
            level, explanation = "Configuration Invalid", f"Historical mode needs usable NASA POWER irradiance. {power_status}."
        elif not selected:
            level, explanation = "Configuration Invalid", "Select a compatible science instrument."
        with status, st.container(key="ow_param_readiness", border=True):
            st.html("<b>MISSION READINESS</b>")
            st.subheader(level)
            st.caption(explanation)
            st.write(f"Instrument compatibility · {', '.join(selected) if selected else 'No instrument selected'}")
            st.write(f"NASA POWER · {power_status}")
            if power_detail:
                st.caption(power_detail)
            if not start:
                st.write("NASA OCO-2 · Requires a historical mission window")
            elif not os.environ.get("EARTHDATA_TOKEN", "").strip():
                st.write("NASA OCO-2 · Earthdata token missing")
            else:
                st.write("NASA OCO-2 · Load historical soundings in Data Analysis after the mission")
            st.write(f"Objective · Transmit {resources['goal']} usable packets")
            st.caption("Outcome depends on power management, data availability and successful transmission before the deadline.")
        with st.container(key="ow_param_resources", border=True):
            st.html("<b>RESOURCE & MISSION ESTIMATE</b> <small>· SIMULATED GAMEPLAY</small>")
            cols = st.columns(6, gap="small")
            for col, (label, value) in zip(cols, [
                ("Satellite mass", f"{resources['mass']} kg"), ("Power capacity", f"{resources['power']} units"),
                ("Storage", f"{resources['storage']} GB"), ("Potential collection", f"{sum(resources['opportunities']) * PACKET_GB} GB"),
                ("Operating cost", f"{resources['operating_cost']:,} cr"), ("After operations", f"{balance - resources['operating_cost']:,} cr"),
            ]):
                col.metric(label, value)
        actions("← BACK", "mission_target", "▶ LAUNCH MISSION",
                lambda: launch(target, settings, resources), level == "Configuration Invalid")