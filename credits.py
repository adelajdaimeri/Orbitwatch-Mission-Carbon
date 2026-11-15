
from pathlib import Path
import base64
import html

import streamlit as st


ASSETS = Path(__file__).resolve().parent / "assets"

NASA_SOURCES = [
    ("NASA POWER Daily API", "Historical air temperature, relative humidity, wind speed and surface solar irradiance"),
]

TECHNOLOGIES = ["Python", "Streamlit", "HTML", "CSS", "JavaScript"]


def get_image(filename):
    path = ASSETS / filename

    if not path.is_file():
        return ""

    encoded = base64.b64encode(path.read_bytes()).decode("utf-8")
    return f"data:image/png;base64,{encoded}"


def navigate_home():
    st.session_state.page = "main"
    st.rerun()


def make_card(icon, title, content):
    st.html(
        f"""
        <div class="credit-panel">
            <div class="credit-panel-icon">{icon}</div>
            <div class="credit-panel-body">
                <h2>{title}</h2>
                {content}
            </div>
        </div>
        """
    )


def get_science_content():
    return "".join(
        f'<p><strong>{html.escape(name)}</strong>'
        f' — {html.escape(description)}</p>'
        for name, description in NASA_SOURCES
    )


def show():
    background = get_image("credits_bg.png")

    if background:
        st.html(
            f"""
            <style>
                .stApp {{
                    background-image: url("{background}") !important;
                    background-size: cover !important;
                    background-position: center !important;
                    background-repeat: no-repeat !important;
                }}
            </style>
            """
        )

    with st.container(key="credit_page"):

        with st.container(key="credit_header"):
            brand, heading, home = st.columns(
                [1.5, 2.4, 0.7],
                gap="medium",
                vertical_alignment="center",
            )

            with brand:
                logo = get_image("orbitwatch_logo.png")

                logo_html = (
                    f'<img class="credit-logo" src="{logo}">'
                    if logo
                    else '<div class="credit-logo-fallback">🛰</div>'
                )

                st.html(
                    f"""
                    <div class="credit-brand">
                        {logo_html}
                        <div>
                            <div class="credit-brand-name">
                                ORBITWATCH
                            </div>
                            <div class="credit-brand-subtitle">
                                MISSION CARBON
                            </div>
                        </div>
                    </div>
                    """
                )

            with heading:
                st.html(
                    """
                    <div class="credit-heading">
                        <span>
                            MISSION CONTROL / PROJECT INFORMATION
                        </span>
                        <h1>MISSION CREDITS</h1>
                    </div>
                    """
                )

            with home:
                if st.button(
                    "⌂ HOME",
                    key="credit_top_home",
                    use_container_width=True,
                ):
                    navigate_home()

        st.html(
            """
            <div class="credit-intro">
                <div class="credit-orbit-symbol">🌍</div>
                <h2>ORBITWATCH</h2>
                <h3>MISSION CARBON</h3>
                <p>
                    An interactive Earth observation experience
                    combining satellite mission simulation,
                    environmental science and real NASA data.
                </p>
            </div>
            """
        )

        with st.container(key="credit_grid"):
            left, right = st.columns(2, gap="medium")

            with left:
                make_card(
                    "♟",
                    "DEVELOPER",
                    '<strong class="credit-accent">Adelajda Imeri</strong>',
                )

            with right:
                make_card(
                    "▤",
                    "SCIENTIFIC DATA",
                    get_science_content(),
                )

            left2, right2 = st.columns(2, gap="medium")

            with left2:
                make_card(
                    "▧",
                    "VISUAL ASSETS",
                    """
                    <p>
                        <strong>NASA Imagery</strong> —
                        Earth and space imagery where used.
                    </p>
                    <p>
                        <strong>Original Artwork</strong> —
                        Custom interface designs.
                    </p>
                    """,
                )

            with right2:
                tags = "".join(
                    f'<span class="credit-tech">'
                    f'{html.escape(tech)}</span>'
                    for tech in TECHNOLOGIES
                )

                make_card(
                    "&lt;/&gt;",
                    "TECHNOLOGIES",
                    f'<div class="credit-tech-list">{tags}</div>',
                )

        st.html(
            """
            <div class="credit-mission">
                <div class="credit-target">◎</div>
                <strong>OUR MISSION</strong>
                <p>
                    Inspire curiosity about our planet through
                    interactive space exploration, satellite
                    engineering and carbon dioxide science.
                </p>
            </div>
            """
        )

        with st.container(key="credit_footer"):
            back, information = st.columns(
                [1, 2],
                gap="large",
                vertical_alignment="center",
            )

            with back:
                if st.button(
                    "← BACK TO MAIN MENU",
                    key="credit_back_home",
                    use_container_width=True,
                ):
                    navigate_home()

            with information:
                st.html(
                    """
                    <div class="credit-footer-info">
                        <small>
                            ORBITWATCH • VERSION 1.0
                        </small>
                    </div>
                    """
                )
