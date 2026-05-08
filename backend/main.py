"""
CTA-SIM PRO — FastAPI Backend
Exposes all psychrometric + AHU simulation endpoints.
Run: uvicorn main:app --reload --port 8000
"""

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional
import math

from psychrometrics import (
    AirState, SimulationResult,
    simulate, annual_profile, daily_profile, step_zone_state,
    psat, humidity_ratio, enthalpy, wet_bulb,
    dew_point, relative_humidity_from_W, specific_volume, air_density
)

# ─── App ──────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="CTA-SIM PRO API",
    description="Plateforme de Simulation Avancée des Centrales de Traitement d'Air — TLILI SOULAYMEN",
    version="3.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Schemas ──────────────────────────────────────────────────────────────────

class SimRequest(BaseModel):
    T_ext:     float = Field(34.0,  description="Outdoor dry-bulb temperature [°C]", ge=-20, le=55)
    RH_ext:    float = Field(50.0,  description="Outdoor relative humidity [%]", ge=5, le=100)
    pct_fresh: float = Field(40.0,  description="Fresh air ratio [%]", ge=0, le=100)
    Q_vol:     float = Field(8000.0,description="Total airflow [m³/h]", ge=500, le=100000)
    T_sup:     float = Field(13.0,  description="Supply air temperature [°C]", ge=5, le=25)
    T_zone:    float = Field(24.0,  description="Zone setpoint temperature [°C]", ge=15, le=32)
    RH_zone:   float = Field(50.0,  description="Zone RH setpoint [%]", ge=20, le=80)
    fan_eta:   float = Field(0.7,   description="Fan efficiency [-]", ge=0.3, le=0.95)
    dp_fan:    float = Field(600.0, description="Fan total pressure rise [Pa]", ge=100, le=3000)


class AnnualRequest(BaseModel):
    T_avg:     float = Field(18.5,  description="Annual average outdoor temp [°C]")
    T_amp:     float = Field(11.5,  description="Annual temperature amplitude [°C]")
    RH_avg:    float = Field(65.0,  description="Annual average RH [%]")
    T_sup:     float = Field(13.0)
    T_zone:    float = Field(24.0)
    RH_zone:   float = Field(50.0)
    Q_vol:     float = Field(8000.0)
    pct_fresh: float = Field(40.0)

class StepRequest(BaseModel):
    T_zone: float = Field(24.0, description="Current Zone Temperature [°C]")
    RH_zone: float = Field(50.0, description="Current Zone RH [%]")
    T_ext: float = Field(34.0)
    RH_ext: float = Field(50.0)
    pct_fresh: float = Field(40.0)
    Q_vol: float = Field(8000.0)
    T_sup: float = Field(13.0)
    fan_eta: float = Field(0.7)
    dp_fan: float = Field(600.0)
    Q_load_sensible: float = Field(35000.0, description="Sensible load [W]")
    Q_load_latent: float = Field(15000.0, description="Latent load [W]")
    dt: float = Field(0.5, description="Time step [seconds]")


def air_state_to_dict(s: AirState) -> dict:
    return {
        "T":   round(s.T, 2),
        "W":   round(s.W * 1000, 3),   # g/kg for UI
        "W_kg": round(s.W, 6),          # kg/kg for calcs
        "h":   round(s.h, 2),
        "RH":  round(s.RH, 1),
        "Tw":  round(s.Tw, 2),
        "Td":  round(s.Td, 2),
        "v":   round(s.v, 4),
        "rho": round(s.rho, 4),
    }


def sim_result_to_dict(r: SimulationResult) -> dict:
    return {
        "states": {
            "outdoor": air_state_to_dict(r.outdoor),
            "mixed":   air_state_to_dict(r.mixed),
            "supply":  air_state_to_dict(r.supply),
            "zone":    air_state_to_dict(r.zone),
        },
        "energy": {
            "Q_sensible": round(r.Q_sensible, 2),
            "Q_latent":   round(r.Q_latent, 2),
            "Q_total":    round(r.Q_total, 2),
            "W_fan":      round(r.W_fan, 3),
            "COP":        round(r.COP, 2),
            "SHF":        round(r.SHF, 3),
            "delta_h":    round(r.delta_h, 2),
        },
        "flow": {
            "mdot":  round(r.mdot, 4),
            "Q_vol": round(r.Q_vol, 0),
        },
        "comfort": {
            "category": r.comfort_cat,
        },
    }


# ─── Endpoints ────────────────────────────────────────────────────────────────

@app.get("/", tags=["Health"])
def root():
    return {"status": "online", "platform": "CTA-SIM PRO v3.0", "author": "TLILI SOULAYMEN"}


@app.get("/health", tags=["Health"])
def health():
    return {"status": "ok"}


@app.post("/api/simulate", tags=["Simulation"])
def api_simulate(req: SimRequest):
    """
    Full AHU psychrometric simulation.
    Returns all 4 air states + complete energy balance.
    """
    r = simulate(
        T_ext=req.T_ext, RH_ext=req.RH_ext,
        pct_fresh=req.pct_fresh, Q_vol=req.Q_vol,
        T_sup=req.T_sup, T_zone=req.T_zone, RH_zone=req.RH_zone,
        fan_eta=req.fan_eta, dp_fan=req.dp_fan,
    )
    return sim_result_to_dict(r)


@app.post("/api/annual", tags=["Simulation"])
def api_annual(req: AnnualRequest):
    """
    Annual 8760-hour energy simulation.
    Returns monthly kWh broken down by mode.
    """
    result = annual_profile(
        T_avg=req.T_avg, T_amp=req.T_amp, RH_avg=req.RH_avg,
        T_sup=req.T_sup, T_zone=req.T_zone, RH_zone=req.RH_zone,
        Q_vol=req.Q_vol, pct_fresh=req.pct_fresh,
    )
    return result


@app.post("/api/daily", tags=["Simulation"])
def api_daily(req: SimRequest):
    """
    24-hour zone temperature profile using 1st-order thermal model.
    """
    result = daily_profile(
        T_ext=req.T_ext, RH_ext=req.RH_ext,
        T_sup=req.T_sup, T_zone=req.T_zone, RH_zone=req.RH_zone,
        Q_vol=req.Q_vol, pct_fresh=req.pct_fresh,
    )
    return result


@app.post("/api/step", tags=["Simulation"])
def api_step(req: StepRequest):
    """
    Advances the dynamic simulation by `dt` seconds using physical thermal mass equations.
    """
    # Simulate to find supply state based on current zone state
    r = simulate(
        T_ext=req.T_ext, RH_ext=req.RH_ext,
        pct_fresh=req.pct_fresh, Q_vol=req.Q_vol,
        T_sup=req.T_sup, T_zone=req.T_zone, RH_zone=req.RH_zone,
        fan_eta=req.fan_eta, dp_fan=req.dp_fan
    )
    
    Q_load_total_kW = (req.Q_load_sensible + req.Q_load_latent) / 1000.0
    if Q_load_total_kW > 0:
        SHF = req.Q_load_sensible / (req.Q_load_sensible + req.Q_load_latent)
    else:
        SHF = 1.0

    # Step the zone state
    new_T, new_W = step_zone_state(
        T_zone=req.T_zone,
        W_zone=r.zone.W,
        Q_load_total=Q_load_total_kW,
        SHF=SHF,
        mdot=r.mdot,
        T_sup=r.supply.T,
        W_sup=r.supply.W,
        dt=req.dt
    )

    new_RH = relative_humidity_from_W(new_T, new_W)

    return {
        "new_zone": {
            "T": round(new_T, 4),
            "RH": round(new_RH, 2),
            "W": round(new_W * 1000, 3)
        },
        "simulation": sim_result_to_dict(r)
    }


@app.get("/api/psychro/saturation", tags=["Psychrometrics"])
def api_saturation(
    T_min: float = Query(-5.0),
    T_max: float = Query(50.0),
    step:  float = Query(0.5),
):
    """
    Returns the saturation curve data for the psychrometric chart.
    """
    points = []
    T = T_min
    while T <= T_max:
        W = humidity_ratio(T, 100.0) * 1000  # g/kg
        points.append({"T": round(T, 1), "W": round(W, 3)})
        T += step
    return {"saturation_curve": points}


@app.get("/api/psychro/rh_lines", tags=["Psychrometrics"])
def api_rh_lines(
    rh_values: str = Query("10,20,30,40,50,60,70,80,90,100"),
    T_min: float = Query(-5.0),
    T_max: float = Query(50.0),
    step:  float = Query(1.0),
):
    """
    Returns constant-RH iso-lines for the psychrometric chart.
    """
    rh_list = [float(x) for x in rh_values.split(",")]
    lines = {}
    for rh in rh_list:
        pts = []
        T = T_min
        while T <= T_max:
            W = humidity_ratio(T, rh) * 1000
            pts.append({"T": round(T, 1), "W": round(W, 3)})
            T += step
        lines[str(int(rh))] = pts
    return {"rh_lines": lines}


@app.get("/api/psychro/enthalpy_lines", tags=["Psychrometrics"])
def api_enthalpy_lines(
    h_values: str = Query("10,20,30,40,50,60,70,80,90,100"),
    T_min: float = Query(-5.0),
    T_max: float = Query(50.0),
):
    """
    Returns constant-enthalpy iso-lines.
    """
    h_list = [float(x) for x in h_values.split(",")]
    lines = {}
    for h_val in h_list:
        pts = []
        T = T_min
        while T <= T_max:
            # W from h = Cpa*T + W*(Hfg + Cpw*T)
            denom = 2501.0 + 1.86 * T
            if denom > 0:
                W_h = (h_val - 1.006 * T) / denom
                if 0 <= W_h <= 0.028:
                    pts.append({"T": round(T, 1), "W": round(W_h * 1000, 3)})
            T += 0.5
        lines[str(int(h_val))] = pts
    return {"enthalpy_lines": lines}


@app.get("/api/point", tags=["Psychrometrics"])
def api_point(T: float = Query(...), RH: float = Query(...)):
    """
    Calculate all psychrometric properties for a single point (T, RH).
    """
    state = AirState.from_T_RH(T, RH)
    return air_state_to_dict(state)


@app.get("/api/comfort/ashrae55", tags=["Comfort"])
def api_comfort_ashrae55(T_zone: float = Query(24.0), RH_zone: float = Query(50.0)):
    """
    Evaluate thermal comfort vs ASHRAE 55 / EN 15251 categories.
    """
    W_zone = humidity_ratio(T_zone, RH_zone)
    h_zone = enthalpy(T_zone, W_zone)
    Tw_zone = wet_bulb(T_zone, RH_zone)

    # PMV approximation (Fanger) — simplified for sedentary 1.1 Met, 0.5 Clo
    PMV_approx = 0.303 * math.exp(-0.036 * 1.1) + 0.028
    PMV_approx *= (57.6 + 1.1 * 8.13 - 3.05e-3 * (5733 - 6.99 * 1.1 * 1.0 - W_zone * 1e3 * 1.33)
                   - 0.42 * (1.1 * 8.13 - 58.15) - 1.7e-5 * 1.1 * (5867 - W_zone * 1e3 * 1.33)
                   - 0.0014 * 1.1 * (34 - T_zone)
                   - 3.96e-8 * 1.0 * ((35.7 - 0.028 * 1.1)**4 - (T_zone + 273)**4)
                   - 1.0 * (35.7 - 0.028 * 1.1 - T_zone))
    PMV_clamped = max(-3.0, min(3.0, PMV_approx))
    PPD = 100 - 95 * math.exp(-0.03353 * PMV_clamped**4 - 0.2179 * PMV_clamped**2)

    cat = "I" if abs(PMV_clamped) <= 0.2 else ("II" if abs(PMV_clamped) <= 0.5 else ("III" if abs(PMV_clamped) <= 0.7 else "IV"))

    return {
        "T_zone": T_zone, "RH_zone": RH_zone,
        "W": round(W_zone * 1000, 2), "h": round(h_zone, 2), "Tw": round(Tw_zone, 2),
        "PMV": round(PMV_clamped, 2),
        "PPD": round(PPD, 1),
        "category": f"EN 15251 Cat. {cat}",
        "acceptable": abs(PMV_clamped) <= 0.7,
    }
