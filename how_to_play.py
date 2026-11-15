
from pathlib import Path
import base64
import html
from mimetypes import guess_type

import streamlit as st


ASSETS = Path(__file__).resolve().parent / "assets"


def image_url(filename):
    path = ASSETS / filename

    if not path.is_file():
        return ""

    encoded = base64.b64encode(path.read_bytes()).decode("utf-8")
    mime, _ = guess_type(path)
    return f"data:{mime or 'image/png'};base64,{encoded}"


def image_html(filename, alt):
    source = image_url(filename)

    if not source:
        return '<div class="help-image-missing">IMAGE COMING SOON</div>'

    return (
        f'<img src="{source}" '
        f'alt="{html.escape(alt, quote=True)}" '
        f'class="help-card-image">'
    )


def go_to(page):
    st.session_state.page = page
    st.rerun()


def instruction_card(number, title, description, filename):
    picture = image_html(filename, title)

    st.html(
        f"""
        <div class="help-card">
            <div class="help-card-art">
                {picture}
            </div>

            <div class="help-card-content">
                <div class="help-card-heading">
                    <span class="help-number">{number}</span>
                    <h2>{title}</h2>
                </div>

                <p>{description}</p>
            </div>
        </div>
        """
    )


def show():
    background = image_url("howtoplay_bg.png")

    if background:
        st.html(
            f"""
            <style>
                .stApp {{
                    background-image: url("{background}") !important;
                    background-position: center center !important;
                    background-size: cover !important;
                    background-repeat: no-repeat !important;
                }}
            </style>
            """
        )
    else:
        st.html(
            """
            <style>
                .stApp {
                    background-image: none !important;
                    background-color: #031427 !important;
                }
            </style>
            """
        )

    with st.container(key="help_page"):

        with st.container(key="help_header"):
            logo_col, title_col, home_col = st.columns(
                [1.65, 2.6, 0.8],
                gap="medium",
                vertical_alignment="center",
            )

            with logo_col:
                logo = image_url("orbitwatch_logo.png")

                if logo:
                    logo_markup = (
                        f'<img src="{logo}" class="help-logo-image">'
                    )
                else:
                    logo_markup = '<div class="help-logo-fallback">🛰</div>'

                st.html(
                    f"""
                    <div class="help-brand">
                        {logo_markup}
                        <div class="help-brand-text">
                            <strong>ORBITWATCH</strong>
                            <span>MISSION CARBON</span>
                        </div>
                    </div>
                    """
                )

            with title_col:
                st.html(
                    """
                    <div class="help-page-title">
                        <span>MISSION CONTROL / HELP CENTER</span>
                        <h1>HOW TO PLAY</h1>
                    </div>
                    """
                )

            with home_col:
                if st.button(
                    "⌂  HOME",
                    key="help_home_top",
                    use_container_width=True,
                ):
                    go_to("main")

        st.html(
            """
            <div class="help-welcome">
                <strong>Welcome, Mission Commander!</strong>
                Learn how to operate your satellite and
                complete your mission.
            </div>
            """
        )

        with st.container(key="help_cards"):
            first, second = st.columns(2, gap="medium")

            with first:
                instruction_card(
                    "01",
                    "DESIGN YOUR SATELLITE",
                    "Choose your scientific instruments, "
                    "solar panels and communication antenna. "
                    "Stay within your mission budget.",
                    "satellite_design.webp",
                )

            with second:
                instruction_card(
                    "02",
                    "EXPLORE EARTH",
                    "Choose locations to investigate, "
                    "including cities, forests and "
                    "industrial regions.",
                    "earth_explore.jpg",
                )

            third, fourth = st.columns(2, gap="medium")

            with third:
                instruction_card(
                    "03",
                    "MANAGE YOUR RESOURCES",
                    "Monitor your electricity, data "
                    "capacity, communication and remaining "
                    "mission time. Make smart decisions "
                    "when unexpected events happen.",
                    "resources.png",
                )

            with fourth:
                instruction_card(
                    "04",
                    "ANALYZE YOUR RESULTS",
                    "Analyze the measurements collected "
                    "by your satellite, discover patterns "
                    "and receive your final mission report.",
                    "data_analysis.png",
                )

        st.html(
            """
            <div class="help-objective">
                <div class="help-target">◎</div>
                <div class="help-objective-title">
                    MISSION OBJECTIVE
                </div>
                <p>
                    Collect valuable scientific data while
                    keeping your satellite operational and
                    completing your mission successfully.
                </p>
            </div>
            """
        )

        with st.container(key="help_bottom_buttons"):
            left_space, back_col, start_col, right_space = (
                st.columns([1, 1.35, 2.1, 1], gap="large")
            )

            with back_col:
                if st.button(
                    "←  BACK TO HOME",
                    key="help_back_home",
                    use_container_width=True,
                ):
                    go_to("main")

            with start_col:
                if st.button(
                    "START MISSION  →",
                    key="help_start_mission",
                    use_container_width=True,
                ):
                    go_to("mission_setup")
