import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime, timedelta

st.set_page_config(
    page_title="Gestion des Congés",
    layout="wide",
    page_icon="🗓️",
    initial_sidebar_state="collapsed"
)

st.markdown("""
<style>
    .stMetric { background: #f8f9fa; border-radius: 10px; padding: 10px; }
    div[data-testid="metric-container"] { background:#f8f9fa; border-radius:10px; padding:10px; }
    .badge-ok    { background:#d4edda; color:#155724; padding:3px 10px; border-radius:20px; font-size:12px; font-weight:600; }
    .badge-warn  { background:#fff3cd; color:#856404; padding:3px 10px; border-radius:20px; font-size:12px; font-weight:600; }
    .badge-danger{ background:#f8d7da; color:#721c24; padding:3px 10px; border-radius:20px; font-size:12px; font-weight:600; }
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────
# FONCTIONS UTILITAIRES
# ─────────────────────────────────────────────

def calculate_leave_duration(d_start: datetime.date, d_end: datetime.date) -> int:
    """
    Calcule la durée INCLUSIVE du congé (le jour de fin compte).
    Exemple : 01/03 → 03/03 = 3 jours
    """
    if d_end < d_start:
        return 0
    return (d_end - d_start).days + 1


def get_reprise(d_end: datetime.date) -> datetime.date:
    return d_end + timedelta(days=1)


def get_status(reliquat: float):
    if reliquat <= 0:
        return "🔴 Épuisé", "danger"
    elif reliquat < 5:
        return "🟠 Critique", "warn"
    return "🟢 OK", "ok"


def safe_float(val, default=0.0) -> float:
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


# ─────────────────────────────────────────────
# CHARGEMENT DES DONNÉES
# ─────────────────────────────────────────────

try:
    conn = st.connection("gsheets", type=GSheetsConnection)
except Exception as e:
    st.error(f"❌ Impossible de se connecter à Google Sheets : {e}")
    st.stop()


@st.cache_data(ttl=30)
def load_data() -> pd.DataFrame:
    data = conn.read(worksheet="Sheet1", ttl=0)
    data.columns = [str(c).strip().lower() for c in data.columns]
    # Normalisation du reliquat
    rel_col = "reliquat des congés"
    if rel_col in data.columns:
        data[rel_col] = pd.to_numeric(data[rel_col], errors="coerce").fillna(0)
    return data


df = load_data()

# Colonnes attendues (minuscules)
COL_NOM       = "nom"
COL_MAT       = "matricule"
COL_SERVICE   = "service affecté"
COL_RELIQUAT  = "reliquat des congés"
COL_DEBUT     = "date début congé"
COL_FIN       = "date fin congé"
COL_REPRISE   = "date reprise"
COL_DUREE     = "durrée"          # gardé tel quel pour compatibilité
COL_REMARQUE  = "remarque"
COL_MAJ       = "derniere_maj"


# ─────────────────────────────────────────────
# EN-TÊTE
# ─────────────────────────────────────────────

st.title("🗓️ Gestion des Congés — Ressources Humaines")
st.caption(f"Mise à jour : {datetime.now().strftime('%d/%m/%Y à %H:%M')}")

st.divider()

# ─────────────────────────────────────────────
# TABLEAU DE BORD (métriques globales)
# ─────────────────────────────────────────────

if COL_RELIQUAT in df.columns:
    total_emp    = len(df)
    epuises      = int((df[COL_RELIQUAT] <= 0).sum())
    critiques    = int(((df[COL_RELIQUAT] > 0) & (df[COL_RELIQUAT] < 5)).sum())
    solde_moyen  = round(df[COL_RELIQUAT].mean(), 1)

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("👥 Total employés",        total_emp)
    m2.metric("🔴 Reliquats épuisés",     epuises,  delta=f"-{epuises}" if epuises else None, delta_color="inverse")
    m3.metric("🟠 Soldes critiques (<5j)", critiques)
    m4.metric("📊 Solde moyen",           f"{solde_moyen} j")

st.divider()

# ─────────────────────────────────────────────
# LISTE DES EMPLOYÉS AVEC FILTRES
# ─────────────────────────────────────────────

with st.expander("📋 Vue d'ensemble — Tous les employés", expanded=True):

    col_f1, col_f2 = st.columns([2, 1])

    with col_f1:
        search = st.text_input("🔍 Rechercher (nom ou matricule)", placeholder="ex: Karim ou 1042")

    with col_f2:
        filtre_statut = st.selectbox("Filtrer par statut", ["Tous", "🟢 OK", "🟠 Critique", "🔴 Épuisé"])

    df_view = df.copy()

    # Filtre texte
    if search.strip():
        mask = (
            df_view[COL_NOM].astype(str).str.contains(search, case=False, na=False)
            | df_view[COL_MAT].astype(str).str.contains(search, case=False, na=False)
        )
        df_view = df_view[mask]

    # Filtre statut
    if filtre_statut == "🟢 OK":
        df_view = df_view[df_view[COL_RELIQUAT] >= 5]
    elif filtre_statut == "🟠 Critique":
        df_view = df_view[(df_view[COL_RELIQUAT] > 0) & (df_view[COL_RELIQUAT] < 5)]
    elif filtre_statut == "🔴 Épuisé":
        df_view = df_view[df_view[COL_RELIQUAT] <= 0]

    # Affichage stylé
    if not df_view.empty:
        affichage = df_view[[COL_MAT, COL_NOM, COL_SERVICE, COL_RELIQUAT]].copy()
        affichage.columns = ["Matricule", "Nom", "Service", "Reliquat (j)"]
        affichage["Statut"] = affichage["Reliquat (j)"].apply(
            lambda r: "🟢 OK" if r >= 5 else ("🟠 Critique" if r > 0 else "🔴 Épuisé")
        )
        st.dataframe(affichage, use_container_width=True, hide_index=True)
    else:
        st.info("Aucun employé ne correspond à la recherche.")

st.divider()

# ─────────────────────────────────────────────
# FORMULAIRE D'AFFECTATION
# ─────────────────────────────────────────────

st.subheader("📝 Affecter un congé")

# Sélection employé
noms       = df[COL_NOM].tolist()
matricules = df[COL_MAT].astype(str).tolist()
options    = ["— Sélectionner un employé —"] + [f"{m}  ·  {n}" for m, n in zip(matricules, noms)]

selection = st.selectbox("Collaborateur", options=options)

if selection and selection != "— Sélectionner un employé —":
    m_id     = selection.split("·")[0].strip()
    emp_mask = df[COL_MAT].astype(str) == m_id

    if emp_mask.sum() == 0:
        st.error("Employé introuvable.")
        st.stop()

    emp     = df[emp_mask].iloc[0]
    idx     = df.index[emp_mask][0]
    solde   = safe_float(emp.get(COL_RELIQUAT, 0))
    label, badge_type = get_status(solde)

    # Colonnes : formulaire | résumé
    col_form, col_side = st.columns([3, 1])

    with col_form:
        st.markdown(f"### {emp[COL_NOM]}")
        st.markdown(f"**Matricule :** `{m_id}` &nbsp;|&nbsp; **Service :** {emp.get(COL_SERVICE, 'N/A')}")

        if badge_type == "danger":
            st.error(f"⚠️ Solde épuisé. Ce dossier nécessite une réaffectation de service.")
        elif badge_type == "warn":
            st.warning(f"🟠 Solde critique : **{solde} jour(s)** restant(s).")
        else:
            st.success(f"🟢 Solde disponible : **{solde} jour(s)**")

        with st.form("affectation_form", clear_on_submit=False):

            f1, f2 = st.columns(2)
            with f1:
                d_start = st.date_input("📅 Date de début", value=datetime.today().date())
            with f2:
                d_end   = st.date_input("📅 Date de fin",   value=(datetime.today() + timedelta(days=1)).date())

            # Calcul en temps réel
            duree   = calculate_leave_duration(d_start, d_end)
            reprise = get_reprise(d_end)
            nouveau_solde = round(solde - duree, 2)

            st.markdown(
                f"**Durée calculée :** `{duree}` jour(s) &nbsp;|&nbsp; "
                f"**Date de reprise :** `{reprise.strftime('%d/%m/%Y')}`"
            )

            # Avertissement si dépassement
            if duree > solde and solde > 0:
                st.warning(f"⚠️ La durée demandée ({duree}j) dépasse le solde disponible ({solde}j). "
                           f"Ajustez les dates ou procédez en plusieurs congés.")
            elif nouveau_solde < 0 and solde <= 0:
                pass  # géré par le bloc épuisé plus haut

            f3, f4 = st.columns(2)
            with f3:
                if badge_type == "danger":
                    target_service = st.text_input(
                        "🔀 Nouveau service (obligatoire)",
                        placeholder="Ex: Production, Maintenance…"
                    )
                else:
                    target_service = st.text_input(
                        "🏢 Service affecté",
                        value=str(emp.get(COL_SERVICE, ""))
                    )

            with f4:
                remarque = st.text_input("📌 Remarque / Note interne", value="")

            submitted = st.form_submit_button("✅ Confirmer l'affectation", use_container_width=True)

            if submitted:
                # Validations
                errors = []

                if d_end < d_start:
                    errors.append("La date de fin est antérieure à la date de début.")

                if badge_type == "danger" and not target_service.strip():
                    errors.append("Le changement de service est obligatoire pour les soldes épuisés.")

                if duree > solde and solde > 0:
                    errors.append(
                        f"Durée demandée ({duree}j) supérieure au reliquat ({solde}j). "
                        "Réduisez la durée du congé."
                    )

                if errors:
                    for err in errors:
                        st.error(f"❌ {err}")
                else:
                    # Mise à jour du DataFrame
                    df.at[idx, COL_DEBUT]    = d_start.strftime("%Y-%m-%d")
                    df.at[idx, COL_FIN]      = d_end.strftime("%Y-%m-%d")
                    df.at[idx, COL_REPRISE]  = reprise.strftime("%Y-%m-%d")
                    df.at[idx, COL_DUREE]    = duree
                    df.at[idx, COL_RELIQUAT] = max(0, nouveau_solde)
                    df.at[idx, COL_SERVICE]  = target_service.strip() if target_service.strip() else emp.get(COL_SERVICE, "")
                    df.at[idx, COL_REMARQUE] = remarque if remarque else (
                        "RÉAFFECTATION : Solde épuisé." if badge_type == "danger" else ""
                    )
                    df.at[idx, COL_MAJ]      = datetime.now().strftime("%Y-%m-%d %H:%M")

                    with st.spinner("🔄 Synchronisation avec Google Sheets…"):
                        try:
                            conn.update(worksheet="Sheet1", data=df)
                            st.cache_data.clear()
                            st.success(
                                f"✅ Dossier de **{emp[COL_NOM]}** mis à jour. "
                                f"Nouveau solde : **{max(0, nouveau_solde)} jour(s)**"
                            )
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ Erreur lors de la sauvegarde : {e}")

    # ── Panneau résumé latéral ──
    with col_side:
        st.markdown("#### Résumé")
        st.metric("Solde actuel",   f"{solde} j")
        duree_preview = calculate_leave_duration(
            datetime.today().date(),
            datetime.today().date() + timedelta(days=1)
        )
        # Recalcul avec valeurs du formulaire (approximation)
        st.metric("Après congé",    f"{max(0, round(solde - duree, 2))} j", delta=-duree)

        st.divider()

        st.markdown("**Historique récent**")
        hist_cols = [COL_DEBUT, COL_FIN, COL_DUREE]
        if all(c in emp.index for c in hist_cols):
            debut_val  = emp.get(COL_DEBUT, "")
            fin_val    = emp.get(COL_FIN, "")
            duree_val  = emp.get(COL_DUREE, "")
            if debut_val and str(debut_val).strip():
                st.caption(f"Dernier congé : {debut_val} → {fin_val} ({duree_val}j)")
            else:
                st.caption("Aucun congé enregistré.")

else:
    st.info("Sélectionnez un employé pour commencer l'affectation.")
