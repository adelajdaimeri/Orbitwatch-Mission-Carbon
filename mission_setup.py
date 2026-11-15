from base64 import b64encode
from functools import lru_cache
from pathlib import Path

import streamlit as st


@lru_cache
def art(name):
    path = Path(__file__).parent / "assets" / f"mission-{name}.jpg"
    return "data:image/jpeg;base64," + b64encode(path.read_bytes()).decode()


def go(page):
    st.session_state.page = page


def init():
    from mission_archive import balance
    if "satellite_config" not in st.session_state:
        st.session_state.satellite_config = {"platform": "Earth observation", "budget": max(0, balance())}
    for key, value in {
        "mission_step": 1, "selected_setup_card": "SATELLITE",
        "selected_region": "urban", "target_mode": "PREDEFINED REGIONS",
        "custom_latitude": 48.86, "custom_longitude": 2.35,
        "saved_target": None, "satellite_config": {"platform": "Earth observation"},
        "mission_parameters": {},
    }.items():
        st.session_state.setdefault(key, value)


def header():
    page = st.session_state.page
    with st.container(key="ow_header"):
        cols = st.columns([2.6, 1.55, 1, 1.45, 1, .55])
        cols[0].html('<div class="ow-brand"><i>🛰</i><b>ORBITWATCH<small>MISSION CARBON</small></b></div>')
        for col, (label, route) in zip(cols[1:], [
            ("🚀 MISSION SETUP", "mission_setup"), ("◉ MISSION CONTROL" if page == "mission_run" else "◉ MISSION", "mission_run"),
            ("▥ DATA ANALYSIS", "mission_analysis"), ("▤ REPORT", "mission_report"),
            ("⚙", "mission_settings"),
        ]):
            active = page == route or (route == "mission_setup" and page in ("satellite_builder", "mission_target", "mission_parameters"))
            col.button(label, key=f"ow_nav_{route}", type="primary" if active else "secondary",
                       on_click=go, args=(route,), width="stretch", help="Settings" if label == "⚙" else None)


def rail(labels, active, completed):
    completed = range(completed) if isinstance(completed, int) else completed
    rows = []
    for i, label in enumerate(labels):
        cls = "current" if i == active else "done" if i in completed else ""
        mark = "✓" if cls == "done" else ""
        rows.append(f'<li class="{cls}"><i>{mark}</i>{label}</li>')
    title = "MISSION PROGRESS" if len(labels) >= 5 else "MISSION SETUP"
    st.html(f'<aside class="ow-rail"><b>{title}</b><ol>{"".join(rows)}</ol></aside>')


def heading(title, subtitle):
    st.html(f'<div class="ow-heading"><h1>{title}</h1><p>{subtitle}</p></div>')


def advance():
    go("mission_target")


def select_card(name, title):
    st.session_state.selected_setup_card = title
    if name == "satellite":
        go("satellite_builder")
    elif name == "target":
        go("mission_target")


def setup():
    left, right = st.columns([1, 5.35], gap="medium")
    with left:
        rail(["Build Satellite", "Choose Target", "Run Mission", "Analyze Data", "Mission Report"],
             st.session_state.mission_step - 1, st.session_state.mission_step - 1)
    with right:
        heading("MISSION SETUP", "Prepare your satellite, select your mission target and configure your systems.")
        cards = [
            ("satellite", "⚒", "SATELLITE", "Design and customize your Earth observation satellite."),
            ("target", "◎", "MISSION TARGET", "Choose the region you want to investigate."),
            ("parameters", "☷", "MISSION PARAMETERS", "Configure mission time, data collection and resources."),
        ]
        for col, (name, icon, title, desc) in zip(st.columns(3), cards):
            active = st.session_state.selected_setup_card == title
            with col, st.container(key=f"ow_card_{name}_{'active' if active else 'idle'}"):
                st.html(f'<img class="ow-card-art" src="{art(name)}" alt="">')
                st.button(f"{icon}  {title}   ›", key=f"ow_pick_{name}", width="stretch",
                          on_click=select_card, args=(name, title))
                st.html(f'<p class="ow-card-copy">{desc}</p>')
        detail = {
            "SATELLITE": "Open the builder to customize and save your satellite.",
            "MISSION TARGET": "Choose a predefined region or enter custom coordinates on the next screen.",
            "MISSION PARAMETERS": "Mission parameters unlock after you save a target.",
        }
        st.html(f'<p class="ow-detail">{detail[st.session_state.selected_setup_card]}</p>')
    actions("← MAIN MENU", "main", "CONTINUE  →", advance)


def actions(back_label, back, next_label=None, callback=None, disabled=False):
    with st.container(key="ow_actions"):
        left, _, right = st.columns([1.4, 4, 1.65])
        left.button(back_label, on_click=go, args=(back,), width="stretch")
        if next_label:
            right.button(next_label, type="primary", on_click=callback, width="stretch", disabled=disabled)


def show():
    from data_investigation import analysis
    from mission_report import page as report_page
    from mission_control import control
    from mission_parameters import parameters
    from mission_target import target
    from satellite_builder import builder
    init()
    page = st.session_state.page
    with st.container(key="orbitwatch"):
        if page == "mission_setup":
            st.html(f"""
                <style>
                    .stApp:has(.ow-setup-backdrop) {{
                        background: #030d19 !important;
                    }}
                </style>
                <span class="ow-setup-backdrop" hidden></span>
            """)
        else:
            st.html(f'<style>.st-key-orbitwatch {{ background: url("{art("deck")}") bottom center / 100% 70px no-repeat; }}</style>')
        if page != "mission_run":
            header()
        if page == "mission_setup":
            setup()
        elif page == "satellite_builder":
            builder()
        elif page == "mission_target":
            target()
        elif page == "mission_parameters":
            parameters()
        elif page == "mission_run":
            control()
        elif page == "mission_analysis":
            analysis()
        elif page == "mission_report":
            report_page()
        else:
            titles = {
                "mission_analysis": ("DATA ANALYSIS", "Analysis tools are coming later."),
                "mission_report": ("REPORT", "Mission reports are coming later."),
                "mission_settings": ("SETTINGS", "No mission settings are available in this build."),
            }
            heading(*titles[page])
            actions("← MISSION SETUP", "mission_setup")
