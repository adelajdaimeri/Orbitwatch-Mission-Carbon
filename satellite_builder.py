from base64 import b64encode
from functools import lru_cache
from io import BytesIO
from pathlib import Path

from PIL import Image
import streamlit as st

from mission_setup import go, heading, rail
from scientific_instruments import INSTRUMENTS, payload


BUDGET = 10_000
SIZE = (800, 360)
ASSETS = Path(__file__).parent / "assets" / "satellite"
STATS = ("Data Accuracy", "Data Capacity", "Power", "Coverage Area")
# Each tuple contains a name, price, stat bonuses (in STATS order), and description.
PARTS = {
    "solar_panels": ("☀ Solar Panels", {
        "basic": ("Basic Panels", 1000, (0, 0, 14, 0), "Compact arrays for a low-cost mission."),
        "standard": ("Standard Panels", 2500, (0, 0, 27, 0), "Balanced solar generation for routine observations."),
        "advanced": ("Advanced Panels", 4000, (0, 0, 42, 0), "Larger arrays support power-hungry instruments."),
        "high_efficiency": ("High-Efficiency Panels", 6000, (0, 0, 57, 0), "High-output cells deliver the most solar power."),
    }),
    "sensors": ("◉ Sensors", {
        "basic": ("Basic CO₂ Sensor", 900, (20, 0, 0, 8), "Entry-level instrument for broad atmospheric patterns."),
        "enhanced": ("Enhanced CO₂ Sensor", 2100, (35, 0, 0, 15), "Improved sensitivity and wider sampling."),
        "high_precision": ("High-Precision CO₂ Sensor", 3600, (54, 0, 0, 23), "Fine sampling for small concentration differences."),
    }),
    "communication": ("⌁ Communication", {
        "basic": ("Basic Antenna", 650, (0, 8, 0, 4), "A simple link for short science passes."),
        "advanced": ("Advanced Antenna", 1600, (0, 20, 0, 12), "A directional dish improves the downlink."),
        "high_bandwidth": ("High-Bandwidth Communication System", 2900, (0, 38, 0, 18), "A larger dish handles heavier data transfers."),
    }),
    "power": ("ϟ Power System", {
        "standard": ("Standard Battery", 600, (0, 0, 10, 0), "Stores power for short periods in Earth's shadow."),
        "extended": ("Extended Battery", 1450, (0, 0, 20, 0), "Keeps instruments running through longer eclipses."),
        "high_capacity": ("High-Capacity Battery", 2550, (0, 0, 32, 0), "Provides the largest reserve for demanding passes."),
    }),
    "body": ("⬡ Body", {
        "compact": ("Compact Body", 850, (0, 10, 0, 8), "A lightweight frame for a small payload."),
        "standard": ("Standard Body", 1850, (0, 21, 0, 16), "Adds room for electronics and data storage."),
        "advanced": ("Advanced Body", 3200, (7, 35, 0, 27), "A reinforced frame supports a larger payload."),
    }),
}
DEFAULT = dict(solar_panels="standard", communication="advanced", power="standard", body="standard")
LAYER_ORDER = ("solar_panels", "body", "communication", "sensors", "power")
LAYER_FILES = {
    (category, part): ASSETS / category / f"{part}.png"
    for category, (_, options) in PARTS.items() for part in options
}

LAYER_FILES.update({('instruments', key): ASSETS / 'instruments' / f'{key}.png' for key in INSTRUMENTS})


def totals(config, instruments=()):
    if set(config) - {'sensors'} != set(PARTS) - {'sensors'} or any(
            part not in PARTS[cat][1] for cat, part in config.items()):
        raise ValueError("Choose one valid component in each category.")
    selected = [PARTS[cat][1][part] for cat, part in config.items()]
    cost = sum(part[1] for part in selected) + sum(INSTRUMENTS[key].price for key in dict.fromkeys(instruments))
    scores = [min(100, base + sum(part[2][i] for part in selected))
              for i, base in enumerate((19, 12, 11, 13))]
    return cost, dict(zip(STATS, scores))


@lru_cache(maxsize=128)
def preview(part_ids, zoom, instruments=()):
    result = Image.new("RGBA", SIZE)
    layers = [(cat, part) for cat, part in zip(LAYER_ORDER, part_ids) if part]
    layers.extend(('instruments', key) for key in instruments)
    for cat, part in layers:
        with Image.open(LAYER_FILES[cat, part]) as layer:
            if layer.size != SIZE:
                raise ValueError(f"{layer.filename} must be {SIZE[0]} × {SIZE[1]} pixels.")
            result.alpha_composite(layer.convert("RGBA"))
    if zoom != 100:
        scaled = result.resize(tuple(round(n * zoom / 100) for n in SIZE), Image.Resampling.LANCZOS)
        result = Image.new("RGBA", SIZE)
        result.paste(scaled, tuple((n - m) // 2 for n, m in zip(SIZE, scaled.size)))
    buffer = BytesIO()
    result.save(buffer, format="PNG")
    return buffer.getvalue()


@lru_cache(maxsize=16)
def thumbnail(category, part):
    with Image.open(LAYER_FILES[category, part]) as image:
        image = image.convert("RGBA")
        image = image.crop(image.getbbox())
        image.thumbnail((160, 80), Image.Resampling.LANCZOS)
        buffer = BytesIO()
        image.save(buffer, format="PNG")
    return b64encode(buffer.getvalue()).decode()


def set_zoom():
    st.session_state.satellite_zoom = st.session_state.satellite_zoom_control


def reset_view():
    st.session_state.satellite_zoom = 100
    st.session_state.satellite_zoom_control = 100


def configuration_error(draft, instruments, budget):
    cost, specs = totals(draft, instruments)
    mass, limit, demand = payload(draft["body"], instruments)
    if cost > budget:
        return f"Insufficient mission credits ({cost - budget:,} over budget)."
    if mass > limit:
        return "Satellite mass capacity exceeded. Choose a larger body or remove instruments."
    if demand + 20 > specs["Power"] and instruments:
        return "Insufficient power for the installed instruments and a downlink."
    return ""


def toggle_instrument(key):
    s = st.session_state
    existing = s.satellite_instruments
    candidate = tuple(k for k in existing if k != key) if key in existing else (*existing, key)
    draft = dict(s.satellite_draft)
    if key == "co2" and key in candidate:
        draft.pop("sensors", None)
    s.satellite_warning = configuration_error(draft, candidate, s.satellite_config.get("budget", BUDGET))
    if not s.satellite_warning:
        s.satellite_draft = draft
        s.satellite_instruments = candidate


def instrument_shop():
    s = st.session_state
    for col, (key, part) in zip(st.columns(4), INSTRUMENTS.items()):
        installed = key in s.satellite_instruments
        status = "selected" if installed else "available"
        with col, st.container(key=f"sat_part_{status}_instrument_{key}"):
            st.html(f'<img class="sat-part-icon" src="data:image/png;base64,{thumbnail("instruments", key)}" alt="">')
            st.markdown(f"**{part.name}**")
            st.caption(part.purpose)
            st.caption(f"{part.collection} · {part.price:,} credits · {part.mass} kg · +{part.energy} energy/scan")
            st.button("✓ Installed · Remove" if installed else "Install", key=f"sat_inst_{key}",
                      on_click=toggle_instrument, args=(key,), width="stretch")


def select(category, part):
    s = st.session_state
    draft = dict(s.satellite_draft, **{category: part})
    s.satellite_detail = part
    s.satellite_warning = configuration_error(draft, s.satellite_instruments, s.satellite_config.get('budget', BUDGET))
    if s.satellite_warning:
        return
    s.satellite_draft = draft


def change_category(category):
    s = st.session_state
    s.satellite_category = category
    s.satellite_detail = s.satellite_draft.get(category)
    s.satellite_warning = ""


def save():
    s = st.session_state
    try:
        budget = s.satellite_config.get('budget', BUDGET)
        instruments = s.satellite_instruments
        cost, specs = totals(s.satellite_draft, instruments)
        error = configuration_error(s.satellite_draft, instruments, budget)
    except ValueError as error:
        s.satellite_warning = str(error)
        return
    if error:
        s.satellite_warning = error
        return
    s.satellite_config = dict(platform="Earth observation", components=dict(s.satellite_draft),
                              specs=specs, total_cost=cost, budget=budget, instruments=instruments)
    s.mission_step = max(2, s.mission_step)
    leave_builder()


def leave_builder():
    go(st.session_state.pop('satellite_return_page', 'mission_setup'))


def builder():
    s = st.session_state
    s.setdefault("satellite_draft", dict(s.satellite_config.get("components", DEFAULT)))
    s.setdefault('satellite_instruments', tuple(s.satellite_config.get('instruments', ())))
    s.setdefault("satellite_category", "solar_panels")
    s.setdefault("satellite_detail", s.satellite_draft.get(s.satellite_category))
    s.setdefault("satellite_warning", "")
    s.setdefault("satellite_zoom", 100)
    s.setdefault("satellite_zoom_control", s.satellite_zoom)
    draft, category = s.satellite_draft, s.satellite_category
    if category == 'sensors' and 'sensors' not in draft:
        category = 'instruments'
    budget = s.satellite_config.get('budget', BUDGET)
    cost, specs = totals(draft, s.satellite_instruments)
    mass, limit, demand = payload(draft['body'], s.satellite_instruments)
    with st.container(key="sat_builder"):
        left, stage, right = st.columns([1, 3.65, 1.85], gap="medium")
        with left:
            rail(["Build Satellite", "Choose Target", "Run Mission", "Analyze Data", "Mission Report"],
                 0, s.mission_step - 1)
        with stage:
            heading("BUILD SATELLITE", "Customize your satellite by selecting and upgrading its components.")
            with st.container(key="sat_preview"):
                st.image(preview(tuple(draft.get(cat) for cat in LAYER_ORDER), s.satellite_zoom, s.satellite_instruments), width="stretch")
            zoom, reset = st.columns([3, 1])
            zoom.slider("Preview zoom", 80, 125, step=5,
                        key="satellite_zoom_control", on_change=set_zoom)
            reset.button("↺ Reset View", on_click=reset_view, width="stretch")
        with right:
            st.html(f'<div class="sat-budget">◈ {budget - cost:,} credits left <small>of {budget:,} mission credits</small></div>')
            st.caption(f'Mass {mass}/{limit} kg · Scan power {12 + demand}/{specs["Power"]} units · Storage {specs["Data Capacity"]} GB (simulated)')
            bars = "".join(f'<div class="sat-stat"><span>{label}</span><meter min="0" max="100" value="{value}"></meter><b>{value}%</b></div>'
                           for label, value in specs.items())
            st.html(f'<section class="sat-specs"><h3>SATELLITE SPECS</h3><small>Simulated gameplay scores</small>{bars}'
                    f'<div class="sat-total">Total cost <b>◈ {cost:,}</b></div></section>')
        _, shop = st.columns([.45, 5.9])
        with shop, st.container(key="sat_shop"):
            tabs = [(key, title) for key, (title, _) in PARTS.items() if key in draft]
            tabs.append(('instruments', '◉ Scientific Instruments'))
            for tab, (key, title) in zip(st.columns(len(tabs)), tabs):
                tab.button(title, key=f"sat_tab_{key}", type="primary" if key == category else "secondary",
                           on_click=change_category, args=(key,), width="stretch")
            if category == 'instruments':
                instrument_shop()
            else:
                options = PARTS[category][1]
                cards = st.columns([1] * len(options) + [1.6], gap="small")
                for col, (key, (name, price, mods, _)) in zip(cards, options.items()):
                    selected = draft[category] == key
                    affordable = cost - options[draft[category]][1] + price <= budget
                    status = "selected" if selected else "available" if affordable else "locked"
                    bonus = " · ".join(f"+{value} {stat}" for stat, value in zip(STATS, mods) if value)
                    with col, st.container(key=f"sat_part_{status}_{category}_{key}"):
                        st.html(f'<img class="sat-part-icon" src="data:image/png;base64,{thumbnail(category, key)}" alt="">')
                        st.button(name, key=f"sat_pick_{category}_{key}", on_click=select,
                                  args=(category, key), width="stretch")
                        message = "✓ Selected" if selected else "Available" if affordable else "Over budget"
                        st.html(f'<div class="sat-part-meta">{bonus}<strong>◈ {price:,}</strong><small>{message}</small></div>')
                detail = s.satellite_detail
                name, price, mods, description = options[detail]
                bonuses = " · ".join(f"+{value} {stat}" for stat, value in zip(STATS, mods) if value)
                with cards[-1]:
                    st.html(f'<article class="sat-detail"><h3>{name}</h3><p>{description}</p>'
                            f'<p>{bonuses}</p><strong>◈ {price:,} credits</strong></article>')
            if s.satellite_warning:
                st.warning(s.satellite_warning)
        left, _, right = st.columns([1.4, 4, 1.65])
        left.button('← BACK', on_click=leave_builder, width='stretch')
        right.button('SAVE SATELLITE  →', type='primary', on_click=save, width='stretch')