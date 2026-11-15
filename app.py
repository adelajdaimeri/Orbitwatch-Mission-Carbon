from pathlib import Path
import base64

import streamlit as st
import mission_setup as mission_ui
import how_to_play
import credits as credits_page

st.set_page_config(
    page_title="OrbitWatch | Mission Carbon",
    page_icon="🌍",
    layout="wide",
    initial_sidebar_state="collapsed",
)


BASE_DIR = Path(__file__).resolve().parent
ASSETS_DIR = BASE_DIR / "assets"


def load_styles():
    css = (BASE_DIR / "styles.css").read_text(encoding="utf-8")

    background_path = ASSETS_DIR / "earthback.png"

    if background_path.exists():
        image_data = base64.b64encode(
            background_path.read_bytes()
        ).decode("utf-8")

        css += f"""
        .stApp {{
            background-image: url("data:image/png;base64,{image_data}");
        }}
        """

    st.html(f"<style>{css}</style>")


def navigate(page):
    st.session_state.page = page
    st.rerun()


def feature_card(icon, title, description):
    st.html(
        f"""
        <div class="feature-card">
            <div class="feature-icon">{icon}</div>
            <div class="feature-content">
                <div class="feature-title">{title}</div>
                <div class="feature-description">{description}</div>
            </div>
        </div>
        """
    )


def main_menu():
    with st.container(key="main_menu"):

        left, right = st.columns([1, 1], gap="large")

        with left:
            st.html(
                """
                <div class="hero-content">
                    <div class="eyebrow">
                        EARTH OBSERVATION • SPACE MISSION SIMULATOR
                    </div>

                    <h1 class="game-title">ORBITWATCH</h1>

                    <div class="game-subtitle">
                        MISSION CARBON
                    </div>

                    <p class="game-description">
                        Design your satellite. Explore our planet.<br>
                        Discover the data.
                    </p>
                </div>
                """
            )

            with st.container(key="menu_buttons"):
                if st.button(
                    "▶  PLAY MISSION",
                    key="play_mission",
                    use_container_width=True,
                ):
                    navigate("mission_setup")

                col1, col2 = st.columns(2, gap="small")

                with col1:
                    if st.button(
                        "HOW TO PLAY",
                        key="how_to_play",
                        use_container_width=True,
                    ):
                        navigate("instructions")

                with col2:
                    if st.button(
                        "CREDITS",
                        key="credits",
                        use_container_width=True,
                    ):
                        navigate("credits")

        with right:
            st.empty()

        with st.container(key="features"):
            col1, col2, col3 = st.columns(3, gap="medium")

            with col1:
                feature_card(
                    "⌘",
                    "DESIGN YOUR SATELLITE",
                    "Build your own scientific spacecraft.",
                )

            with col2:
                feature_card(
                    "◎",
                    "OBSERVE EARTH",
                    "Explore different regions of our planet.",
                )

            with col3:
                feature_card(
                    "▥",
                    "ANALYZE DATA",
                    "Discover carbon dioxide patterns.",
                )

        st.html(
            """
            <div class="mission-footer">
                <div class="footer-heading">
                    MISSION CONTROL SYSTEMS ONLINE
                </div>
                <div class="footer-subtitle">
                    EDUCATIONAL SIMULATION • VERSION 1.0
                </div>
            </div>
            """
        )


def secondary_page(title, description):
    with st.container(key="secondary_page"):
        st.html(
            f"""
            <div class="secondary-heading">
                <div class="eyebrow">ORBITWATCH • MISSION CARBON</div>
                <h1>{title}</h1>
                <p>{description}</p>
            </div>
            """
        )

        if st.button("← BACK TO MAIN MENU", key="back_button"):
            navigate("main")


def instructions():
    secondary_page(
        "HOW TO PLAY",
        "Design a satellite, observe Earth, and analyze "
        "carbon dioxide patterns using NASA scientific data.",
    )


def credits():
    secondary_page(
        "CREDITS",
        "OrbitWatch: Mission Carbon — An educational "
        "Earth observation simulation.",
    )


def main():
    load_styles()

    if "page" not in st.session_state:
        st.session_state.page = "main"
    pages = {
        "main": main_menu,
        **dict.fromkeys(("mission_setup", "satellite_builder", "mission_target", "mission_parameters", "mission_run", "mission_analysis", "mission_report", "mission_settings"), mission_ui.show),
        "instructions": how_to_play.show,
        "credits": credits_page.show,
    }

    pages.get(st.session_state.page, main_menu)()


if __name__ == "__main__":
    main()
