from datetime import timedelta
from math import isfinite
from urllib.parse import urlencode
from urllib.request import urlopen
import json

import streamlit as st


POWER = "https://power.larc.nasa.gov/api/temporal/daily/point"
PARAMETER = "ALLSKY_SFC_SW_DWN"
WEATHER = {"T2M": ("Air temperature at 2 m", "°C", "C"),
           "RH2M": ("Relative humidity at 2 m", "%", "%"),
           "WS10M": ("Wind speed at 10 m", "m/s", "m/s"),
           PARAMETER: ("Surface solar irradiance", "kWh/m²/day", "kW-hr/m^2/day")}


@st.cache_data(ttl=3600, max_entries=64)
def power(lat, lon, start, days):
    end = start + timedelta(days=days - 1)
    url = POWER + "?" + urlencode(dict(
        parameters=",".join(WEATHER), community="RE", latitude=lat, longitude=lon,
        start=start.strftime("%Y%m%d"), end=end.strftime("%Y%m%d"), format="JSON",
        **{"time-standard": "UTC"},
    ))
    with urlopen(url, timeout=12) as response:
        document = json.loads(response.read(256_000))
    units = document["parameters"][PARAMETER]["units"]
    if units != "kW-hr/m^2/day":
        raise ValueError("Unexpected NASA POWER irradiance units")
    fill = document["header"]["fill_value"]
    parameters = document["properties"]["parameter"]
    weather = {}
    for key, (_, _, expected_units) in WEATHER.items():
        if document["parameters"][key]["units"] != expected_units:
            raise ValueError(f"Unexpected NASA POWER units for {key}")
        raw = parameters[key]
        series = []
        for offset in range(days):
            value = raw.get((start + timedelta(days=offset)).strftime("%Y%m%d"))
            valid = isinstance(value, (int, float)) and isfinite(value) and value != fill
            series.append(value if valid else None)
        weather[key] = series
    return dict(source=url, units=units, start=start.isoformat(), series=weather[PARAMETER],
                weather=weather, sources=document["header"].get("sources", []))
