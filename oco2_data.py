"""NASA GES DISC OCO-2 Lite retrieval for a mission's UTC dates and target box."""
import os
from datetime import date, timedelta
from urllib.parse import urlparse

import requests
import streamlit as st

CMR = "https://cmr.earthdata.nasa.gov/search/granules.json"
PRODUCT = "OCO2_L2_Lite_FP"
RADIUS = 2


@st.cache_data(ttl=86400, max_entries=12, show_spinner="Loading NASA OCO-2 soundings…")
def retrieve(lat, lon, start, days):

    token = os.environ.get("EARTHDATA_TOKEN", "").strip()
    if not token:
        raise ValueError("Set EARTHDATA_TOKEN to your Earthdata Login user token and restart Streamlit.")
    from netCDF4 import Dataset, num2date
    import numpy as np

    end = start + timedelta(days=days)
    versions = ["11.3r", "11.2r"] if end > date(2024, 1, 1) else ["11.2r"]
    granules = {}
    for version in versions:
        response = requests.get(CMR, params=dict(short_name=PRODUCT, version=version,
            provider="GES_DISC", temporal=f"{start}T00:00:00Z,{end-timedelta(days=1)}T23:59:59Z",
            page_size=100), timeout=20)
        response.raise_for_status()
        for entry in response.json()["feed"]["entry"]:
            day = entry["time_start"][:10]
            if not start.isoformat() <= day < end.isoformat() or day in granules or (version == "11.3r" and day < "2024-01-01"):
                continue
            for link in entry.get("links", []):
                url = link.get("href", "")
                parts = urlparse(url)
                if (parts.scheme == "https" and parts.hostname == "data.gesdisc.earthdata.nasa.gov"
                        and parts.path.startswith("/data/") and parts.path.endswith(".nc4")):
                    granules[day] = (version, url)
                    break
    rows = []
    for version, url in sorted(granules.values()):
        with requests.get(url, headers={"Authorization": f"Bearer {token}"},
                          allow_redirects=False, timeout=(10, 45)) as response:
            if response.status_code in (301, 302, 303, 307, 308, 401, 403):
                raise ValueError(f"GES DISC returned HTTP {response.status_code}. Check the Earthdata token and GES DISC authorization.")
            response.raise_for_status()
            with Dataset("oco2.nc4", memory=response.content) as ds:
                def read(name):
                    return np.ma.asarray(ds[name][:], dtype=float).filled(np.nan)
                xs, ys, ppm, quality = map(read, ("longitude", "latitude", "xco2", "xco2_quality_flag"))
                if str(ds["xco2"].units).strip().lower() not in {"ppm", "parts per million"}:
                    raise ValueError("Unexpected OCO-2 XCO₂ units.")
                times = read("time")
                indices = np.flatnonzero((quality == 0) & np.isfinite(ppm) & (ppm > 0)
                    & (abs(ys - lat) <= RADIUS) & (abs((xs - lon + 180) % 360 - 180) <= RADIUS)
                    & np.isfinite(times))
                timestamps = num2date(times[indices], ds["time"].units, only_use_cftime_datetimes=False)
                for i, stamp in zip(indices, timestamps):
                    day = stamp.strftime("%Y-%m-%d")
                    if start.isoformat() <= day < end.isoformat():
                        rows.append(dict(date=day, timestamp=stamp.isoformat(), latitude=float(ys[i]),
                            longitude=float(xs[i]), xco2_ppm=float(ppm[i]), xco2_quality_flag=0,
                            version=version, source=url))
    return {"observations": rows, "granules": [url for _, url in granules.values()]}