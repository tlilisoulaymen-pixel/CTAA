"""
CTA-SIM PRO — Psychrometric Engine
Based on ASHRAE Fundamentals 2021, Chapter 1
Standard atmosphere: 101.325 kPa
"""

import math
from dataclasses import dataclass

# ─── Constants ────────────────────────────────────────────────────────────────
P_ATM = 101.325      # kPa — standard atmospheric pressure (sea level)
C_PA  = 1.006        # kJ/(kg·K) — specific heat dry air
C_PW  = 1.86         # kJ/(kg·K) — specific heat water vapour
H_FG  = 2501.0       # kJ/kg — enthalpy of vaporisation at 0°C
EPS   = 0.62198      # ratio molecular mass water/air


# ─── Core psychrometric functions ─────────────────────────────────────────────

def psat(T: float) -> float:
    """Saturation pressure of water vapour [kPa] — Buck equation (±0.04%)
    Valid: -40°C to 60°C
    """
    if T >= 0:
        return 0.61121 * math.exp((18.678 - T / 234.5) * (T / (257.14 + T)))
    else:
        # Ice surface
        return 0.61115 * math.exp((23.036 - T / 333.7) * (T / (279.82 + T)))


def humidity_ratio(T: float, RH: float) -> float:
    """Humidity ratio W [kg_w/kg_da] from dry-bulb T [°C] and RH [%]"""
    pv = (RH / 100.0) * psat(T)
    return EPS * pv / (P_ATM - pv)


def humidity_ratio_from_wb(T: float, Tw: float) -> float:
    """Humidity ratio W from dry-bulb T and wet-bulb Tw [°C] — Sprung formula"""
    Ws_wb = humidity_ratio(Tw, 100.0)
    return Ws_wb - 6.6e-4 * (1 + 0.00115 * Tw) * (T - Tw)


def enthalpy(T: float, W: float) -> float:
    """Specific enthalpy h [kJ/kg_da]"""
    return C_PA * T + W * (H_FG + C_PW * T)


def relative_humidity_from_W(T: float, W: float) -> float:
    """RH [%] from dry-bulb T [°C] and humidity ratio W [kg/kg]"""
    pv = W * P_ATM / (EPS + W)
    return min(100.0, max(0.0, (pv / psat(T)) * 100.0))


def dew_point(T: float, RH: float) -> float:
    """Dew-point temperature [°C] — Magnus formula"""
    a, b = 17.27, 237.3
    alpha = math.log(max(RH / 100.0, 1e-9)) + a * T / (b + T)
    return b * alpha / (a - alpha)


def wet_bulb(T: float, RH: float, tol: float = 1e-5, max_iter: int = 60) -> float:
    """Wet-bulb temperature [°C] — iterative Newton-Raphson"""
    W_target = humidity_ratio(T, RH)
    Tw = T - 8.0  # initial guess
    for _ in range(max_iter):
        W_calc = humidity_ratio_from_wb(T, Tw)
        dW_dTw = (humidity_ratio_from_wb(T, Tw + 0.001) - W_calc) / 0.001
        delta = (W_calc - W_target) / (dW_dTw if abs(dW_dTw) > 1e-12 else 1e-12)
        Tw -= delta
        if abs(delta) < tol:
            break
    return Tw


def specific_volume(T: float, W: float) -> float:
    """Specific volume v [m³/kg_da] — ideal gas law"""
    return 0.2871 * (T + 273.15) * (1 + 1.6078 * W) / P_ATM


def air_density(T: float, W: float) -> float:
    """Moist air density [kg/m³]"""
    return (1 + W) / specific_volume(T, W)


# ─── AHU Process Calculations ─────────────────────────────────────────────────

@dataclass
class AirState:
    T: float        # dry-bulb [°C]
    W: float        # humidity ratio [kg/kg]
    h: float        # enthalpy [kJ/kg_da]
    RH: float       # relative humidity [%]
    Tw: float       # wet-bulb [°C]
    Td: float       # dew-point [°C]
    v: float        # specific volume [m³/kg_da]
    rho: float      # density [kg/m³]

    @classmethod
    def from_T_RH(cls, T: float, RH: float) -> "AirState":
        W = humidity_ratio(T, RH)
        h = enthalpy(T, W)
        Tw = wet_bulb(T, RH)
        Td = dew_point(T, RH)
        v = specific_volume(T, W)
        rho = air_density(T, W)
        return cls(T=T, W=W, h=h, RH=RH, Tw=Tw, Td=Td, v=v, rho=rho)

    @classmethod
    def from_T_W(cls, T: float, W: float) -> "AirState":
        RH = relative_humidity_from_W(T, W)
        h = enthalpy(T, W)
        Tw = wet_bulb(T, RH)
        Td = dew_point(T, RH) if RH > 0.1 else T - 30
        v = specific_volume(T, W)
        rho = air_density(T, W)
        return cls(T=T, W=W, h=h, RH=RH, Tw=Tw, Td=Td, v=v, rho=rho)


@dataclass
class SimulationResult:
    # States
    outdoor:  AirState
    mixed:    AirState
    supply:   AirState
    zone:     AirState
    # Energy balance
    Q_sensible:  float   # kW
    Q_latent:    float   # kW
    Q_total:     float   # kW
    W_fan:       float   # kW
    COP:         float
    SHF:         float   # Sensible Heat Factor
    delta_h:     float   # kJ/kg
    # Flow
    mdot:        float   # kg/s
    Q_vol:       float   # m³/h
    # Comfort
    comfort_cat: str


def simulate(
    T_ext: float,
    RH_ext: float,
    pct_fresh: float,   # % fresh air (0–100)
    Q_vol: float,       # m³/h total airflow
    T_sup: float,       # supply temperature [°C]
    T_zone: float,      # zone setpoint [°C]
    RH_zone: float,     # zone RH setpoint [%]
    fan_eta: float = 0.7,
    dp_fan: float = 600.0,  # Pa total pressure rise
) -> SimulationResult:
    """
    Full AHU simulation based on ASHRAE psychrometric processes.
    Returns complete energy balance and air states.
    """
    # ── States ──
    outdoor = AirState.from_T_RH(T_ext, RH_ext)
    zone    = AirState.from_T_RH(T_zone, RH_zone)

    # ── Mixing ──
    f = pct_fresh / 100.0  # fresh air fraction
    T_mix = f * T_ext + (1 - f) * T_zone
    W_mix = f * outdoor.W + (1 - f) * zone.W
    mixed = AirState.from_T_W(T_mix, W_mix)

    # ── Supply state (after coil) ──
    # W_sup constrained by saturation at T_sup (coil dehumidifies)
    W_sat_sup = humidity_ratio(T_sup, 100.0)
    W_sup = min(W_mix, W_sat_sup * 0.95)   # 95% saturation at coil ADP
    supply = AirState.from_T_W(T_sup, W_sup)

    # ── Mass flow ──
    rho_mean = (mixed.rho + supply.rho) / 2.0
    mdot = rho_mean * Q_vol / 3600.0   # kg/s

    # ── Energy balance ──
    delta_h = mixed.h - supply.h               # kJ/kg — cooling process
    Q_total = mdot * delta_h                   # kW
    Q_sensible = mdot * C_PA * (T_mix - T_sup) # kW
    Q_latent = Q_total - Q_sensible            # kW
    SHF = Q_sensible / Q_total if Q_total > 0.001 else 1.0

    # ── Fan power ──
    W_fan = (Q_vol / 3600.0) * dp_fan / (fan_eta * 1000.0)  # kW

    # ── COP (apparent) ──
    COP = Q_total / W_fan if W_fan > 0.001 else 99.0

    # ── Comfort category (EN 15251 / ASHRAE 55) ──
    delta_T_zone = abs(T_zone - 22.0)
    if delta_T_zone <= 1.0 and 40 <= RH_zone <= 60:
        comfort_cat = "Catégorie I (ISO)"
    elif delta_T_zone <= 2.0 and 35 <= RH_zone <= 65:
        comfort_cat = "Catégorie II (ISO)"
    elif delta_T_zone <= 3.0:
        comfort_cat = "Catégorie III (ISO)"
    else:
        comfort_cat = "Hors norme"

    return SimulationResult(
        outdoor=outdoor, mixed=mixed, supply=supply, zone=zone,
        Q_sensible=Q_sensible, Q_latent=Q_latent, Q_total=Q_total,
        W_fan=W_fan, COP=COP, SHF=SHF, delta_h=delta_h,
        mdot=mdot, Q_vol=Q_vol, comfort_cat=comfort_cat,
    )


def annual_profile(
    T_avg: float,
    T_amp: float,
    RH_avg: float,
    T_sup: float,
    T_zone: float,
    RH_zone: float,
    Q_vol: float,
    pct_fresh: float,
) -> dict:
    """
    Generate 8760-hour annual simulation profile.
    Uses Fourier approximation for outdoor T and RH.
    Returns monthly aggregated energy [kWh] and operating hours per mode.
    """
    import numpy as np

    hours = np.arange(8760)
    # Day-of-year angle
    doy = hours / 24.0
    hour_of_day = hours % 24

    # Sinusoidal outdoor temp: peak in July (day 198), daily swing ±5°C
    T_annual = T_avg + T_amp * np.sin(2 * math.pi * (doy - 80) / 365)
    T_daily  = T_annual + 5.0 * np.sin(2 * math.pi * (hour_of_day - 14) / 24)

    # RH inversely correlated with T
    RH_annual = RH_avg - 15.0 * np.sin(2 * math.pi * (doy - 80) / 365)
    RH_hourly = np.clip(RH_annual + 10.0 * np.cos(2 * math.pi * (hour_of_day - 14) / 24), 10, 100)

    months = [0,744,1416,2160,2880,3624,4368,5088,5832,6552,7296,8016,8760]
    month_names = ['Jan','Fév','Mar','Avr','Mai','Jun','Jul','Aoû','Sep','Oct','Nov','Déc']

    monthly_cool = []
    monthly_heat = []
    monthly_vent = []
    mode_hours = {'cooling': 0, 'heating': 0, 'freecooling': 0, 'vent': 0}

    for m in range(12):
        s, e = months[m], months[m+1]
        Ts = T_daily[s:e]
        RHs = RH_hourly[s:e]
        cool_kwh = heat_kwh = vent_kwh = 0.0
        for T_h, RH_h in zip(Ts, RHs):
            try:
                r = simulate(float(T_h), float(RH_h), pct_fresh, Q_vol, T_sup, T_zone, RH_zone)
                if r.Q_total > 0.5:
                    cool_kwh += r.Q_total
                    mode_hours['cooling'] += 1
                elif r.Q_total < -0.5:
                    heat_kwh += abs(r.Q_total)
                    mode_hours['heating'] += 1
                elif float(T_h) < T_zone and r.Q_total >= 0:
                    cool_kwh += r.Q_total * 0.2
                    mode_hours['freecooling'] += 1
                else:
                    mode_hours['vent'] += 1
                vent_kwh += r.W_fan
            except Exception:
                vent_kwh += 2.0
        monthly_cool.append(round(cool_kwh, 1))
        monthly_heat.append(round(heat_kwh, 1))
        monthly_vent.append(round(vent_kwh, 1))

    total = sum(mode_hours.values()) or 1
    return {
        'months': month_names,
        'cooling': monthly_cool,
        'heating': monthly_heat,
        'ventilation': monthly_vent,
        'mode_pct': {k: round(v / total * 100, 1) for k, v in mode_hours.items()},
    }


def daily_profile(
    T_ext: float,
    RH_ext: float,
    T_sup: float,
    T_zone: float,
    RH_zone: float,
    Q_vol: float,
    pct_fresh: float,
    tau: float = 3.0,   # zone thermal time constant [h]
) -> dict:
    """
    24-hour zone temperature profile using 1st-order thermal model.
    Returns hourly T_zone, T_ext, Q_total arrays.
    """
    hours = list(range(24))
    T_zones, T_exts, Q_loads = [], [], []
    Tz = T_zone  # initial zone temp

    for h in hours:
        T_ext_h = T_ext + (T_ext * 0.18) * math.sin((h - 14) * math.pi / 12)
        RH_h = max(10, min(100, RH_ext - 8 * math.sin((h - 14) * math.pi / 12)))
        Q_sol = max(0.0, math.sin((h - 6) * math.pi / 12)) * 3.0

        try:
            r = simulate(T_ext_h, RH_h, pct_fresh, Q_vol, T_sup, T_zone, RH_zone)
            Q_hvac = r.Q_total
        except Exception:
            Q_hvac = 0.0

        # 1st-order ODE: τ dTz/dt = T_ext_h*UA_coeff + Q_sol - Q_hvac - UA*(Tz-T_zone_sp)
        dTz = (1.0 / tau) * (
            T_ext_h * 0.10
            + Q_sol * 0.06
            - Q_hvac * 0.05
            - (Tz - T_zone) * 0.45
        )
        Tz = round(Tz + dTz, 3)

        T_zones.append(Tz)
        T_exts.append(round(T_ext_h, 2))
        Q_loads.append(round(Q_hvac, 2))

    return {'hours': hours, 'T_zone': T_zones, 'T_ext': T_exts, 'Q_load': Q_loads,
            'T_setpoint': T_zone, 'comfort_hi': T_zone + 1.5, 'comfort_lo': T_zone - 1.5}


# ─── Dynamic Zone Simulation ──────────────────────────────────────────────────

BUILDING_VOLUME = 7000.0  # m³
BUILDING_HEAT_CAPACITY = 2000000.0  # kJ/K

def step_zone_state(
    T_zone: float,
    W_zone: float,
    Q_load_total: float,    # kW
    SHF: float,             # Sensible Heat Factor [0.0 - 1.0]
    mdot: float,            # kg/s (supply air mass flow)
    T_sup: float,           # °C
    W_sup: float,           # kg/kg
    dt: float,              # seconds
    V_bldg: float = BUILDING_VOLUME,
    C_bldg: float = BUILDING_HEAT_CAPACITY
) -> tuple[float, float]:
    """
    Physically simulates the zone temperature and humidity ratio after a time step `dt`.
    Returns (new_T_zone, new_W_zone).
    """
    Q_load_sensible = Q_load_total * SHF
    Q_load_latent = Q_load_total * (1.0 - SHF)

    # 1. Temperature Step
    # Sensible cooling provided to the zone [kW]
    Q_supply_sensible = mdot * C_PA * (T_zone - T_sup)
    
    # ODE: dT/dt = (Q_load_sensible - Q_supply_sensible) / C_bldg
    new_T_zone = T_zone + dt * (Q_load_sensible - Q_supply_sensible) / C_bldg

    # 2. Humidity Step
    # Latent load water generation [kg/s]
    H_fg_zone = H_FG + C_PW * T_zone
    mdot_load_water = Q_load_latent / H_fg_zone if H_fg_zone > 0 else 0.0

    # Mass of dry air in the building
    rho_zone = air_density(T_zone, W_zone)
    m_da_bldg = V_bldg * rho_zone

    # Current mass of water
    m_w_bldg = m_da_bldg * W_zone

    # ODE: dm_w/dt = mdot * W_sup + mdot_load_water - mdot * W_zone
    dm_w_dt = mdot * W_sup + mdot_load_water - mdot * W_zone
    new_m_w_bldg = m_w_bldg + dt * dm_w_dt

    new_W_zone = max(0.0, new_m_w_bldg / m_da_bldg)

    return new_T_zone, new_W_zone
