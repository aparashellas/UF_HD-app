import math
import datetime as dt
import streamlit as st
import json

st.set_page_config(page_title="Individualized UF Helper", page_icon="🩺", layout="wide")
st.title("🩺 Individualized UF Helper")
st.caption("v0.2 • UF safety + Overhydration balance • Προσθήκες: BP pre/post, συμπτώματα, EF/αρρυθμίες, TMP/VP start–end, σύσταση διαλύματος, P_overhydration_risk")

# ============ SIDEBAR: Συντελεστές & thresholds ============
with st.sidebar:
    st.header("Hypotension model (logistic)")
    gamma0 = st.number_input("γ0 (intercept)", value=-2.6, step=0.1, format="%.3f")
    gamma1 = st.number_input("γ1 (per mL/kg/h UF)", value=0.10, step=0.01, format="%.3f")
    g_meds = st.number_input("γ_meds (antihypertensives <6h)", value=0.25, step=0.01, format="%.3f")
    g_tmp  = st.number_input("γ_tmp (TMP slope /h)", value=0.10, step=0.01, format="%.3f")
    g_vp   = st.number_input("γ_vp (VP trend /h)", value=0.08, step=0.01, format="%.3f")
    g_age  = st.number_input("γ_age (per decade >60)", value=0.12, step=0.01, format="%.3f")
    g_dm   = st.number_input("γ_dm (DM=1)", value=0.15, step=0.01, format="%.3f")
    g_press= st.number_input("γ_press (per 10 hPa drop)", value=0.07, step=0.01, format="%.3f")
    tau_default = st.number_input("Target hypotension risk τ (%)", value=20.0, min_value=1.0, max_value=80.0, step=1.0)

    st.divider()
    st.header("Safety bounds & guards")
    rmin = st.number_input("r_min (mL/kg/h)", value=0.5, step=0.1)
    rmax = st.number_input("r_max (mL/kg/h)", value=13.0, step=0.5)
    tmp_thr = st.number_input("TMP_slope_threshold (mmHg/h)", value=2.0, step=0.5)
    vp_thr  = st.number_input("VP_trend_threshold (mmHg/h)", value=1.5, step=0.5)
    bp_drop_thr = st.number_input("SBP drop threshold (%)", value=20.0, step=1.0)
    safety_mult = st.number_input("safety_multiplier_if_exceeded", value=0.85, step=0.01, min_value=0.1, max_value=1.0)
    round_step = st.number_input("Round minutes step", value=5, step=1, min_value=1, max_value=30)

    st.divider()
    st.header("Overhydration model (logistic)")
    beta0 = st.number_input("β0 (intercept)", value=-2.2, step=0.1, format="%.2f")
    b_OH  = st.number_input("β_OH per L", value=0.55, step=0.05, format="%.2f")
    b_dysp= st.number_input("β_dyspnea", value=0.70, step=0.05, format="%.2f")
    b_edm = st.number_input("β_edema", value=0.35, step=0.05, format="%.2f")
    b_ef  = st.number_input("β_low EF (<40%)", value=0.40, step=0.05, format="%.2f")
    b_af  = st.number_input("β_recent AF/arrhythmia", value=0.30, step=0.05, format="%.2f")
    omega_target = st.number_input("Target overhydration risk ω (%)", value=10.0, min_value=1.0, max_value=50.0, step=1.0)

# ============ TABS ============
tab_plan, tab_learn = st.tabs(["🧮 Plan", "📈 Actuals & Learning"])

with tab_plan:
    st.subheader("Patient & session inputs")

    # ---- Βασικά inputs
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
        iv_L = st.number_input("IV infusions (L)", value=0.0, step=0.05, format="%.2f")
        meds_recent = st.selectbox("Αντιυπερτασικά <6h", [0,1], index=1)
        dm = st.selectbox("ΣΔ (0/1)", [0,1], index=0)
        dP_atm_10hPa = st.number_input("ΔP_atm_10hPa (units)", value=0.0, step=0.1, format="%.2f")

    # ---- Αιμοδυναμικά & συμπτώματα
    st.markdown("### Αιμοδυναμικά & συμπτώματα")
    cbp1, cbp2, cbp3 = st.columns(3)
    with cbp1:
        sbp_pre = st.number_input("SBP pre (mmHg)", value=150, step=1)
        dbp_pre = st.number_input("DBP pre (mmHg)", value=80, step=1)
    with cbp2:
        sbp_post = st.number_input("SBP post (mmHg)", value=130, step=1)
        dbp_post = st.number_input("DBP post (mmHg)", value=75, step=1)
    with cbp3:
        bp_drop_pct = 0.0 if sbp_pre <= 0 else max(0.0, (sbp_pre - sbp_post) * 100.0 / sbp_pre)
        st.metric("% πτώση SBP", f"{bp_drop_pct:.1f}%")

    symp_cols = st.columns(4)
    with symp_cols[0]:
        s_headache = st.checkbox("Κεφαλαλγία", value=False)
    with symp_cols[1]:
        s_cramps = st.checkbox("Κράμπες", value=False)
    with symp_cols[2]:
        s_gi = st.checkbox("Γ/Ε συμπτώματα", value=False)
    with symp_cols[3]:
        s_syncope = st.checkbox("Συγκοπή/λιποθυμία", value=False)
    hypo_symptoms_any = 1 if any([s_headache, s_cramps, s_gi, s_syncope]) else 0

    # ---- Καρδιακές παράμετροι
    st.markdown("### Καρδιακές παράμετροι")
    cc1, cc2, cc3 = st.columns(3)
    with cc1:
        ef_percent = st.number_input("EF (%)", value=55, step=1, min_value=10, max_value=80)
    with cc2:
        arrhythmia = st.checkbox("Αρρυθμίες (γενικά)", value=False)
    with cc3:
        af_recent = st.checkbox("Παροξ. κολπική μαρμαρυγή (recent)", value=False)
    low_ef = 1 if ef_percent < 40 else 0
    arrhythmia_any = 1 if (arrhythmia or af_recent) else 0

    # ---- Παράμετροι μηχανήματος
    st.markdown("### Μηχάνημα αιμοκάθαρσης")
    cm1, cm2, cm3, cm4 = st.columns(4)
    with cm1:
        tmp_start = st.number_input("TMP start (mmHg)", value=80.0, step=1.0)
        vp_start  = st.number_input("VP start (mmHg)", value=120.0, step=1.0)
    with cm2:
        tmp_end   = st.number_input("TMP end (mmHg)", value=90.0, step=1.0)
        vp_end    = st.number_input("VP end (mmHg)", value=110.0, step=1.0)
    with cm3:
        hours = max(0.1, duration_min/60.0)
        tmp_slope = (tmp_end - tmp_start) / hours
        vp_trend  = (vp_end  - vp_start ) / hours
        st.metric("TMP_slope (mmHg/h)", f"{tmp_slope:.2f}")
        st.metric("VP_trend (mmHg/h)", f"{vp_trend:.2f}")
    with cm4:
        tmp_pct = 0.0 if tmp_start == 0 else (tmp_end - tmp_start) * 100.0 / tmp_start
        vp_pct  = 0.0 if vp_start  == 0 else (vp_end  - vp_start ) * 100.0 / vp_start
        st.metric("%Δ TMP", f"{tmp_pct:.1f}%")
        st.metric("%Δ VP", f"{vp_pct:.1f}%")

    # ---- Σύσταση διαλύματος
    st.markdown("### Σύσταση διαλύματος/μηχανήματος")
    cd1, cd2, cd3, cd4 = st.columns(4)
    with cd1:
        dial_Na = st.number_input("Na⁺ διαλύματος (mEq/L)", value=138, step=1)
    with cd2:
        dial_HCO3 = st.number_input("HCO₃⁻ (mEq/L)", value=32, step=1)
    with cd3:
        dial_cond = st.number_input("Αγωγιμότητα (mS/cm)", value=13.6, step=0.1, format="%.1f")
    with cd4:
        dial_K = st.number_input("K⁺ (mmol/L)", value=2.0, step=0.5, format="%.1f")
        dial_Ca = st.number_input("Ca²⁺ (mmol/L)", value=1.5, step=0.1, format="%.1f")

    # ---- Υπερυδάτωση / κλινική εικόνα
    st.markdown("### Υπερυδάτωση / Κλινική εικόνα")
    oh_cols = st.columns(4)
    with oh_cols[0]:
        OH_L = st.number_input("Overhydration estimate (L)", value=0.0, step=0.1, format="%.1f", help="BCM ή κλινική εκτίμηση καθαρής υπερυδάτωσης")
    with oh_cols[1]:
        dyspnea = st.checkbox("Δύσπνοια/οίδημα πνευμόνων", value=False)
    with oh_cols[2]:
        edema = st.checkbox("Περιφερικό οίδημα", value=False)
    with oh_cols[3]:
        chest_symp = st.checkbox("Θωρακικά συμπτώματα", value=False)  # προαιρετικό flag

    # ============ Υπολογισμοί "Plan" ============
    def sigmoid(x): 
        return 1.0/(1.0 + math.exp(-x))

    age_over60_dec = max(0.0, (age - 60.0)/10.0)
    tau = tau_default  # μπορεί να γίνει override με δικό πεδίο αν θες

    # Hypotension: logit target
    logit_tau = math.log((tau/100.0)/(1 - (tau/100.0)))
    lin_terms = (gamma0 + g_meds*meds_recent + g_tmp*tmp_slope + g_vp*vp_trend
                + g_age*age_over60_dec + g_dm*dm + g_press*dP_atm_10hPa)

    r_raw = (logit_tau - lin_terms) / gamma1 if gamma1 != 0 else float("nan")
    r_bounded = min(max(r_raw, rmin), rmax)

    # dynamic guard: αν υψηλό TMP/VP ή μεγάλη πτώση SBP ή συμπτώματα → κόφτης
    guard_hit = (tmp_slope > tmp_thr) or (vp_trend > vp_thr) or (bp_drop_pct >= bp_drop_thr) or (hypo_symptoms_any == 1)
    guard_mult = safety_mult if guard_hit else 1.0
    r_max_dyn = r_bounded * guard_mult

    UF_cap_L = r_max_dyn * (duration_min/60.0) * weight / 1000.0
    UF_needed_L = idwg + intake_L - rinseback_L - iv_L
    UF_recommended_L = min(UF_cap_L, UF_needed_L)
    UF_deficit_L = max(0.0, UF_needed_L - UF_recommended_L)

    st.markdown("---")
    st.subheader("🧮 Current plan")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("r_max (mL/kg/h)", f"{r_max_dyn:.2f}")
    m2.metric("UF_cap_net (L)", f"{UF_cap_L:.2f}")
    m3.metric("UF_needed_net (L)", f"{UF_needed_L:.2f}")
    m4.metric("UF_recommended (L)", f"{UF_recommended_L:.2f}")
    if UF_deficit_L > 0.0:
        st.warning(f"UF_deficit: {UF_deficit_L:.2f} L — εξετάστε παράταση συνεδρίας ή split UF.")

    # Overhydration risk (logistic)
    x_over = (beta0 
            + b_OH * OH_L 
            + b_dysp * (1 if dyspnea else 0)
            + b_edm  * (1 if edema else 0)
            + b_ef   * low_ef
            + b_af   * arrhythmia_any)
    P_over = sigmoid(x_over)
    st.metric("P_overhydration_risk", f"{P_over*100:.1f}%")
    omega = omega_target

    plan_notes = []
    if P_over*100 > omega and UF_deficit_L > 0:
        # προτείνεται παράταση αντί αύξησης ρυθμού
        if r_max_dyn > 0:
            extra_minutes_over = UF_deficit_L * 1000.0 / (r_max_dyn * weight) * 60.0
            def round_up_step(x, step):
                return int(math.ceil(x/step) * step)
            extra_minutes_over = round_up_step(extra_minutes_over, round_step)
            st.info(f"Πρόταση: +{extra_minutes_over} λεπτά με ίδιο ασφαλές r για κάλυψη overload.")
        plan_notes.append("Υπερυδάτωση ↑ + UF deficit → προτεραιότητα παράτασης αντί αύξησης r.")
    elif UF_deficit_L > 0:
        plan_notes.append("Χωρίς υψηλό overload → παράταση ή split UF, ανά κλινική κρίση.")

    alerts = []
    if UF_deficit_L > 0.0: alerts.append(f"UF deficit {UF_deficit_L:.2f} L")
    if tmp_slope > tmp_thr or vp_trend > vp_thr: alerts.append("High TMP/VP")
    if bp_drop_pct >= bp_drop_thr: alerts.append(f"SBP drop ≥{bp_drop_thr:.0f}%")
    if hypo_symptoms_any == 1: alerts.append("Συμπτώματα υπότασης")
    if P_over*100 > omega: alerts.append("P_overhydration πάνω από στόχο")
    if alerts:
        st.error(" | ".join(alerts))
    if plan_notes:
        st.caption(" • ".join(plan_notes))

with tab_learn:
    st.subheader("Actuals & learning (post-session)")
    cA, cB, cC, cD = st.columns(4)
    with cA:
        UF_actual_total = st.number_input("UF_actual_total (L)", value=0.0, step=0.1, format="%.2f")
    with cB:
        duration_actual_min = st.number_input("Διάρκεια_actual (min)", value=240, step=1)
    with cC:
        outcome_last = st.selectbox("Outcome_last (0=OK,1=hypotension)", [0,1], index=0)
    with cD:
        gamma0_offset_current = st.number_input("γ0_offset_current", value=0.0, step=0.1, format="%.2f")

    # Υπολογισμοί για learning
    UF_actual_net = None
    if UF_actual_total > 0:
        UF_actual_net = UF_actual_total - rinseback_L - iv_L - intake_L

    r_used_last = None
    if (UF_actual_net is not None) and duration_actual_min > 0 and weight > 0:
        r_used_last = UF_actual_net * 1000.0 * 60.0 / (weight * duration_actual_min)

    def sigmoid(x):
        return 1.0/(1.0 + math.exp(-x))

    p_old_last = None
    if r_used_last is not None:
        lin_old = (gamma0 + gamma1 * r_used_last +
                   g_meds*meds_recent + g_tmp*tmp_slope + g_vp*vp_trend +
                   g_age*max(0.0, (age - 60.0)/10.0) + g_dm*dm + g_press*dP_atm_10hPa +
                   gamma0_offset_current)
        p_old_last = sigmoid(lin_old)

    tau = tau_default
    p_target = (tau/200.0) if outcome_last == 0 else min(0.8, 2*(tau/100.0))
    delta_logit = None
    if (p_old_last is not None) and (0 < p_old_last < 1):
        delta_logit = math.log(p_target/(1-p_target)) - math.log(p_old_last/(1-p_old_last))

    alpha = st.number_input("α (learning rate)", value=0.2, step=0.05, min_value=0.0, max_value=1.0)
    gamma0_offset_updated = gamma0_offset_current
    if delta_logit is not None:
        gamma0_offset_updated = gamma0_offset_current + alpha * delta_logit

    # Next session planning (+15% cap από βάση)
    logit_tau = math.log((tau/100.0)/(1 - (tau/100.0)))
    lin_terms_base = (gamma0 + g_meds*meds_recent + g_tmp*tmp_slope + g_vp*vp_trend +
                      g_age*max(0.0,(age-60.0)/10.0) + g_dm*dm + g_press*dP_atm_10hPa)
    r_bounded_base = min(max((logit_tau - lin_terms_base) / gamma1 if gamma1!=0 else float('nan'), rmin), rmax)

    lin_terms_next = lin_terms_base + gamma0_offset_updated  # μόνο offset αλλάζει ρητά
    r_next_raw = (logit_tau - lin_terms_next) / gamma1 if gamma1 != 0 else float("nan")
    r_next_bounded = min(max(r_next_raw, rmin), rmax)
    r_next_capped = min(r_next_bounded, 1.15 * r_bounded_base)

    guard_hit = (tmp_slope > tmp_thr) or (vp_trend > vp_thr) or (bp_drop_pct >= bp_drop_thr) or (hypo_symptoms_any == 1)
    r_next_dyn = (safety_mult if guard_hit else 1.0) * r_next_capped

    UF_cap_next_L = r_next_dyn * (duration_actual_min/60.0) * weight / 1000.0

    # Αν από σήμερα προκύπτει έλλειμμα, πόσα λεπτά επιπλέον χρειάζονται στην επόμενη;
    extra_minutes = 0.0
    if r_next_dyn > 0:
        UF_needed_L = idwg + intake_L - rinseback_L - iv_L
        UF_cap_L_base = r_next_dyn * (duration_actual_min/60.0) * weight / 1000.0
        UF_deficit_L = max(0.0, UF_needed_L - UF_cap_L_base)
        if UF_deficit_L > 0:
            extra_minutes = UF_deficit_L * 1000.0 / (r_next_dyn * weight) * 60.0

    def round_up_step(x, step):
        return int(math.ceil(x/step) * step)

    recommended_total_minutes = round_up_step(duration_actual_min + max(0.0, extra_minutes), round_step)

    st.markdown("---")
    cN1, cN2, cN3, cN4 = st.columns(4)
    cN1.metric("r_max_next (dyn)", f"{r_next_dyn:.2f}")
    cN2.metric("UF_cap_next (L)", f"{UF_cap_next_L:.2f}")
    cN3.metric("Extra minutes needed", f"{extra_minutes:.0f} min")
    cN4.metric("Recommended total minutes", f"{recommended_total_minutes} min")

    # Export snapshot (JSON)
    st.markdown("---")
    if st.button("📤 Export snapshot (JSON)"):
        data = {
            "session_dt": session_dt, "patient_id": patient_id,
            "age": age, "weight": weight, "duration_min": duration_min,
            "idwg": idwg, "intake_L": intake_L, "rinseback_L": rinseback_L, "iv_L": iv_L,
            "meds_recent": meds_recent, "dm": dm, "dP_atm_10hPa": dP_atm_10hPa,
            "sbp_pre": sbp_pre, "sbp_post": sbp_post, "bp_drop_pct": bp_drop_pct,
            "symptoms": {"headache": bool(s_headache), "cramps": bool(s_cramps), "GI": bool(s_gi), "syncope": bool(s_syncope)},
            "ef_percent": ef_percent, "arrhythmia": bool(arrhythmia), "af_recent": bool(af_recent),
            "tmp_start": tmp_start, "tmp_end": tmp_end, "tmp_slope": tmp_slope,
            "vp_start": vp_start, "vp_end": vp_end, "vp_trend": vp_trend,
            "dialysate": {"Na": dial_Na, "HCO3": dial_HCO3, "cond": dial_cond, "K": dial_K, "Ca": dial_Ca},
            "OH_L": OH_L, "dyspnea": bool(dyspnea), "edema": bool(edema), "chest_symp": bool(chest_symp),
            "tau": tau, "r_max_dyn": r_max_dyn, "UF_cap_L": UF_cap_L, "UF_needed_L": UF_needed_L,
            "UF_recommended_L": UF_recommended_L,
            "P_overhydration_risk": P_over,
            "UF_actual_total": UF_actual_total, "UF_actual_net": UF_actual_net,
            "duration_actual_min": duration_actual_min, "r_used_last": r_used_last,
            "outcome_last": outcome_last, "alpha": alpha,
            "gamma0_offset_current": gamma0_offset_current, "gamma0_offset_updated": gamma0_offset_updated,
            "r_max_next_dyn": r_next_dyn, "UF_cap_next_L": UF_cap_next_L,
            "extra_minutes": extra_minutes, "recommended_total_minutes": recommended_total_minutes
        }
        st.download_button("Download session.json", data=json.dumps(data, indent=2), file_name="session.json", mime="application/json")

st.caption("⚠️ Prototype — validate clinically πριν από συστηματική χρήση • Προσαρμόστε thresholds/συντελεστές ανά μονάδα")
Add BP, cardiac, machine params & P_over risk
