from html import escape
from math import isfinite
from datetime import date, timedelta
from statistics import mean, pstdev

import plotly.graph_objects as go_chart
import pydeck as pdk
import pandas as pd
import streamlit as st

from mission_setup import go, heading
from co2_practice import SOURCE as PRACTICE_SOURCE, VARIABLE as PRACTICE_VARIABLE, series as practice_series, usable
from graph_game import mission_series, play
from nasa_data import PARAMETER, WEATHER, power


TOOLS = ("CO₂ Investigation", "Build a Graph", "Compare Regions", "Detect Anomalies", "Submit Conclusion", "NASA OCO-2 Observations")
SOURCE = "https://power.larc.nasa.gov/docs/services/api/temporal/daily/"


def observations(config):
    env = config.get("environment")
    if not env:
        return pd.DataFrame(columns=["Date", "Variable", "Value", "Units", "Source"])
    start = date.fromisoformat(env["start"])
    weather = env.get("weather", {PARAMETER: env["series"]})
    return pd.DataFrame([
        (day, WEATHER[key][0], value, WEATHER[key][1], "NASA POWER")
        for key, values in weather.items() if key in WEATHER
        for day, value in zip(*mission_series(config,key)) if value is not None
    ], columns=["Date", "Variable", "Value", "Units", "Source"])


def chart(data, kind, *, key=None):
    unit = data.iloc[0]["Units"]
    variable = data.iloc[0]["Variable"]
    source = data.iloc[0]["Source"]
    if kind == "Histogram":
        trace = go_chart.Histogram(x=data.Value, marker_color="#39e7f6")
        x_title, y_title = f"{variable} ({unit})", "Count"
    else:
        values = dict(x=data.Date, y=data.Value, marker_color="#39e7f6",
                      hovertemplate=f"%{{x|%Y-%m-%d}} · %{{y:.2f}} {unit}<extra>{source}</extra>")
        trace = (go_chart.Bar(**values) if kind == "Bar" else
                 go_chart.Scatter(**values, mode="lines+markers" if kind == "Line" else "markers"))
        x_title, y_title = "Date (UTC)", f"{variable} ({unit})"
    fig = go_chart.Figure(trace)
    fig.update_layout(template="plotly_dark", height=245, margin=dict(l=8,r=8,t=12,b=8),
                      paper_bgcolor="#051b29", plot_bgcolor="#071f30", xaxis_title=x_title, yaxis_title=y_title)
    st.plotly_chart(fig, key=key, width="stretch", config={"scrollZoom": True})


def region_map(target):
    location = dict(lat=target["lat"], lon=target["lon"])
    layer = pdk.Layer("ScatterplotLayer", [location], get_position="[lon, lat]",
                      get_fill_color=[40, 231, 248, 220], radius_min_pixels=8,
                      get_line_color=[195, 254, 255], stroked=True, pickable=True)
    view = pdk.ViewState(latitude=max(-85,min(85,location["lat"])), longitude=location["lon"], zoom=4)
    st.pydeck_chart(pdk.Deck(layers=[layer], initial_view_state=view, map_provider="carto",
                            map_style="dark", tooltip={"text":"Mission target: {lat}°, {lon}°"}),
                    height=260)
    st.caption("● Mission target · Basemap © CARTO, © OpenStreetMap contributors")


def filtered(data, prefix):
    variable = st.selectbox("NASA POWER measurement", data["Variable"].unique(), key=f"{prefix}_variable")
    series = data[data.Variable == variable].sort_values("Date")
    dates = sorted(series.Date.unique())
    start, end = st.select_slider("Observation dates (UTC)", dates, value=(dates[0], dates[-1]),
                                  key=f"{prefix}_dates_{variable}") if len(dates) > 1 else (dates[0], dates[0])
    return series[series.Date.between(start, end)]


CHALLENGE_NAMES = ("Find the Peak", "Calculate the Change", "Interpret the Trend")
CHALLENGE_POINTS = (25, 25, 15)


def trend_answer(values, unit):
    # Require a meaningful endpoint change and agreement from at least two
    # thirds of consecutive available readings. Flat steps count against agreement.
    threshold = {"ppm": .5, "°C": 1.0, "%": 5.0, "m/s": .5, "kWh/m²/day": .5}[unit]
    steps = [b - a for a, b in zip(values, values[1:])]
    change = values[-1] - values[0]
    if change >= threshold and 3 * sum(step > 0 for step in steps) >= 2 * len(steps):
        answer = "Increased"
    elif change <= -threshold and 3 * sum(step < 0 for step in steps) >= 2 * len(steps):
        answer = "Decreased"
    else:
        answer = "Fluctuated / no clear trend"
    return answer, (f"Last minus first was {change:+.2f} {unit}. A directional trend requires "
                    f"at least {threshold:g} {unit} of net change and at least two thirds of "
                    "consecutive available readings moving in that direction.")


def challenges(state, data, config, mission_id):
    eligible = [variable for variable, group in data.groupby("Variable", sort=False) if group.Date.nunique() >= 3]
    if not eligible:
        st.info("Scientific challenges unavailable. At least three usable dates are needed for one measurement.")
        return
    quiz = state.setdefault("power_challenges", {"attempts": []})
    attempts = quiz["attempts"]
    variable = quiz.get("variable")
    if variable not in eligible:
        variable = None
    if variable is None:
        variable = st.selectbox("Challenge measurement", eligible, key=f"power_quiz:{mission_id}:variable")
    else:
        st.caption(f"Challenge measurement · {variable}")
    series = data[data.Variable == variable].sort_values("Date")
    values = series.Value.tolist()
    dates = series.Date.tolist()
    unit = series.Units.iloc[0]
    source = series.Source.iloc[0]
    st.caption(source)
    start = date.fromisoformat(config.get("start") or (config["co2_scenario"]["start"] if source == PRACTICE_SOURCE else config["environment"]["start"]))
    days = [f"Day {(day - start).days + 1} · {day}" for day in dates]
    index = len(attempts)
    if attempts:
        latest = attempts[-1]
        display = st.success if latest["correct"] else st.warning
        display(f"{'Correct' if latest['correct'] else 'Incorrect'} · {latest['points']} points")
        st.caption(latest["explanation"])
    if index == 3:
        st.success(f"All three challenges submitted · {sum(attempt['points'] for attempt in attempts)}/65 points")
        return
    st.markdown(f"**CHALLENGE {index + 1} / 3 — {CHALLENGE_NAMES[index].upper()}**")
    st.dataframe(series[["Date", "Value", "Units"]], hide_index=True, height=160)
    key = f"power_quiz:{mission_id}:{index}:{variable}"
    if index == 0:
        peak = max(values)
        correct_days = [day for day, value in zip(days, values) if value == peak]
        answer = st.radio(f"Which mission day had the highest {variable.lower()}?", days, index=None, key=key)
        correct = answer in correct_days
        explanation = f"Peak: {peak:.2f} {unit} on {', '.join(correct_days)}."
    elif index == 1:
        answer = st.number_input(f"Change from {dates[0]} to {dates[-1]} ({unit})",
                                 value=None, step=.01, key=key)
        change = values[-1] - values[0]
        correct = answer is not None and abs(answer - change) <= .005000001
        explanation = f"Last minus first: {values[-1]:.2f} − ({values[0]:.2f}) = {change:+.2f} {unit}."
    else:
        trend, rule = trend_answer(values, unit)
        answer = st.radio(f"How did {variable.lower()} generally change during the mission?",
                          ["Increased", "Decreased", "Fluctuated / no clear trend"], index=None, key=key)
        correct = answer == trend
        explanation = f"{trend}. {rule}"
    if st.button("Check Answer", disabled=answer is None, key=f"{key}:submit"):
        quiz["variable"] = variable
        attempts.append(dict(challenge=CHALLENGE_NAMES[index], answer=answer, correct=correct,
                             points=CHALLENGE_POINTS[index] if correct else 0, explanation=explanation))
        st.rerun()


def scores(state):
    if state.get("co2_investigation"):
        return state["co2_investigation"]["score"]
    quiz_points = sum(attempt["points"] for attempt in state.get("power_challenges", {}).get("attempts", []))
    graph_points = round(15 * max((e.get("accuracy", 100) for e in state["evidence"]), default=0) / 100)
    return quiz_points + graph_points + (state["conclusion"].get("points", 20) if state["conclusion"] else 0)


def analysis():
    mission = st.session_state.get("active_mission")
    with st.container(key="investigation_lab"):
        heading("DATA INVESTIGATION LAB", "Scientific operations · Investigate your mission archive and draw evidence-based conclusions.")
        if not mission or not mission["outcome"]:
            st.info("Complete a mission to unlock its investigation archive.")
            st.button("Mission Control", on_click=go, args=("mission_run",))
            return
        from mission_archive import history, save
        if any(row["id"] == mission.get("id") and row["transmitted"] for row in history()):
            st.info("This investigation was finalized and transmitted. Open Mission Report to review the archived results.")
            st.button("Open Mission Report", on_click=go, args=("mission_report",))
            return
        config = mission["config"]
        target = config["target"]
        if not config.get("environment") and not mission.get("analysis_environment"):
            st.caption("No NASA POWER data was attached at launch. Simulation mode does not request historical measurements.")
            with st.form("lab_power_archive"):
                start = st.date_input("Historical context start (UTC)", value=date(2023, 6, 1),
                                      min_value=date(1981, 1, 1), max_value=date.today()-timedelta(days=1))
                submitted = st.form_submit_button("Load NASA POWER context")
            if submitted:
                try:
                    days = min(config.get("duration", 7), (date.today()-start).days)
                    archive = power(target["lat"], target["lon"], start, days)
                    if not any(value is not None for values in archive["weather"].values() for value in values):
                        st.warning("NASA POWER returned no usable values for this window.")
                    else:
                        mission["analysis_environment"] = archive
                        st.rerun()
                except (OSError, ValueError, KeyError, TypeError) as error:
                    st.error(f"NASA POWER request failed: {error}")
        supplemental = mission.get("analysis_environment")
        config = {**config, "environment": config.get("environment") or supplemental}
        if supplemental:
            st.caption("Historical context added after the mission · separate from scan results and transmitted packets.")
        data = observations(config)
        state = mission.setdefault("analysis", dict(answers=[], evidence=[], flags={}, conclusion=None))
        challenge_data = data
        if config.get("co2_scenario"):
            days, values = practice_series(config)
            carbon = pd.DataFrame([(day, PRACTICE_VARIABLE, value, "ppm", PRACTICE_SOURCE)
                                   for day, value in zip(days, values) if value is not None], columns=data.columns)
            challenge_data = pd.concat([carbon, data], ignore_index=True)
        score = scores(state)
        state["score"] = score
        state["objectives"] = [bool(state["evidence"]) and not challenge_data.empty,
                               len(state.get("power_challenges", {}).get("attempts", [])) == 3,
                               bool(state["conclusion"])]
        if state.get("co2_investigation"):
            state["objectives"] = [True, True, True]
        state["limitations"] = ["OCO-2 soundings do not establish regional representativeness" if config.get("oco2", {}).get("observations") else "No OCO-2 retrievals in the mission archive", "NASA POWER covers one requested point"]
        env = config.get("environment")
        state["citations"] = [env["source"]] if env else []
        save(mission)
        st.caption(f"SCIENTIFIC OPERATIONS  ·  {mission['credits']:,} mission credits")
        left, center, right = st.columns([1.15, 4.1, 1.55], gap="small")
        with left, st.container(border=True):
            st.markdown("**ANALYSIS TOOLS**")
            tool = st.radio("Analysis tools", TOOLS, label_visibility="collapsed")
        with center:
            period = f"{data.Date.min()} to {data.Date.max()}" if len(data) else "Unavailable"
            for col, (label, value) in zip(st.columns(4), [
                ("Available measurements", len(data)), ("Observation period", period),
                ("Research objectives", f"{sum(state['objectives'])} / 3"), ("Analysis score", f"{score} / 100"),
            ]):
                col.metric(label, value)
            with st.container(border=True):
                workspace(tool, target, config, data, state)
            if tool not in (TOOLS[0], TOOLS[1]):
                with st.expander("Environmental context · NASA POWER"):
                    st.markdown("**ENVIRONMENTAL CONDITIONS · NASA POWER**")
                    if len(data):
                        st.dataframe(data, hide_index=True, height=210)
                        st.link_button("Source request", env["source"])
                    else:
                        st.caption("No historical environment measurements were saved with this mission.")
        with right:
            with st.container(border=True):
                if tool == TOOLS[0]:
                    st.caption("Use the timeline and notebook to complete your investigation.")
                elif tool == TOOLS[1]:
                    st.caption("Open another analysis tool to view the scientific challenges.")
                else:
                    challenges(state, challenge_data, config, mission["id"])
            with st.container(border=True):
                st.markdown("**RESEARCH OBJECTIVES**")
                if tool == TOOLS[0] or state.get("co2_investigation"):
                    labels = ["Check all recorded CO₂ measurements", "Answer the peak and average questions",
                              "Submit a written conclusion"]
                    done = [bool(state.get("co2_investigation"))] * 3
                    st.caption("40 notebook · 20 peak · 20 average · 20 written submission")
                else:
                    labels = ["Save a graph of archived measurements", "Submit all three measurement challenges",
                              "Submit a conclusion attempt"]
                    done = state["objectives"]
                    st.caption("25 peak · 25 change · 15 trend · 15 graph · 20 conclusion")
                for complete, label in zip(done, labels):
                    st.write(f"{'✓' if complete else '□'} {label}")
                st.button("MISSION REPORT →", disabled=not (state.get("co2_investigation") or (state["objectives"][1] and state["conclusion"])),
                          on_click=go, args=("mission_report",), width="stretch")


def workspace(tool, target, config, data, state):
    if tool == TOOLS[0]:
        practice_view(config, state=state, prefix=f"co2_lab:{st.session_state.active_mission['id']}")
        return
    if tool == TOOLS[5]:
        map_col, trend = st.columns(2, gap="small")
        from oco2_data import retrieve
        archive = config.get("oco2", {})
        start = config.get("start")
        if start and st.button("Load NASA OCO-2"):
            try:
                archive = retrieve(target["lat"], target["lon"], date.fromisoformat(start), config["duration"])
            except (ImportError, OSError, ValueError, RuntimeError) as error:
                st.error(f"OCO-2 retrieval failed: {error}")
            else:
                mission = st.session_state.active_mission
                mission["config"]["oco2"] = archive
                from mission_archive import save
                save(mission)
        samples = pd.DataFrame(archive.get("observations", []))
        with map_col:
            st.markdown("**CO₂ OBSERVATION MAP**")
            if samples.empty:
                region_map(target)
            else:
                points = samples.iloc[::max(1, (len(samples)+1999)//2000)]
                fig = go_chart.Figure(go_chart.Scattermap(
                    lat=points.latitude, lon=points.longitude, mode="markers",
                    text=points.timestamp, customdata=points.xco2_ppm,
                    hovertemplate="%{text}<br>%{customdata:.2f} ppm<extra>NASA OCO-2</extra>",
                    marker=dict(size=7,color=points.xco2_ppm,colorscale="Viridis",
                                showscale=True,colorbar=dict(title="XCO₂ (ppm)"))))
                fig.add_trace(go_chart.Scattermap(lat=[target["lat"]],lon=[target["lon"]],
                                              mode="markers", name="Mission target", marker=dict(color="cyan",size=13)))
                fig.update_layout(map=dict(style="carto-darkmatter",zoom=5,
                    center=dict(lat=target["lat"],lon=target["lon"])),
                    template="plotly_dark",height=280,margin=dict(l=0,r=0,t=0,b=0))
                st.plotly_chart(fig,key="oco2_map")
                st.caption(f"Map shows {len(points):,} of {len(samples):,} soundings. Cyan marks the mission target.")
        with trend:
            st.markdown("**ATMOSPHERIC CO₂ TREND — NASA OCO-2**")
            if samples.empty:
                if not start:
                    st.info("Use a historical mission with a saved start date to retrieve OCO-2.")
                elif "granules" in archive:
                    st.info("No quality-approved soundings matched the mission dates and target box.")
                else:
                    st.info("Load OCO-2 to search this mission’s UTC dates.")
            else:
                daily = samples.groupby("date").xco2_ppm.agg(["mean","count"]).reset_index()
                fig = go_chart.Figure(go_chart.Scatter(x=daily.date,y=daily["mean"],mode="markers",
                    marker=dict(color="#46f1ff",size=9),customdata=daily["count"],
                    hovertemplate="%{x}<br>%{y:.2f} ppm<br>%{customdata} soundings<extra></extra>"))
                fig.update_layout(template="plotly_dark",height=245,xaxis_title="Observation date (UTC)",
                                  yaxis_title="XCO₂ (ppm)",margin=dict(l=8,r=8,t=12,b=8))
                st.plotly_chart(fig,key="oco2_trend")
                values = samples.xco2_ppm
                st.caption(f"Mean {values.mean():.2f} ppm · Min {values.min():.2f} · Max {values.max():.2f} · "
                           f"{len(values):,} soundings · {daily.date.min()} to {daily.date.max()}")
                st.caption("Each dot is a daily arithmetic mean of valid soundings. Sample means do not establish regional representativeness or local emissions.")
        st.markdown("**ATMOSPHERIC CO₂ OBSERVATIONS · NASA OCO-2**")
        if not samples.empty:
            st.dataframe(samples[["date","latitude","longitude","xco2_ppm","version","source"]].head(250),
                         hide_index=True,height=220)
            st.caption("First 250 soundings shown. Quality flag 0, within ±2° latitude and longitude of the target. Historical NASA observations are separate from gameplay packets.")
        st.link_button("NASA OCO-2 product information", "https://ocov2.jpl.nasa.gov/science/oco-2-data-center/")
        return
    if tool == TOOLS[4]:
        conclusion(state, config)
        return
    if tool == TOOLS[1]:
        play(config, state)
        return
    if data.empty:
        st.info("This mission archive contains no scientific measurements for this tool.")
        return
    series = filtered(data, f"lab_{TOOLS.index(tool)}")
    if tool == TOOLS[2]:
        st.caption("This archive covers one region. Compare two periods for the same measurement.")
        dates = sorted(series.Date.unique())
        if len(dates) < 2:
            st.info("Select at least two dates.")
            return
        split = st.selectbox("Last date of period A", dates[:-1])
        a, b = series[series.Date <= split], series[series.Date > split]
        stats = pd.DataFrame({label: group.Value.agg(["mean", "min", "max", "count"])
                              for label, group in [("Period A", a), ("Period B", b)]})
        st.dataframe(stats)
        st.write(f"Mean difference (B − A): {b.Value.mean() - a.Value.mean():.2f} {series.iloc[0].Units}")
        chart(series, "Scatter", key="lab_comparison_chart")
        st.caption("Uneven sampling and short windows limit interpretation.")
        if st.button("Record coverage review"):
            state["coverage_reviewed"] = True
            st.rerun()
    else:
        threshold = st.slider("Flag at or above this many standard deviations", 1.0, 3.0, 2.0, .25)
        values = series.Value.tolist()
        spread = pstdev(values)
        if len(values) < 3 or not spread:
            st.info("At least three varying measurements are needed for this screen.")
            return
        anomalies = series.assign(Deviation=(series.Value - mean(values)).abs() / spread)
        anomalies = anomalies[anomalies.Deviation >= threshold]
        if anomalies.empty:
            st.caption("No candidates at this threshold.")
            return
        day = st.selectbox("Inspect observation", anomalies.Date.tolist())
        st.dataframe(series[series.Date.between(day - timedelta(days=1), day + timedelta(days=1))], hide_index=True)
        st.caption("Statistical flags identify candidates for review. The NASA POWER archive here contains no per-row quality flag.")
        decision = st.selectbox("Review decision", ["Accept", "Flag for review", "Exclude from this anomaly review"])
        key = f"{series.iloc[0].Variable} · {day}"
        if st.button("Save review decision"):
            state["flags"][key] = decision
        st.caption(f"Saved decision: {state['flags'].get(key, 'None')}")


INSUFFICIENT = "Insufficient evidence"
SUPPORTED = "The available observations support an XCO₂ estimate"
SAMPLE_MEAN = "The transmitted soundings support a sample mean"
COVERAGE_EVIDENCE = "Mission archive: XCO₂ sample quality and coverage"


def conclusion_review(config, answer, evidence):
    # An OCO-2 loader can attach target/date-scoped rows and a documented
    # representativeness assessment to config["oco2"]. Coverage defaults to unknown.
    if config.get("co2_scenario"):
        readings = usable(config)
        correct_answer = SAMPLE_MEAN if readings else INSUFFICIENT
        correct = answer == correct_answer
        relevant = COVERAGE_EVIDENCE in evidence or bool(set(evidence) & set(config.get("comparison_labels", [])))
        reason = (f"{len(readings)} usable soundings support a sample mean of "
                  f"{mean(row['xco2_ppm'] for row in readings):.2f} ppm." if readings
                  else "No usable transmitted soundings are available for a sample mean.")
        return dict(correct=correct, correct_answer=correct_answer,
                    feedback="The selected archive evidence is relevant." if relevant else "Cite the sounding quality and coverage record or a saved CO₂ comparison.",
                    reason=f"{PRACTICE_SOURCE}. {reason} This does not establish a representative regional average or local emissions.",
                    points=15 * correct + 5 * (correct and relevant))
    archive = config.get("oco2") or {}
    valid = [
        row["xco2_ppm"] for row in archive.get("observations", [])
        if row.get("xco2_quality_flag") == 0
        and isinstance(row.get("xco2_ppm"), (float, int))
        and isfinite(row["xco2_ppm"]) and row["xco2_ppm"] > 0
    ]
    assessment = archive.get("regional_coverage") or {}
    representative = bool(valid and assessment.get("representative") is True
                          and assessment.get("rationale", "").strip())
    correct_answer = SUPPORTED if representative else INSUFFICIENT
    if not valid:
        explanation = ("The archive contains no valid OCO-2 XCO₂ observations. "
                       "Environmental readings such as air temperature cannot establish atmospheric XCO₂.")
    elif representative:
        explanation = f"{len(valid)} quality-approved samples support the estimate. {assessment['rationale']}"
    else:
        explanation = (f"The {len(valid)} quality-approved samples can give a sample mean of "
                       f"{mean(valid):.2f} ppm. A representative regional estimate also requires "
                       "adequate spatial and temporal coverage, which this archive does not establish.")
    correct = answer == correct_answer
    relevant = COVERAGE_EVIDENCE in evidence
    feedback = ("The archive quality and coverage record supports your conclusion." if relevant and correct
                else "The archive quality and coverage record is relevant, but it supports the correct answer above." if relevant
                else "The selected evidence does not establish XCO₂ quality or coverage." if evidence
                else "No supporting evidence was selected. The archive's XCO₂ quality and coverage record is relevant.")
    return dict(correct=correct, correct_answer=correct_answer, feedback=feedback,
                reason=explanation, points=15 * correct + 5 * (correct and relevant))


def conclusion(state, config):
    practice = bool(config.get("co2_scenario"))
    comparisons = [item["label"] for item in state.get("co2_comparisons", [])]
    question = ("Do transmitted practice soundings support calculating a sample mean?"
                if practice else "Can this mission archive support a representative estimate of the target region’s mean XCO₂?")
    st.markdown(f"**{question}**")
    with st.form("scientific_conclusion"):
        answer = st.radio("Conclusion", [INSUFFICIENT, SAMPLE_MEAN if practice else SUPPORTED], index=None)
        evidence = st.multiselect("Evidence references (optional)",
                                  [COVERAGE_EVIDENCE, *comparisons, *[item["label"] for item in state["evidence"]]])
        explanation = st.text_area("Explain your reasoning (optional)", max_chars=1500)
        if st.form_submit_button("Submit conclusion", type="primary"):
            if answer is None:
                st.info("Choose an answer to submit.")
            else:
                state["conclusion"] = dict(answer=answer, evidence=evidence, explanation=explanation,
                                           **conclusion_review(dict(config, comparison_labels=comparisons), answer, evidence))
                st.rerun()
    if state["conclusion"]:
        conclusion_result(state["conclusion"])


def conclusion_result(result):
    if "correct" not in result:
        st.success("Previously accepted conclusion saved.")
        st.write(result["answer"])
        return
    status = "CORRECT CONCLUSION" if result["correct"] else "INCORRECT CONCLUSION"
    tone = "correct" if result["correct"] else "incorrect"
    st.html(f"""<section class="ow-conclusion {tone}">
        <h3>{status}</h3>
        <p><b>Your answer</b> · {escape(result['answer'])}</p>
        <p><b>Correct answer</b> · {escape(result['correct_answer'])}</p>
        <p>{escape(result['reason'])}</p>
        <p><b>Evidence</b> · {escape(result['feedback'])}</p>
        <strong>{result['points']} / 20 conclusion points</strong>
        </section>""")


def report_findings(mission, *, mission_id, section):
    state = mission.get("analysis", {})
    if not state.get("conclusion"):
        st.info("Complete the investigation to add scientific findings.")
        return
    st.metric("Investigation score", f"{state['score']} / 100")
    st.write(f"Research objectives completed: {sum(state['objectives'])} / 3")
    conclusion_result(state["conclusion"])
    st.write(state["conclusion"]["explanation"])
    st.write("Evidence", state["conclusion"]["evidence"])
    for index, item in enumerate(state["evidence"]):
        with st.expander(item["label"]):
            if "accuracy" in item:
                st.write(f"Accuracy: {item['accuracy']}/100 · MAE: {item['mae']:.2f}")
            # Older reports have no graph ID. Their archived order is stable.
            graph_id = item.get("id") or f"legacy-{index}"
            chart(pd.DataFrame(item["rows"]), item["kind"],
                  key=f"report:{mission_id}:{section}:graph:{graph_id}:{index}")
    for limitation in state["limitations"]:
        st.caption(limitation)
    for source in state["citations"]:
        st.link_button("NASA POWER source request", source)


def notebook_report(result):
    st.success("INVESTIGATION COMPLETE")
    st.caption(PRACTICE_SOURCE)
    st.write(f"{len(result['table'])} observations analyzed · Highest {result['peak']:.2f} ppm · "
             f"Average {result['mean']:.2f} ppm · Research score {result['score']}/100")
    st.dataframe(result["table"], hide_index=True)
    st.write(f"Peak answer: {result['peak_answer']} · Average answer: {result['average_answer']:.2f} ppm")
    st.caption("Written conclusion submitted. The writing was checked for completion.")
    st.text(result["conclusion"])


def remember(draft, field, key, obs=None):
    if obs is None:
        draft[field] = st.session_state[key]
    else:
        draft["entries"][obs] = st.session_state[key]
        draft["checks"].pop(obs, None)


def practice_view(config, *, state=None, prefix="co2_lab"):
    # Downlink appends packets in FIFO order, preserving scan and packet sequence.
    records = config.get("co2_transmitted", [])
    st.markdown("**CO₂ OBSERVATION TIMELINE**")
    st.caption("Analyze the atmospheric carbon dioxide measurements collected during your satellite mission.")
    st.caption(f"SIMULATED XCO₂ — MISSION OBSERVATIONS · {PRACTICE_SOURCE}")
    if not records:
        st.info("No CO₂ measurements have been transmitted to Earth yet. Complete satellite scans and transmit your collected data to begin your investigation.")
        return
    target = config["target"]["name"]
    positions = list(range(len(records)))
    fig = go_chart.Figure(go_chart.Scatter(
        x=positions, y=[row["xco2_ppm"] for row in records],
        mode="lines+markers" if len(records) > 1 else "markers",
        line=dict(color="#41efff", width=2),
        marker=dict(color="#41efff", size=9, symbol="circle"),
        customdata=[[row["day"], row.get("date") or "Date unavailable", row["id"], target, row["quality"]]
                    for row in records],
        hovertemplate="Day %{customdata[0]} · %{customdata[1]}<br>%{y:.2f} ppm · %{customdata[2]}"
                      "<br>%{customdata[3]} · %{customdata[4]}<extra></extra>",
    ))
    fig.update_layout(template="plotly_dark", paper_bgcolor="#061a29", plot_bgcolor="#081d2d",
                      height=330, xaxis_title="Observation ID", yaxis_title="Simulated XCO₂ (ppm)",
                      margin=dict(l=8, r=8, t=12, b=8))
    fig.update_xaxes(tickmode="array", tickvals=positions,
                     ticktext=[row["id"] for row in records], showgrid=False)
    fig.update_yaxes(showgrid=True, gridcolor="#1c3c4e")
    st.plotly_chart(fig, key=f"{prefix}_timeline")
    if state is None:
        return
    if state.get("co2_investigation"):
        notebook_report(state["co2_investigation"])
        return
    draft = state.setdefault("co2_notebook", dict(entries={}, checks={}, peak=None, average=None, conclusion=""))
    st.markdown("**SCIENTIFIC OBSERVATION LOG**")
    st.caption("Study the CO₂ observation graph above and manually record the measurements collected during your mission. Hover over each point to read its exact value.")
    for col, title in zip(st.columns([1.1, 1, 1.15, .8]),
                          ("Mission Day", "Observation Date", "CO₂ Measurement (ppm)", "Status")):
        col.markdown(f"**{title}**")
    for row in records:
        obs = row["id"]
        day, timestamp, entry, status = st.columns([1.1, 1, 1.15, .8])
        day.write(f"Day {row['day']} · {obs}")
        timestamp.write(row.get("date") or "—")
        key = f"{prefix}:entry:{obs}"
        entry.number_input(f"CO₂ measurement for {obs}", value=draft["entries"].get(obs),
                           step=.01, format="%.2f", label_visibility="collapsed", key=key,
                           on_change=remember, args=(draft, "entries", key, obs))
        check = draft["checks"].get(obs)
        status.write("✅ Correct" if check is True else "🔴 Try again" if check is False
                     else "Not completed" if draft["entries"].get(obs) is None else "Not checked")
    if st.button("CHECK MEASUREMENTS", key=f"{prefix}:check"):
        draft["checks"] = {r["id"]: abs(draft["entries"][r["id"]] - r["xco2_ppm"]) <= .050000001
                           for r in records if draft["entries"].get(r["id"]) is not None}
        draft["checked"] = True
        st.rerun()
    st.caption(f"Measurements recorded: {sum(draft['entries'].get(r['id']) is not None for r in records)} / {len(records)}")
    if draft.get("checked"):
        st.caption(f"Correct measurements: {sum(draft['checks'].values())} / {len(records)}")
    st.markdown("**RESEARCH QUESTIONS**")
    st.caption("Use your satellite observations to answer the following scientific questions. Include every transmitted point in the average.")
    labels = {r["id"]: f"Day {r['day']} · {r['id']}" for r in records}
    options = list(labels)
    key = f"{prefix}:peak"
    st.selectbox("1. Which observation recorded the highest CO₂ concentration?", options,
                 index=options.index(draft["peak"]) if draft["peak"] in options else None,
                 format_func=labels.get, key=key, on_change=remember, args=(draft,"peak",key))
    key = f"{prefix}:average"
    st.number_input("2. Average CO₂ concentration (ppm)", value=draft["average"], step=.01,
                    key=key, on_change=remember, args=(draft,"average",key))
    key = f"{prefix}:conclusion"
    st.text_area("3. What can you conclude about the CO₂ measurements collected during your mission?",
                 value=draft["conclusion"], key=key, max_chars=1500, on_change=remember,
                 args=(draft,"conclusion",key))
    if st.button("SUBMIT INVESTIGATION", type="primary", key=f"{prefix}:submit"):
        highest = max(r["xco2_ppm"] for r in records)
        average = mean(r["xco2_ppm"] for r in records)
        errors = []
        if not all(draft["checks"].get(r["id"]) is True for r in records):
            errors.append("Record every measurement and check the table. Fix entries marked Try again.")
        if draft["peak"] not in {r["id"] for r in records if r["xco2_ppm"] == highest}:
            errors.append("Question 1: identify the highest point on the graph.")
        if draft["average"] is None or abs(draft["average"] - average) > .050000001:
            errors.append("Question 2: add all transmitted readings and divide by their count.")
        if len(draft["conclusion"].strip()) < 25 or len(draft["conclusion"].split()) < 5:
            errors.append("Question 3: write a short conclusion in your own words.")
        if errors:
            for error in errors:
                st.warning(error)
        else:
            state["co2_investigation"] = dict(peak=highest, mean=average, score=100, source=PRACTICE_SOURCE,
                peak_answer=draft["peak"], average_answer=draft["average"], conclusion=draft["conclusion"],
                table=[{"Mission day": r["day"], "Date": r.get("date"), "Observation": r["id"],
                        "Recorded ppm": draft["entries"][r["id"]], "Status": "Correct"} for r in records])
            st.rerun()
