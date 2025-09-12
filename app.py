import math
import datetime as dt
import streamlit as st
import json

st.set_page_config(page_title="Individualized UF Helper", page_icon="🩺", layout="wide")

st.title("🩺 Individualized UF Helper (Bayesian/Logistic Prototype)")
st.caption("v0.1 • Mirrors the Excel v4m logic with per-session inputs")

# --- Defaults / coefficients ---
with st.sidebar:
    st.header("Model coefficients & thresholds")
    gamma0 = st.number_input("γ0 (intercept)", value=-2.6, step=0.1, format="%.3f")
    gamma1 = st.number_input("γ1 (per mL/kg/h UF)", value=0.10, step=0.01, format="%.3f")
    g_meds = st.number_input("γ_meds (antihypertensives <6h)", value=0.25, step=0.01, format="%.3f")
    g_tmp  = st.number_input("γ_tmp (TMP slope /h)", value=0.10, step=0.01, format="%.3f")
    g_vp   = st.number_input("γ_vp (VP trend /h)", value=0.08, step=0.01, format="%.3f")
    g_age  = st.number_input("γ_age (per decade >60)", value=0.12, step=0.01, format="%.3f")
    g_dm   = st.number_input("γ_dm (DM=1)", value=0.15, step=0.01, format="%.3f")
    g_press= st.number_input("γ_press (per 10 hPa drop)", value=0.07, step=0.01, format="%.3f")
    tau_default = st.number_input("Target hypotension risk τ (%)", value=20.0, min_value=1.0, max_value=80.0, step=1.0)
    rmin = st.number_input("r_max_min (mL/kg/h)", value=0.5, step=0.1)
    rmax = st.number_input("r_max_max (mL/kg/h)", value=13.0, step=0.5)
    tmp_thr = st.number_input("TMP_slope_threshold (mmHg/h)", value=2.0, step=0.5)
    vp_thr  = st.number_input("VP_trend_threshold (mmHg/h)", value=1.5, step=0.5)
    safety_mult = st.number_input("safety_multiplier_if_exceeded", value=0.85, step=0.01, min_value=0.1, max_value=1.0)
    round_step = st.number_input("Round minutes step", value=5, step=1, min_value=1, max_value=30)

st.subheader("Patient & session inputs")
c1, c2, c3 = st.columns([1.2,1,1])
with c1:
    session_dt = st.text_input("Ημερομηνία συνεδρίας (YYYY-MM-DD HH:MM)", value=dt.datetime.now().strftime("%Y-%m-%d %H:%M"))
    patient_id = st.text_input("Patient_ID", value="Case01")
    age = st.number_input("Ηλικία (έτη)", value=72, step=1)
    weight = st.number_input("Βάρος (kg)", value=72.0, step=0.1, format="%.2f")
with c2:
    duration_min = st.number_input("Διάρκεια (min, planned)", value=240, step=5)
    idwg = st.number_input("IDWG (kg)", value=2.9, step=0.1)
    intake_L = st.number_input("Ενδοσυνεδριακή πρόσληψη (L)", value=0.40, step=0.05, format="%.2f")
    rinseback_L = st.number_input("Rinseback (L)", value=0.36, step=0.01, format="%.2f")
with c3:
    iv_L = st.number_input("IV_infusions (L)", value=0.0, step=0.05, format="%.2f")
    meds_recent = st.selectbox("Αντιυπερτασικά <6h", [0,1], index=1)
    dm = st.selectbox("ΣΔ (0/1)", [0,1], index=0)
    dP_atm_10hPa = st.number_input("ΔP_atm_10hPa (units)", value=0.0, step=0.1, format="%.2f")

c4, c5, c6 = st.columns(3)
with c4:
    tmp_slope = st.number_input("TMP_slope (mmHg/h)", value=0.0, step=0.5)
with c5:
    vp_trend = st.number_input("VP_trend (mmHg/h)", value=0.0, step=0.5)
with c6:
    tau_override = st.number_input("Τ% (override, optional)", value=0.0, step=1.0)

# --- Υπολογισμοί ---
age_over60_dec = max(0.0, (age - 60.0)/10.0)
tau = tau_override if tau_override > 0 else tau_default
logit_tau = math.log((tau/100.0)/(1 - (tau/100.0)))
lin_terms = (gamma0 + g_meds*meds_recent + g_tmp*tmp_slope + g_vp*vp_trend
             + g_age*age_over60_dec + g_dm*dm + g_press*dP_atm_10hPa)
r_max = (logit_tau - lin_terms) / gamma1 if gamma1 != 0 else float("nan")
r_max_bounded = min(max(r_max, rmin), rmax)
guard_mult = safety_mult if (tmp_slope > tmp_thr or vp_trend > vp_thr) else 1.0
r_max_dyn = r_max_bounded * guard_mult

UF_cap_L = r_max_dyn * (duration_min/60.0) * weight / 1000.0
UF_needed_L = idwg + intake_L - rinseback_L - iv_L
UF_recommended_L = min(UF_cap_L, UF_needed_L)
UF_deficit_L = max(0.0, UF_needed_L - UF_recommended_L)

st.markdown("---")
st.subheader("🧮 Current plan")
st.metric("r_max (mL/kg/h)", f"{r_max_dyn:.2f}")
st.metric("UF_cap_net (L)", f"{UF_cap_L:.2f}")
st.metric("UF_needed_net (L)", f"{UF_needed_L:.2f}")
st.
