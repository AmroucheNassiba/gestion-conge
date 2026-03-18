import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime, timedelta

# ══════════════════════════════════════════════
#  CONFIG PAGE
# ══════════════════════════════════════════════
st.set_page_config(
    page_title="Gestion des Congés RH",
    layout="wide",
    page_icon="🗓️"
)

st.markdown("""
<style>
    /* Cartes métriques */
    div[data-testid="metric-container"] {
        background: #f8f9fa;
        border-radius: 10px;
        padding: 12px 16px;
        border: 1px solid #e9ecef;
    }
    /* Tableau historique */
    .hist-row {
        display: flex;
        justify-content: space-between;
        padding: 6px 0;
        border-bottom: 1px solid #f0f0f0;
        font-size: 13px;
    }
    .hist-row:last-child { border-bottom: none; }
    .tag-conge {
        background: #d1ecf1; color: #0c5460;
        padding: 2px 8px; border-radius: 12px;
        font-size: 11px; font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════
#  CONSTANTES — noms de colonnes Google Sheets
# ══════════════════════════════════════════════
COL_MAT      = "matricule"
COL_NOM      = "nom"
COL_SERVICE  = "service affecté"
COL_RELIQUAT = "reliquat des congés"
COL_MAJ      = "derniere_maj"
# Préfixe pour les congés numérotés (congé 1, 2, 3…)
# Chaque congé occupe 4 colonnes : debut, fin, duree, reprise
CONGE_PREFIX = "conge"


# ══════════════════════════════════════════════
#  FONCTIONS UTILITAIRES
# ══════════════════════════════════════════════

def duree_inclusive(d_start, d_end) -> int:
    """Durée réelle : le jour de début ET de fin comptent."""
    if d_end < d_start:
        return 0
    return (d_end - d_start).days + 1


def date_reprise(d_end) -> str:
    return (d_end + timedelta(days=1)).strftime("%d/%m/%Y")


def safe_float(val, default=0.0) -> float:
    try:
        f = float(val)
        return f if not pd.isna(f) else default
    except (ValueError, TypeError):
        return default


def get_status(reliquat: float):
    """Retourne (label, couleur_streamlit)"""
    if reliquat <= 0:
        return "🔴 Reliquat épuisé", "error"
    elif reliquat < 5:
        return "🟠 Solde critique", "warning"
    return "🟢 Solde disponible", "success"


def prochain_slot_conge(row: pd.Series) -> int:
    """
    Cherche le prochain numéro de congé libre pour cet employé.
    Ex : si conge1_debut et conge2_debut existent → retourne 3.
    """
    i = 1
    while True:
        col = f"{CONGE_PREFIX}{i}_debut"
        if col not in row.index:
            return i          # colonne pas encore créée du tout
        val = row.get(col, "")
        if pd.isna(val) or str(val).strip() == "":
            return i          # slot vide trouvé
        i += 1


def historique_conges(row: pd.Series) -> list[dict]:
    """Retourne la liste des congés déjà enregistrés pour un employé."""
    hist = []
    i = 1
    while True:
        col_debut = f"{CONGE_PREFIX}{i}_debut"
        if col_debut not in row.index:
            break
        debut = row.get(col_debut, "")
        if pd.isna(debut) or str(debut).strip() == "":
            break
        hist.append({
            "n":       i,
            "debut":   str(row.get(f"{CONGE_PREFIX}{i}_debut",  "")).strip(),
            "fin":     str(row.get(f"{CONGE_PREFIX}{i}_fin",    "")).strip(),
            "duree":   str(row.get(f"{CONGE_PREFIX}{i}_duree",  "")).strip(),
            "reprise": str(row.get(f"{CONGE_PREFIX}{i}_reprise","")).strip(),
        })
        i += 1
    return hist


def date_min_prochain_conge(row: pd.Series, slot: int):
    """
    Retourne la date minimale autorisée pour le début du congé N.
    = date de reprise du congé N-1 (l'employé doit être revenu avant de repartir).
    Si c'est le 1er congé, pas de contrainte → retourne aujourd'hui.
    """
    if slot <= 1:
        return datetime.today().date()
    col_reprise_precedente = f"{CONGE_PREFIX}{slot - 1}_reprise"
    val = row.get(col_reprise_precedente, "")
    if pd.isna(val) or str(val).strip() == "":
        return datetime.today().date()
    try:
        return datetime.strptime(str(val).strip(), "%Y-%m-%d").date()
    except ValueError:
        return datetime.today().date()


def assurer_colonnes(df: pd.DataFrame, slot: int) -> pd.DataFrame:
    """
    S'assure que les colonnes congeN_debut/fin/duree/reprise existent.
    Si non, les crée avec des chaînes vides.
    """
    for suffix in ["_debut", "_fin", "_duree", "_reprise"]:
        col = f"{CONGE_PREFIX}{slot}{suffix}"
        if col not in df.columns:
            df[col] = ""
    return df


# ══════════════════════════════════════════════
#  CONNEXION GOOGLE SHEETS
# ══════════════════════════════════════════════
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
except Exception as e:
    st.error(f"❌ Impossible de se connecter à Google Sheets : {e}")
    st.stop()


@st.cache_data(ttl=30)
def load_data() -> pd.DataFrame:
    data = conn.read(worksheet="Sheet1", ttl=0)
    data.columns = [str(c).strip().lower() for c in data.columns]
    if COL_RELIQUAT in data.columns:
        data[COL_RELIQUAT] = pd.to_numeric(data[COL_RELIQUAT], errors="coerce").fillna(0)
    return data


df = load_data()


# ══════════════════════════════════════════════
#  EN-TÊTE
# ══════════════════════════════════════════════
st.title("🗓️ Gestion des Congés — Ressources Humaines")
st.caption(f"📅 {datetime.now().strftime('%A %d %B %Y, %H:%M')}")
st.divider()


# ══════════════════════════════════════════════
#  MÉTRIQUES GLOBALES
# ══════════════════════════════════════════════
if COL_RELIQUAT in df.columns:
    total     = len(df)
    epuises   = int((df[COL_RELIQUAT] <= 0).sum())
    critiques = int(((df[COL_RELIQUAT] > 0) & (df[COL_RELIQUAT] < 5)).sum())
    moy       = round(df[COL_RELIQUAT].mean(), 1)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("👥 Total employés",         total)
    c2.metric("🔴 Reliquats épuisés",       epuises)
    c3.metric("🟠 Soldes critiques (< 5j)", critiques)
    c4.metric("📊 Solde moyen",             f"{moy} j")
    st.divider()


# ══════════════════════════════════════════════
#  TABLEAU DES EMPLOYÉS AVEC FILTRES
# ══════════════════════════════════════════════
with st.expander("📋 Vue d'ensemble — Tous les employés", expanded=False):
    fa, fb = st.columns([2, 1])
    with fa:
        search = st.text_input("🔍 Nom ou matricule", placeholder="ex: Karim, 1042…")
    with fb:
        filtre = st.selectbox("Statut", ["Tous", "🟢 OK (≥5j)", "🟠 Critique (<5j)", "🔴 Épuisé"])

    dv = df.copy()
    if search.strip():
        m = (
            dv[COL_NOM].astype(str).str.contains(search, case=False, na=False)
            | dv[COL_MAT].astype(str).str.contains(search, case=False, na=False)
        )
        dv = dv[m]
    if filtre == "🟢 OK (≥5j)":
        dv = dv[dv[COL_RELIQUAT] >= 5]
    elif filtre == "🟠 Critique (<5j)":
        dv = dv[(dv[COL_RELIQUAT] > 0) & (dv[COL_RELIQUAT] < 5)]
    elif filtre == "🔴 Épuisé":
        dv = dv[dv[COL_RELIQUAT] <= 0]

    cols_affich = [c for c in [COL_MAT, COL_NOM, COL_SERVICE, COL_RELIQUAT] if c in dv.columns]
    aff = dv[cols_affich].copy()
    aff.columns = ["Matricule", "Nom", "Service", "Reliquat (j)"][:len(cols_affich)]
    if "Reliquat (j)" in aff.columns:
        aff["Statut"] = aff["Reliquat (j)"].apply(
            lambda r: "🟢 OK" if r >= 5 else ("🟠 Critique" if r > 0 else "🔴 Épuisé")
        )
    st.dataframe(aff, use_container_width=True, hide_index=True)

st.divider()


# ══════════════════════════════════════════════
#  SÉLECTION EMPLOYÉ
# ══════════════════════════════════════════════
st.subheader("📝 Gestion du dossier employé")

options_emp = ["— Sélectionner un employé —"] + [
    f"{m}  ·  {n}"
    for m, n in zip(df[COL_MAT].astype(str).tolist(), df[COL_NOM].tolist())
]
selection = st.selectbox("Collaborateur", options=options_emp)

if selection == "— Sélectionner un employé —":
    st.info("👆 Sélectionnez un employé pour gérer son dossier congé.")
    st.stop()

# ── Récupération des données de l'employé ──
m_id     = selection.split("·")[0].strip()
emp_mask = df[COL_MAT].astype(str) == m_id
if emp_mask.sum() == 0:
    st.error("Employé introuvable dans la base.")
    st.stop()

emp    = df[emp_mask].iloc[0]
idx    = df.index[emp_mask][0]
solde  = safe_float(emp.get(COL_RELIQUAT, 0))
label, badge = get_status(solde)
solde_epuise = solde <= 0

st.divider()

# ══════════════════════════════════════════════
#  MISE EN PAGE : FORMULAIRE | PANNEAU LATÉRAL
# ══════════════════════════════════════════════
col_main, col_side = st.columns([3, 1], gap="large")

# ────────────────────────────
#  COLONNE PRINCIPALE
# ────────────────────────────
with col_main:

    # Fiche identité
    st.markdown(f"### {emp[COL_NOM]}")
    st.markdown(
        f"**Matricule :** `{m_id}`  &nbsp;|&nbsp;  "
        f"**Service actuel :** {emp.get(COL_SERVICE, 'N/A')}  &nbsp;|&nbsp;  "
        f"**Reliquat :** {solde} j"
    )

    # Bandeau de statut
    if badge == "error":
        st.error(f"{label} — Le formulaire de congé est désactivé. Choisissez une action ci-dessous.")
    elif badge == "warning":
        st.warning(f"{label} — Il reste seulement {solde} jour(s). Le système bloquera si la durée demandée dépasse ce solde.")
    else:
        st.success(f"{label} — {solde} jour(s) disponibles.")

    st.markdown("---")

    # ══════════════════════════════
    #  CAS 1 : RELIQUAT ÉPUISÉ
    # ══════════════════════════════
    if solde_epuise:
        st.markdown("#### 🔀 Action — Reliquat épuisé")
        st.markdown(
            "Le solde de congés de cet employé est **nul**. "
            "Vous pouvez soit le **maintenir dans son service actuel**, "
            "soit le **réaffecter à un autre service**."
        )

        with st.form("form_epuise"):
            choix = st.radio(
                "Que souhaitez-vous faire ?",
                options=[
                    "✅ Maintenir dans le service actuel",
                    "🔀 Réaffecter à un autre service",
                ],
                horizontal=True
            )

            nouveau_service = ""
            if choix == "🔀 Réaffecter à un autre service":
                nouveau_service = st.text_input(
                    "Nouveau service",
                    placeholder="Ex: Production, Maintenance, Administration…"
                )

            remarque = st.text_input(
                "Remarque / Note interne",
                placeholder="Motif de la décision…"
            )

            confirmer = st.form_submit_button("✅ Enregistrer la décision", use_container_width=True)

            if confirmer:
                if choix == "🔀 Réaffecter à un autre service" and not nouveau_service.strip():
                    st.error("❌ Veuillez saisir le nom du nouveau service.")
                else:
                    service_final = nouveau_service.strip() if choix == "🔀 Réaffecter à un autre service" else emp.get(COL_SERVICE, "")
                    note_auto     = f"Décision solde épuisé : {choix.replace('✅ ','').replace('🔀 ','')}."
                    note_finale   = f"{note_auto} {remarque}".strip()

                    df.at[idx, COL_SERVICE] = service_final
                    df.at[idx, COL_MAJ]     = datetime.now().strftime("%Y-%m-%d %H:%M")
                    # On ajoute la remarque dans la dernière colonne historique remarque si elle existe
                    # sinon on crée une colonne dédiée
                    if "remarque_epuisement" not in df.columns:
                        df["remarque_epuisement"] = ""
                    df.at[idx, "remarque_epuisement"] = note_finale

                    with st.spinner("🔄 Synchronisation…"):
                        try:
                            conn.update(worksheet="Sheet1", data=df)
                            st.cache_data.clear()
                            action_msg = (
                                f"réaffecté au service **{service_final}**"
                                if choix == "🔀 Réaffecter à un autre service"
                                else f"maintenu dans le service **{service_final}**"
                            )
                            st.success(f"✅ **{emp[COL_NOM]}** a été {action_msg}.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ Erreur de sauvegarde : {e}")

    # ══════════════════════════════
    #  CAS 2 : RELIQUAT DISPONIBLE
    # ══════════════════════════════
    else:
        slot  = prochain_slot_conge(emp)
        d_min = date_min_prochain_conge(emp, slot)
        st.markdown(f"#### 📅 Affecter le congé n°{slot}")

        if slot > 1:
            st.info(
                f"📌 Congé précédent (n°{slot-1}) : reprise le **{d_min.strftime('%d/%m/%Y')}**. "
                f"Le congé n°{slot} ne peut pas commencer avant cette date."
            )

        # ── DATES : HORS du st.form → mise à jour immédiate à chaque changement ──
        sk_start = f"d_start_{m_id}"
        sk_end   = f"d_end_{m_id}"

        # Initialisation session_state si premier affichage ou changement d'employé
        if sk_start not in st.session_state or st.session_state[sk_start] < d_min:
            st.session_state[sk_start] = d_min
        if sk_end not in st.session_state or st.session_state[sk_end] <= st.session_state[sk_start]:
            st.session_state[sk_end] = d_min + timedelta(days=1)

        fa, fb = st.columns(2)
        with fa:
            d_start = st.date_input(
                "📅 Date de début",
                key=sk_start,
                min_value=d_min
            )
        with fb:
            d_end = st.date_input(
                "📅 Date de fin",
                key=sk_end,
                min_value=d_min     # contrainte fixe : >= plancher du slot seulement
            )

        # ── MÉTRIQUES : recalculées en direct à chaque changement de date ──
        # Alerte temps réel si fin < début (sans bloquer Streamlit)
        if d_end < d_start:
            st.error("⛔ La date de fin est antérieure à la date de début. Corrigez avant de continuer.")

        duree     = duree_inclusive(d_start, d_end)   # retourne 0 si d_end < d_start
        reprise   = date_reprise(d_end)
        new_solde = round(solde - duree, 2)
        depasse   = duree > solde or d_end < d_start  # bloque aussi si dates incohérentes

        bc1, bc2, bc3 = st.columns(3)
        bc1.metric("⏱ Durée demandée",     f"{duree} j")
        bc2.metric("📅 Date de reprise",     reprise)
        bc3.metric(
            "📊 Solde après validation",
            f"{max(0, new_solde)} j",
            delta=f"-{duree}" if not depasse else None,
            delta_color="inverse"
        )

        if depasse:
            st.error(
                f"⛔ Durée demandée ({duree}j) **supérieure** au reliquat disponible ({solde}j). "
                f"Réduisez la période ou fractionnez en **{int(solde)}j** maintenant + retour pour la suite."
            )
        elif new_solde == 0:
            st.warning(
                "⚠️ Ce congé **épuisera entièrement** le reliquat. "
                "À la reprise, l'employé sera soumis à la procédure de réaffectation."
            )
        elif new_solde < 5:
            st.info(f"ℹ️ Après ce congé, le reliquat sera critique : **{new_solde}j**.")

        # ── FORMULAIRE : uniquement service, remarque et bouton confirmer ──
        with st.form("form_conge"):
            fc1, fc2 = st.columns(2)
            with fc1:
                service = st.text_input(
                    "🏢 Service affecté",
                    value=str(emp.get(COL_SERVICE, ""))
                )
            with fc2:
                remarque = st.text_input(
                    "📌 Remarque",
                    placeholder="Note interne facultative…"
                )

            confirmer = st.form_submit_button(
                "✅ Confirmer l'affectation",
                use_container_width=True,
                disabled=depasse    # bouton grisé si dépassement
            )

            if confirmer and not depasse:
                errors = []
                if d_end < d_start:
                    errors.append("La date de fin est antérieure à la date de début.")
                if d_start < d_min:
                    errors.append(
                        f"La date de début ({d_start.strftime('%d/%m/%Y')}) est antérieure "
                        f"à la date de reprise du congé précédent ({d_min.strftime('%d/%m/%Y')}). "
                        "L'employé doit reprendre avant de repartir."
                    )
                if errors:
                    for e in errors:
                        st.error(f"❌ {e}")
                else:
                    df = assurer_colonnes(df, slot)
                    df.at[idx, f"{CONGE_PREFIX}{slot}_debut"]   = d_start.strftime("%Y-%m-%d")
                    df.at[idx, f"{CONGE_PREFIX}{slot}_fin"]     = d_end.strftime("%Y-%m-%d")
                    df.at[idx, f"{CONGE_PREFIX}{slot}_duree"]   = duree
                    df.at[idx, f"{CONGE_PREFIX}{slot}_reprise"] = (d_end + timedelta(days=1)).strftime("%Y-%m-%d")
                    df.at[idx, COL_RELIQUAT] = max(0, new_solde)
                    df.at[idx, COL_SERVICE]  = service.strip() if service.strip() else emp.get(COL_SERVICE, "")
                    df.at[idx, COL_MAJ]      = datetime.now().strftime("%Y-%m-%d %H:%M")
                    if "remarque" not in df.columns:
                        df["remarque"] = ""
                    df.at[idx, "remarque"] = remarque

                    with st.spinner("🔄 Synchronisation avec Google Sheets…"):
                        try:
                            conn.update(worksheet="Sheet1", data=df)
                            st.cache_data.clear()
                            st.success(
                                f"✅ Congé n°{slot} de **{emp[COL_NOM]}** enregistré. "
                                f"Période : {d_start.strftime('%d/%m/%Y')} → {d_end.strftime('%d/%m/%Y')} "
                                f"({duree}j). Nouveau solde : **{max(0, new_solde)}j**."
                            )
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ Erreur de sauvegarde : {e}")


# ────────────────────────────
#  COLONNE LATÉRALE : historique + résumé
# ────────────────────────────
with col_side:

    # Résumé solde
    st.markdown("#### Solde")
    if solde_epuise:
        st.error(f"**0 j** — Épuisé")
    elif solde < 5:
        st.warning(f"**{solde} j** — Critique")
    else:
        st.success(f"**{solde} j** disponibles")

    st.markdown("---")

    # Historique des congés
    st.markdown("#### Historique des congés")
    hist = historique_conges(emp)

    if not hist:
        st.caption("Aucun congé enregistré pour cet employé.")
    else:
        for h in hist:
            with st.container():
                st.markdown(
                    f"<div class='hist-row'>"
                    f"<span class='tag-conge'>Congé {h['n']}</span>"
                    f"<span style='font-size:11px;color:#555'>{h['debut']} → {h['fin']}</span>"
                    f"</div>"
                    f"<div style='font-size:11px;color:#888;padding:2px 0 6px 8px'>"
                    f"Durée : <b>{h['duree']}j</b> · Reprise : {h['reprise']}"
                    f"</div>",
                    unsafe_allow_html=True
                )

    st.markdown("---")

    # Simulation rapide
    if not solde_epuise:
        st.markdown("#### Simulation")
        sim_j = st.number_input(
            "Simuler N jours",
            min_value=1,
            max_value=int(max(solde, 1)),
            value=min(int(solde), 10),
            step=1
        )
        sim_solde = round(solde - sim_j, 1)
        if sim_solde > 0:
            st.caption(f"Après {sim_j}j → **{sim_solde}j** restants.")
        elif sim_solde == 0:
            st.caption(f"Après {sim_j}j → solde **épuisé**.")
        else:
            st.caption(f"⛔ {sim_j}j dépasse le solde disponible.")
