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
st.metric("UF_recommended (L)", f"{UF_recommended_L:.2f}")
if UF_deficit_L > 0.0:
    st.warning(f"UF_deficit: {UF_deficit_L:.2f} L — εξετάστε παράταση συνεδρίας ή split UF.")
# --- Actuals & Learning (post-session) ---
st.markdown("---")
st.subheader("📈 Actuals & learning (post-session)")
cA, cB, cC, cD = st.columns(4)
with cA:
    UF_actual_total = st.number_input("UF_actual_total (L)", value=0.0, step=0.1, format="%.2f")
with cB:
    duration_actual_min = st.number_input("Διάρκεια_actual (min)", value=duration_min, step=1)
with cC:
    outcome_last = st.selectbox("Outcome_last (0=OK,1=hypotension)", [0,1], index=0)
with cD:
    gamma0_offset_current = st.number_input("γ0_offset_current", value=0.0, step=0.1, format="%.2f")

UF_actual_net = None
if UF_actual_total > 0:
    UF_actual_net = UF_actual_total - rinseback_L - iv_L - intake_L

r_used_last = None
if (UF_actual_net is not None) and duration_actual_min > 0 and weight > 0:
    r_used_last = UF_actual_net * 1000.0 * 60.0 / (weight * duration_actual_min)

def sigmoid(x): 
    import math
    return 1.0/(1.0 + math.exp(-x))

p_old_last = None
if r_used_last is not None:
    lin_old = (gamma0 +
               gamma1 * r_used_last +
               g_meds*meds_recent + g_tmp*tmp_slope + g_vp*vp_trend +
               g_age*max(0.0, (age - 60.0)/10.0) + g_dm*dm + g_press*dP_atm_10hPa +
               gamma0_offset_current)
    p_old_last = sigmoid(lin_old)

p_target = ( (tau_override if tau_override>0 else tau_default) / 200.0 ) if outcome_last == 0 else min(0.8, 2*((tau_override if tau_override>0 else tau_default)/100.0))
delta_logit = None
if (p_old_last is not None) and (0 < p_old_last < 1):
    import math
    delta_logit = math.log(p_target/(1-p_target)) - math.log(p_old_last/(1-p_old_last))

alpha = st.number_input("α (learning rate)", value=0.2, step=0.05, min_value=0.0, max_value=1.0)
gamma0_offset_updated = gamma0_offset_current
if delta_logit is not None:
    gamma0_offset_updated = gamma0_offset_current + alpha * delta_logit

# --- Next session planning ---
import math
logit_tau = math.log(((tau_override if tau_override>0 else tau_default)/100.0)/(1 - ((tau_override if tau_override>0 else tau_default)/100.0)))
lin_terms_next = (gamma0 + gamma0_offset_updated + g_meds*meds_recent + g_tmp*tmp_slope +
                  g_vp*vp_trend + g_age*max(0.0,(age-60.0)/10.0) + g_dm*dm + g_press*dP_atm_10hPa)
r_max_next = (logit_tau - lin_terms_next) / gamma1 if gamma1 != 0 else float("nan")
r_max_bounded_base = min(max(((logit_tau - (gamma0 + g_meds*meds_recent + g_tmp*tmp_slope + g_vp*vp_trend + g_age*max(0.0,(age-60.0)/10.0) + g_dm*dm + g_press*dP_atm_10hPa)) / gamma1) if gamma1!=0 else float('nan'), rmin), rmax)
r_max_next_bounded = min(max(r_max_next, rmin), rmax)
r_max_next_capped = min(r_max_next_bounded, 1.15 * r_max_bounded_base)  # +15% cap
guard_mult = (0.85 if (tmp_slope > 2.0 or vp_trend > 1.5) else 1.0)  # ίδιο guard με πάνω, προσαρμόσ’το αν άλλαξες τιμές
r_max_next_dyn = r_max_next_capped * guard_mult

UF_cap_next_L = r_max_next_dyn * (duration_min/60.0) * weight / 1000.0
extra_minutes = 0.0
if (idwg + intake_L - rinseback_L - iv_L) - min(UF_cap_L, idwg + intake_L - rinseback_L - iv_L) > 0 and r_max_next_dyn > 0:
    UF_deficit_L = (idwg + intake_L - rinseback_L - iv_L) - min(UF_cap_L, idwg + intake_L - rinseback_L - iv_L)
    extra_minutes = UF_deficit_L * 1000.0 / (r_max_next_dyn * weight) * 60.0

def round_up_step(x, step):
    return int(math.ceil(x/step) * step)

recommended_total_minutes = round_up_step(duration_min + max(0.0, extra_minutes), 5)

st.markdown("### 🔄 Next session planning")
cN1, cN2, cN3, cN4 = st.columns(4)
cN1.metric("r_max_next (dyn)", f"{r_max_next_dyn:.2f}")
cN2.metric("UF_cap_next (L)", f"{UF_cap_next_L:.2f}")
cN3.metric("Extra minutes needed", f"{extra_minutes:.0f} min")
cN4.metric("Recommended total minutes", f"{recommended_total_minutes} min")

# --- Export snapshot JSON ---
st.markdown("---")
import json
if st.button("📤 Export snapshot (JSON)"):
    data = {
        "tau": (tau_override if tau_override>0 else tau_default),
        "UF_cap_L": UF_cap_L, "UF_needed_L": UF_needed_L, "UF_recommended_L": UF_recommended_L,
        "UF_actual_total": UF_actual_total, "UF_actual_net": UF_actual_net,
        "r_used_last": r_used_last, "p_old_last": p_old_last, "p_target": p_target,
        "gamma0_offset_updated": gamma0_offset_updated,
        "r_max_next_dyn": r_max_next_dyn, "UF_cap_next_L": UF_cap_next_L,
        "extra_minutes": extra_minutes, "recommended_total_minutes": recommended_total_minutes
    }
    st.download_button("Download session.json", data=json.dumps(data, indent=2), file_name="session.json", mime="application/json")

st.caption("⚠️ Prototype — validate clinically before routine use")


