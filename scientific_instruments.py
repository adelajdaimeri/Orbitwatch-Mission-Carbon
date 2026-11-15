"""Fictional payload specifications. Prices, mass and energy are gameplay values."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Instrument:
    name: str
    collection: str
    price: int
    mass: int
    energy: int
    purpose: str


INSTRUMENTS = {
    "co2": Instrument("CO₂ Spectrometer", "Atmospheric CO₂", 1500, 12, 5,
                      "Uses spectroscopy for OCO-2-style column-average CO₂ observations."),
    "multispectral": Instrument("Multispectral Imager", "Land and Vegetation", 1200, 9, 4,
                                "Uses multiple reflected-light bands to study vegetation and land surfaces."),
    "thermal": Instrument("Thermal Infrared Sensor", "Surface Temperature", 1800, 15, 7,
                          "Uses thermal infrared radiance to estimate land surface temperature."),
    "gas": Instrument("Atmospheric Gas Spectrometer", "Additional atmospheric measurements", 2200, 18, 8,
                      "Models nitrogen dioxide (NO₂) observations, comparable in purpose to Aura OMI NO₂."),
}
BODY_LIMITS = {"compact": (85, 110), "standard": (115, 160), "advanced": (150, 220)}


def payload(body, instruments):
    parts = [INSTRUMENTS[key] for key in dict.fromkeys(instruments)]
    mass, limit = BODY_LIMITS[body]
    return mass + sum(part.mass for part in parts), limit, sum(part.energy for part in parts)


def supported_collections(satellite):
    supported = {INSTRUMENTS[key].collection for key in satellite.get("instruments", ())}
    if satellite["components"].get("sensors"):
        supported.add("Atmospheric CO₂")
    return supported
