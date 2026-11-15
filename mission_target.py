from html import escape
from math import isfinite
from pathlib import Path

import streamlit as st

from mission_setup import actions, art, go, heading, rail


# Coordinates are representative gameplay targets. Observation data can be
# associated with a saved target later, separately from this catalog.
REGIONS = {
    "urban": ("Urban Area", "▥", "High population and transport activity.",
              "Prague, Czechia · Central Europe", 50.0755, 14.4378, "Urban atmospheric CO₂ patterns"),
    "forest": ("Forest", "♠", "Monitor atmospheric CO₂ over forest ecosystems.",
               "Amazon Basin, Brazil", -3.1190, -60.0217, "Vegetation and carbon-cycle patterns"),
    "industrial": ("Industrial Region", "⚒", "Investigate atmospheric CO₂ near industrial activity.",
                   "Ruhr Region, Germany", 51.47, 7.12, "Industrial areas and atmospheric concentrations"),
    "agricultural": ("Agricultural Area", "⚘", "Study atmospheric CO₂ patterns in agricultural landscapes.",
                     "Great Plains, USA", 39.0, -100.0, "Agriculture and land-use relationships"),
    "polar": ("Polar Region", "❄", "Investigate high-latitude atmospheric conditions.",
              "Svalbard, Norwegian Arctic", 78.22, 15.65, "Polar atmospheric CO₂ patterns"),
}
MODES = ("PREDEFINED REGIONS", "CUSTOM AREA")
GLOBE = st.components.v2.component(
    "orbitwatch.globe",
    html='<div class="globe"><canvas width="380" height="380" aria-label="Earth globe"></canvas><div class="pins"></div></div>',
    css="""
        .globe{position:relative;max-width:560px;margin:auto;aspect-ratio:1;overflow:hidden}
        canvas,.pins{position:absolute;inset:0;width:100%;height:100%}
        canvas{cursor:grab;touch-action:none}
        canvas:active{cursor:grabbing}
        .pins{pointer-events:none}
        button{position:absolute;pointer-events:auto;transform:translate(-50%,-50%);border:1px solid #49e8ff;
               border-radius:50%;width:28px;height:28px;font:700 16px/1 system-ui,sans-serif;background:#002739;color:#9df7ff;cursor:pointer;
               padding:0;box-shadow:0 0 10px #03dffa}
        button[aria-pressed=true]{background:#63efff;color:#001722;z-index:1;outline:2px solid #b5faff}
        button[hidden]{display:none}
        button:hover,button:focus-visible{z-index:2;background:#fff;color:#001722}
    """,
    js=Path(__file__).with_name("mission_globe.js").read_text(encoding="utf-8"),
)


def region(key):
    st.session_state.selected_region = key
    st.session_state.target_mode = MODES[0]


def pick_marker():
    key = st.session_state["ow_globe"].marker
    if key in REGIONS:
        region(key)


def valid(lat, lon):
    return isfinite(lat) and isfinite(lon) and -90 <= lat <= 90 and -180 <= lon <= 180


def current():
    s = st.session_state
    if s.target_mode == MODES[1]:
        if "custom_target_name" not in s:
            return None
        return dict(category="custom", name=s.custom_target_name or "Custom Area",
                    lat=s.custom_latitude, lon=s.custom_longitude)
    name, _, _, _, lat, lon, _ = REGIONS[s.selected_region]
    return dict(category=s.selected_region, name=name, lat=lat, lon=lon)



ORBITS = {"LEO": "Low Earth Orbit", "SSO": "Sun-Synchronous Orbit"}
DURATIONS = (3, 7, 14, 21, 30)
COPY = st.components.v2.component(
    "orbitwatch.coordinates",
    html='<button type="button">Copy Coordinates</button> <span role="status"></span>',
    css="button{background:#092335;color:#a4f6ff;border:1px solid #37778f;border-radius:6px;padding:6px;cursor:pointer}span{color:#a4f6ff;font:12px sans-serif}",
    js="""export default function({parentElement, data}) {
        const status = parentElement.querySelector('span');
        status.textContent = '';
        parentElement.querySelector('button').onclick = async () => {
            try {
                await navigator.clipboard.writeText(data.coordinates);
                status.textContent = 'Copied';
            } catch {
                status.textContent = 'Select the displayed coordinates to copy manually.';
            }
        };
    }""",
)


def saved_satellite():
    config = st.session_state.satellite_config
    return config if all(key in config for key in ("components", "specs", "total_cost", "budget")) else None


def estimate(config, duration, orbit):
    specs = config["specs"]
    coverage = min(100, specs["Coverage Area"] + (10 if orbit == "SSO" else 0))
    daily_gb = (1 + specs["Data Accuracy"] / 50) * (.75 + coverage / 100)
    # Gameplay conversion: one capacity point represents one GB of onboard storage.
    return round(duration * daily_gb, 1), specs["Data Capacity"], coverage


def save():
    s = st.session_state
    draft, config = current(), saved_satellite()
    settings = s.target_settings
    if not config or not draft or not valid(draft["lat"], draft["lon"]):
        return
    volume, capacity, _ = estimate(config, settings["duration"], settings["orbit"])
    if volume > capacity:
        return
    s.saved_target = dict(draft, **settings)
    s.mission_parameters = {**s.mission_parameters, **settings}
    s.mission_step = max(3, s.mission_step)
    go("mission_parameters")


def custom_form():
    s = st.session_state
    with st.form("ow_custom_form"):
        name = st.text_input("Target name (optional)", value=s.get("custom_target_name", ""), max_chars=60)
        lat = st.number_input("Latitude (−90° to 90°)", -90.0, 90.0, s.custom_latitude, step=.01, format="%.4f")
        lon = st.number_input("Longitude (−180° to 180°)", -180.0, 180.0, s.custom_longitude, step=.01, format="%.4f")
        if st.form_submit_button("Select Location", width="stretch"):
            if valid(lat, lon):
                s.custom_latitude, s.custom_longitude = lat, lon
                s.custom_target_name = name.strip()
                st.rerun()
            st.error("Enter coordinates within the displayed bounds.")


def summary(config):
    with st.container(key="ow_mission_summary"):
        st.html('<b>MISSION SUMMARY</b>')
        if not config:
            st.caption("Save a satellite before saving your target.")
            st.button("Build Satellite", on_click=go, args=("satellite_builder",), width="stretch")
            return
        from satellite_builder import PARTS
        body = PARTS["body"][1][config["components"]["body"]][0]
        scores = "".join(f"<div>{label}: {score}%</div>" for label, score in config["specs"].items())
        st.html(f"""<div>{body}</div>{scores}<hr><div>Budget: {config['budget']:,}</div>
            <div>Construction: {config['total_cost']:,}</div>
            <b class="ow-gold">Credits left: {config['budget'] - config['total_cost']:,}</b>""")


def configuration(draft, config):
    s = st.session_state
    coords, settings, estimates = st.columns([1.15, 1.6, 1.2])
    with coords, st.container(key="ow_coordinates"):
        st.html('<b>⌖ TARGET COORDINATES</b>')
        if draft:
            lat, lon = draft["lat"], draft["lon"]
            st.html(f'<div>Latitude {lat:.4f}°<br>Longitude {lon:.4f}°</div>')
            COPY(key="ow_copy", data={"coordinates": f"{lat:.4f}, {lon:.4f}"})
        else:
            st.caption("Select a custom location.")
    with settings, st.container(key="ow_target_config"):
        st.html('<b>▤ MISSION CONFIGURATION</b>')
        for field in ("duration", "orbit"):
            s.setdefault(f"ow_target_{field}", s.target_settings[field])
        first, second = st.columns([1, 1.5])
        duration = first.selectbox("Mission Duration", DURATIONS, format_func=lambda d: f"{d} days",
                                   key="ow_target_duration")
        orbit = second.selectbox("Orbit", tuple(ORBITS), format_func=lambda k: f"{ORBITS[k]} ({k})",
                                 key="ow_target_orbit")
        description = ("General low-altitude observation." if orbit == "LEO"
                       else "Passes at similar local solar times.")
        st.caption(f"Gameplay assumption · {description} Real mission feasibility is not evaluated.")
        s.target_settings = dict(duration=duration, orbit=orbit)
    with estimates, st.container(key="ow_target_estimate"):
        st.html('<b>▥ ESTIMATED DATA</b>')
        if not config:
            st.caption("Save a satellite to estimate collection and storage.")
            return False
        volume, capacity, coverage = estimate(config, duration, orbit)
        st.html(f'<div><b>{volume:.1f} GB</b> over {duration} days<br>Coverage {coverage}% · Storage {capacity} GB</div>')
        st.caption("Simulated gameplay estimates")
        if volume > capacity:
            st.warning("Onboard storage is too small. Shorten the mission or upgrade the satellite.")
            return False
        return True


def picture(name, css_class):
    try:
        return f'<img class="{css_class}" src="{art(name)}" alt="">'
    except FileNotFoundError:
        return f'<div class="{css_class} ow-image-placeholder" aria-hidden="true">◎</div>'



def target():
    s = st.session_state
    s.setdefault("target_settings", {"duration": s.mission_parameters.get("duration", 14),
                                     "orbit": s.mission_parameters.get("orbit", "LEO")})
    draft, config = current(), saved_satellite()
    key = draft["category"] if draft else None
    with st.container(key="ow_target_dashboard"):
        left, main = st.columns([1.15, 6.2], gap="medium")
        with left:
            completed = {i for i, done in enumerate((config is not None, s.saved_target is not None)) if done}
            rail(["Build Satellite", "Mission Target", "Mission Parameters", "Launch Mission",
                  "Analyze Data", "Mission Report"], 1, completed)
            summary(config)
        with main:
            heading("MISSION TARGET", "Choose the region you want to investigate and collect CO₂ data from.")
            globe, info, options = st.columns([2.45, 1.25, 2.45], gap="small")
            with globe:
                pins = [dict(id=k, icon=v[1], name=v[0], lat=v[4], lon=v[5]) for k, v in REGIONS.items()]
                if key == "custom":
                    pins.append(dict(id=key, icon="◎", name=draft["name"], lat=draft["lat"], lon=draft["lon"]))
                try:
                    texture = art("earth")
                except FileNotFoundError:
                    texture = None
                GLOBE(key="ow_globe", data=dict(pins=pins, selected=key, texture=texture), on_marker_change=pick_marker)
                st.html('<div class="ow-globe-help">↔ Drag to rotate · Scroll to zoom · Select a region marker</div>')
            with info:
                if not draft:
                    st.html('<article class="ow-info">Select a custom location to see its details.</article>')
                else:
                    custom = key == "custom"
                    location = "Player-selected point" if custom else REGIONS[key][3]
                    focus = "Atmospheric carbon patterns" if custom else REGIONS[key][6]
                    days = "14–21" if key in {"forest", "polar", "agricultural"} else "7–14"
                    st.html(f"""<article class="ow-info">{picture("target" if custom else key, "ow-info-art")}
                        <h3>{escape(draft['name'])}</h3><dl>
                        <dt>SAMPLE TARGET LOCATION</dt><dd>{location}<br>{draft['lat']:.4f}°, {draft['lon']:.4f}°</dd>
                        <dt>ATMOSPHERIC CO₂</dt><dd>CO₂ observation data not yet loaded.</dd>
                        <dt>RECOMMENDED DURATION</dt><dd>{days} days · gameplay</dd>
                        <dt>SCIENTIFIC FOCUS</dt><dd>{focus}</dd></dl></article>""")
            with options, st.container(key="ow_options"):
                for col, mode in zip(st.columns(2), MODES):
                    col.button(mode, type="primary" if mode == s.target_mode else "secondary",
                               width="stretch", on_click=s.__setitem__, args=("target_mode", mode))
                if s.target_mode == MODES[0]:
                    for k, (name, icon, desc, *_) in REGIONS.items():
                        with st.container(key=f"ow_region_{k}_{'active' if k == key else 'idle'}"):
                            pic, copy = st.columns([1, 2.85], gap="small")
                            pic.html(picture(k, "ow-thumb"))
                            with copy:
                                st.button(f"{icon}  {name}   {'✓' if k == key else '□'}", key=f"ow_region_pick_{k}",
                                          on_click=region, args=(k,), width="stretch")
                                st.html(f'<p class="ow-region-copy">{desc}</p>')
                else:
                    custom_form()
        can_save = configuration(draft, config)
        actions("← BACK", "mission_setup", "SAVE TARGET  →", save, not (can_save and draft))
