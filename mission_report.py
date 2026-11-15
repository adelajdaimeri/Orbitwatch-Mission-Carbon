import json
from datetime import date, timedelta
from time import sleep

import plotly.graph_objects as plot
import streamlit as st

import mission_archive as archive
from data_investigation import chart, observations, region_map, report_findings, practice_view, notebook_report
from mission_setup import go, heading
from mission_target import picture
from mission_rules import PACKET_GB, REWARD_PER_PACKET, SUCCESS_BONUS


def new_mission():
    s = st.session_state
    active = s.get("active_mission")
    if active and not active["outcome"]:
        return
    if active:
        archive.save(active)
    for key in list(s.keys()):
        if key.startswith(("satellite_", "ow_", "lab_", "mc_")) or key in {
            "active_mission", "mission_step", "selected_setup_card", "saved_target", "selected_region",
            "target_mode", "custom_latitude", "custom_longitude", "custom_target_name",
            "mission_parameters", "target_settings", "parameter_draft", "power_result", "outlook_day",
        }:
            del s[key]
    go("mission_setup")


def finalize_review(mission):
    state = mission.setdefault("analysis", {})
    state.setdefault("score", 0)
    state["finalized"] = True
    archive.save(mission)


def scientific_data(mission):
    config = mission["config"]
    env = config.get("environment") or mission.get("analysis_environment")
    return observations({**config, "environment": env}), env


def open_report():
    st.session_state.report_history_open = False


def page():
    active = st.session_state.get("active_mission")
    if active and active["outcome"]:
        archive.save(active)
    with st.container(key="report_dashboard"):
        heading("MISSION REPORT & LOGS", "Review your mission results, transmit scientific data to Earth, and explore your complete mission history.")
        st.caption(f"◈ {archive.balance():,} mission credits")
        left, center, right = st.columns([1, 3, 1.13], gap="small")
        with left, st.container(border=True):
            st.markdown("**◷ MISSION LOGS**")
            records = archive.history()
            query = st.text_input("Search targets").casefold()
            with st.expander("Filters"):
                outcome = st.selectbox("Outcome", ["All", "Mission Success", "Partial Success", "Mission Failure"])
                status = st.selectbox("Transmission", ["All", "Transmitted", "Pending"])
                sort = st.selectbox("Sort", ["Newest", "Highest score", "Credits earned"])
            records = [r for r in records if query in r["name"].casefold()
                       and (outcome == "All" or outcome == r["outcome"])
                       and (status == "All" or bool(r["transmitted"]) == (status == "Transmitted"))]
            field = {"Newest": "number", "Highest score": "score", "Credits earned": "reward"}[sort]
            records.sort(key=lambda r: r[field], reverse=True)
            if records:
                labels = {r["id"]: f"#{r['number']:03d} · {r['name']} · {r['outcome']} · {r['score']}/100" for r in records}
                with st.container(height=300, border=False):
                    selected = st.radio("Saved missions", list(labels), format_func=labels.get, key="report_selected", on_change=open_report)
            else:
                selected = None
                st.caption("No matching completed missions.")
            st.button("＋ New Mission", on_click=new_mission, disabled=bool(active and not active["outcome"]), width="stretch")
        if not selected or st.session_state.get("report_history_open", False):
            with center:
                st.info("Select a saved mission to open its report." if records else "Complete a mission to generate its report.")
                if records:
                    st.button("Open selected report", on_click=open_report)
            return
        report = archive.load(selected)
        mission = report["snapshot"]
        config = mission["config"]
        state = mission.get("analysis", {})
        data, env = scientific_data(mission)
        current = bool(active and active.get("id") == selected)
        with center:
            with st.container(border=True):
                image, title = st.columns([.8, 3])
                title.caption(f"MISSION REPORT — #{report['number']:03d} · {report['created'][:10]} UTC")
                title.subheader(report["name"])
                target = config["target"]
                image.html(picture(target.get("category", "target"), "report-thumb"))
                title.write(f"{target['lat']:.4f}°, {target['lon']:.4f}° · {config['duration']} days")
                if config.get("start"):
                    start = date.fromisoformat(config["start"])
                    title.caption(f"Historical window: {start} to {start + timedelta(days=config['duration']-1)} UTC")
                title.caption(" · ".join(config.get("collection", [])))
            overview, findings, performance, evidence = st.tabs(["Mission Overview", "Scientific Findings", "Performance", "Data & Evidence"])
            with overview:
                cols = st.columns(3)
                cols[0].metric("Mission outcome", mission["outcome"])
                cols[1].metric("Overall score", f"{report['score']} / 100")
                cols[2].metric("Report credits earned", f"{report['reward']:,} cr")
                st.caption("Score weights: packet objective 65%, remaining power 15%, investigation 20%.")
                st.write(mission["reason"])
                st.progress(archive.objective(mission), text=f"{mission['transmitted']} / {mission['resources']['goal']} packets transmitted")
                if len(data):
                    st.dataframe(data.groupby(["Variable", "Units"]).Value.agg(["mean", "count"]))
                else:
                    st.info("No scientific environmental measurements are archived.")
                st.caption("OCO-2 measurements are unavailable in the current retrieval pipeline.")
            with findings:
                if config.get("co2_scenario"):
                    practice_view(config, prefix=f"report_co2_{selected}")
                    if state.get("co2_investigation"):
                        notebook_report(state["co2_investigation"])
                    else:
                        st.caption("CO₂ investigation not submitted.")
                    for item in state.get("co2_comparisons", []):
                        st.write(item["label"], item["note"])
                else:
                    region_map(target)
                if len(data):
                    variable = st.selectbox("Historical NASA POWER variable", data.Variable.unique())
                    chart(data[data.Variable == variable], "Scatter", key=f"report:{selected}:findings:context")
                    st.link_button("NASA POWER request", env["source"])
                st.caption("Historical environmental context is independent of simulated scans and packet transmissions.")
                if state.get("conclusion"):
                    st.write(state["conclusion"]["answer"])
                st.caption("Mission insights: environmental context cannot establish regional XCO2.")
            with performance:
                events = mission.get("events", [])
                stats = {"Turns completed": mission["day"],
                         "Scans attempted": sum(e["action"] == "scan" for e in events),
                         "Scans yielding packets": sum(e["action"] == "scan" and e["packets"] > 0 for e in events),
                         "Packets collected": sum(e["packets"] for e in events if e["action"] == "scan"),
                         "Transmitted data (GB)": mission["transmitted"] * PACKET_GB,
                         "Energy spent": sum(max(0, -e["power_change"]) for e in events),
                         "Orbit adjustments": sum(e["action"] == "adjust" for e in events)}
                st.dataframe([{"Metric": key, "Value": value} for key, value in stats.items()], hide_index=True)
                if events:
                    fig = plot.Figure(plot.Bar(x=[e["day"] for e in events], y=[e["power_change"] for e in events]))
                    fig.update_layout(template="plotly_dark", xaxis_title="Mission day", yaxis_title="Energy change · simulated", height=220)
                    st.plotly_chart(fig, key=f"report:{selected}:performance:energy")
                    st.dataframe(events, hide_index=True)
            with evidence:
                attempts = state.get("power_challenges", {}).get("attempts", [])
                st.write("Completed scientific challenges", len(attempts) or len(state.get("answers", [])))
                for attempt in attempts:
                    with st.expander(attempt["challenge"]):
                        st.write(attempt["answer"])
                        st.write(f"{attempt['points']} points")
                        st.caption(attempt["explanation"])
                report_findings(mission, mission_id=selected, section="evidence")
                if len(data):
                    st.download_button("Download NASA POWER context CSV", data.to_csv(index=False), "power-context.csv")
                export = dict(report, snapshot={key: value for key, value in mission.items() if key != "co2_buffer"})
                st.download_button("Download mission report JSON", json.dumps(export, indent=2, default=str), "mission-report.json")
        with right:
            with st.container(border=True):
                st.markdown("**⌁ DATA TRANSMISSION**")
                st.caption("Send the final report to the simulated Earth ground station.")
                if report["transmitted"]:
                    st.success("TRANSMITTED ✓")
                    st.caption(report["transmitted"])
                    st.caption(f"Receipt {report['id']} · {report['reward']:,} cr awarded")
                elif not state.get("finalized"):
                    if current:
                        st.button("Data Analysis", on_click=go, args=("mission_analysis",), width="stretch")
                    if st.button("Finalize with available evidence", width="stretch"):
                        finalize_review(active if current else mission)
                        st.rerun()
                elif st.button("TRANSMIT TO EARTH", type="primary", width="stretch"):
                    progress = st.progress(0)
                    for percent, label in [(25, "Preparing archive"), (55, "Connecting to simulated ground station")]:
                        progress.progress(percent, text=label)
                        sleep(.16)
                    try:
                        archive.transmit(selected)
                    except (KeyError, ValueError) as error:
                        st.error(f"Transmission could not be saved. Retry: {error}")
                    else:
                        progress.progress(100, text="Receipt archived")
                        sleep(.16)
                        st.rerun()
                st.caption(f"{'✓' if state.get('finalized') else '○'} Review finalized · ✓ Report archived")
            with st.container(border=True):
                st.markdown("**◈ MISSION REWARDS**")
                for label, amount in archive.rewards(mission).items():
                    st.write(f"{label} · +{amount:,} cr")
                st.metric("Claimed" if report["transmitted"] else "Pending transmission",
                          f"{report['reward'] if report['transmitted'] else sum(archive.rewards(mission).values()):,} cr")
                st.caption(f"Mission Control already paid {mission['transmitted'] * REWARD_PER_PACKET + (SUCCESS_BONUS if mission['outcome'] == 'Mission Success' else 0):,} cr gross.")
            with st.container(border=True):
                st.markdown("**→ NEXT STEPS**")
                st.button("Start New Mission", on_click=new_mission, disabled=bool(active and not active["outcome"]), width="stretch")
                if st.button("Return to Mission Logs", width="stretch"):
                    st.session_state["report_history_open"] = True
                    st.rerun()
        if len(records) > 1:
            with st.expander("Compare missions", expanded=False):
                other = st.selectbox("Compare with", [r["id"] for r in records if r["id"] != selected], format_func=labels.get)
                compare = [report, archive.load(other)]
                st.dataframe([dict(Mission=x["name"], Score=x["score"], Credits=x["reward"],
                                   Packets=x["snapshot"]["transmitted"],
                                   Analysis=x["snapshot"].get("analysis", {}).get("score", 0),
                                   Objective=f"{archive.objective(x['snapshot']):.0%}") for x in compare], hide_index=True)
                st.caption("Compares gameplay results. Scientific measurements require comparable sampling and units.")