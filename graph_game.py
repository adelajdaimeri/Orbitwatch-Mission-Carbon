from uuid import uuid5, NAMESPACE_URL
from datetime import date, timedelta
from math import isfinite
from statistics import mean

import pandas as pd
import streamlit as st

from co2_practice import KEY, SOURCE, VARIABLE, series as practice_series
from nasa_data import PARAMETER, WEATHER

TOLERANCE = {KEY: .25, "T2M": 1, "RH2M": 5, "WS10M": .5, PARAMETER: .5}
EDITOR = st.components.v2.component("orbitwatch.graph_editor",
    html='<svg viewBox="0 0 760 310" role="img" aria-label="Editable measurement graph"></svg>',
    css="svg{width:100%;background:#061b2a;touch-action:none;cursor:crosshair;border-radius:12px} text{fill:#abdce9;font:11px sans-serif;pointer-events:none}",
    js="""export default function({parentElement,data,setTriggerValue}) {
    const svg = parentElement.querySelector('svg');
    const points = {...data.points};
    const x = i => 65 + i * 660 / Math.max(1,data.days.length-1);
    const y = v => 260 - (v-data.low)*230/(data.high-data.low);
    const node = (tag, attrs, label) => {
        const el=document.createElementNS('http://www.w3.org/2000/svg',tag);
        Object.entries(attrs).forEach(([key,value])=>el.setAttribute(key,value));
        if(label!==undefined) el.textContent=label;
        svg.append(el);
    };
    function draw() {
        svg.replaceChildren();
        for(let j=0;j<=5;j++){
            const v=data.low+j*(data.high-data.low)/5;
            node('line',{x1:65,x2:725,y1:y(v),y2:y(v),stroke:'#254657'});
            node('text',{x:5,y:y(v)+4},v.toFixed(1)+' '+data.unit);
        }
        data.days.forEach((day,i)=>{
            node('line',{x1:x(i),x2:x(i),y1:30,y2:260,stroke:'#173649'});
            node('text',{x:x(i),y:278,'text-anchor':'middle'},i+1);
            if(i % Math.ceil(data.days.length/10)===0)
                node('text',{x:x(i),y:297,'text-anchor':'middle'},day.slice(5));
        });
        for(const [series,color] of [[points,'#42edff'],[data.reference,'#ffca65']]){
            for(const [i,value] of Object.entries(series))
                node('circle',{cx:x(+i),cy:y(value),r:6,fill:color});
        }
    }
    let index=null;
    function coords(e){
        const p=svg.createSVGPoint();p.x=e.clientX;p.y=e.clientY;
        return p.matrixTransform(svg.getScreenCTM().inverse());
    }
    function move(e){
        const p=coords(e);
        points[index]=Math.round(100*(data.low+Math.max(0,Math.min(1,(260-p.y)/230))*(data.high-data.low)))/100;
        draw();
    }
    svg.onpointerdown=e=>{
        const p=coords(e);
        const i=Math.round((p.x-65)*Math.max(1,data.days.length-1)/660);
        if(!data.editable.includes(i)||p.y<20||p.y>265)return;
        index=i;svg.setPointerCapture(e.pointerId);move(e);
    };
    svg.onpointermove=e=>{if(index!==null)move(e);};
    svg.onpointerup=()=>{if(index===null)return;setTriggerValue('edit',{index,value:points[index]});index=null;};
    svg.onpointercancel=()=>{index=null;draw();};
    draw();
    return ()=>{svg.onpointerdown=svg.onpointermove=svg.onpointerup=svg.onpointercancel=null;};
}""")


def mission_series(config, key):
    env = config["environment"]
    start = date.fromisoformat(config.get("start") or env["start"])
    source_start = date.fromisoformat(env["start"])
    raw = env.get("weather", {PARAMETER: env["series"]}).get(key, [])
    days = [start + timedelta(days=i) for i in range(config.get("duration", len(env["series"])))]
    values = []
    for day in days:
        offset = (day-source_start).days
        values.append(raw[offset] if 0 <= offset < len(raw) else None)
    return days, values


def edit(board, index, value):
    board["undo"].append(dict(board["points"]))
    if value is None:
        board["points"].pop(index, None)
    else:
        board["points"][index] = value
    board["result"] = None


def widget_edit(board, targets, low, high):
    change = st.session_state.graph_editor.edit
    index, value = change["index"], change["value"]
    if index in targets and isfinite(value) and low <= value <= high:
        edit(board, index, value)


def play(config, state):
    fields = {}
    if config.get("co2_scenario"):
        fields[KEY] = (VARIABLE, "ppm", SOURCE, practice_series(config))
    if config.get("environment"):
        for key, (label, unit, _) in WEATHER.items():
            fields[key] = (label, unit, "NASA POWER", mission_series(config, key))
    keys = [key for key, (_, _, _, (_, values)) in fields.items() if any(v is not None for v in values)]
    if not keys:
        st.info("No usable environmental readings or transmitted XCO₂ soundings are available.")
        return
    key = st.selectbox("Measurement",keys,format_func=lambda k: fields[k][0])
    mode = st.radio("Exercise",["Plot the Data","Predict the Trend"],horizontal=True)
    label,unit,source,(days,values)=fields[key]
    st.caption(source)
    known=[i for i,v in enumerate(values) if v is not None]
    clues=set(known[::3]) if mode=="Predict the Trend" and len(known)>1 else set()
    targets=[i for i in known if i not in clues]
    board=state.setdefault("graph_boards",{}).setdefault(f"{key}:{mode}",dict(points={},undo=[],result=None))
    if mode=="Predict the Trend":
        st.caption("Predict hidden readings from the gold clues in this practice exercise.")
    st.caption("Click a mission day to place a point. Drag vertically to adjust it. Cyan shows your points.")
    # Fixed physical display domains avoid leaking hidden values through autoscaling.
    low,high={KEY:(413,428),"T2M":(-90,60),"RH2M":(0,100),"WS10M":(0,45),PARAMETER:(0,16)}[key]
    result=board["result"]
    reference={str(i):values[i] for i in (known if result else clues)}
    EDITOR(key="graph_editor",data=dict(days=[str(d) for d in days],points={str(i): v for i, v in board["points"].items()},
           reference=reference,editable=targets,low=low,high=high,unit=unit),
           on_edit_change=lambda: widget_edit(board,targets,low,high))
    selected=st.selectbox("Edit or delete a point",targets,format_func=lambda i:f"Day {i+1} · {days[i]}")
    value=st.number_input(f"Point value ({unit})",value=float(board["points"].get(selected,(low+high)/2 if key == KEY else 0)),step=.01)
    place,delete,undo,reset=st.columns(4)
    if place.button("Place point"):
        if low<=value<=high:
            edit(board,selected,value)
            st.rerun()
        st.error(f"Enter a value between {low} and {high} {unit}.")
    if delete.button("Delete point",disabled=selected not in board["points"]):
        edit(board,selected,None)
        st.rerun()
    if undo.button("Undo",disabled=not board["undo"]):
        board["points"]=board["undo"].pop()
        board["result"]=None
        st.rerun()
    if reset.button("Reset",disabled=not board["points"]):
        board["undo"].append(dict(board["points"]))
        board.update(points={},result=None)
        st.rerun()
    if st.button("CHECK ACCURACY",disabled=not all(i in board["points"] for i in targets)):
        errors=[abs(board["points"][i]-values[i]) for i in targets]
        mae=mean(errors)
        accuracy=round(100/(1+mae/TOLERANCE[key]))
        board["result"]=dict(mae=mae,accuracy=accuracy)
        evidence=dict(label=f"{mode} · {label} · {days[0]} to {days[-1]}",kind="Scatter",
                      accuracy=accuracy,mae=mae,points=dict(board["points"]),
                      rows=[dict(Date=str(days[i]),Variable=label,Units=unit,Value=values[i],Source=source) for i in known])
        prior=next((e for e in state["evidence"] if e["label"]==evidence["label"]),None)
        evidence["id"] = (prior or {}).get("id") or str(uuid5(NAMESPACE_URL, evidence["label"]))
        if prior is None or accuracy>=prior.get("accuracy",0):
            state["evidence"]=[e for e in state["evidence"] if e["label"]!=evidence["label"]]+[evidence]
        st.rerun()
    if result:
        st.success(f"{result['accuracy']}/100 · Mean absolute error {result['mae']:.2f} {unit}")
        st.caption(f"Score = 100 ÷ (1 + MAE ÷ {TOLERANCE[key]} {unit}), rounded. Missing readings are excluded.")
    st.markdown(f"**{source}**")
    st.dataframe(pd.DataFrame([
        {"Day":i+1,"Date":day,"Reading":("Missing" if values[i] is None else "Hidden"
         if mode=="Predict the Trend" and i in targets and not result else f"{values[i]:.2f} {unit}"),
         "Your point":board["points"].get(i),"Absolute error":round(abs(board["points"][i]-values[i]),2) if result and i in targets else None}
        for i,day in enumerate(days)]),hide_index=True)
    if source == "NASA POWER":
        st.link_button("NASA POWER source request",config["environment"]["source"])