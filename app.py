import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime, timedelta

# Configuration de la page
st.set_page_config(page_title="HR Management System", layout="wide", page_icon="🏢")

# --- FONCTIONS CŒUR MÉTIER ---
def calculate_leave_metrics(d_start, d_end):
    """Calcule la durée et la date de reprise automatiquement."""
    duration = (d_end - d_start).days
    return max(0, duration), d_end + timedelta(days=1)

def get_status_badge(reliquat):
    """Retourne un indicateur visuel du solde de l'employé."""
    if reliquat <= 0:
        return "🔴 Solde Épuisé"
    elif reliquat < 5:
        return "🟠 Solde Critique"
    return "🟢 Solde OK"

# --- CHARGEMENT DES DONNÉES ---
try:
    conn = st.connection("gsheets", type=GSheetsConnection)

    @st.cache_data(ttl=0)
    def load_cleaned_data():
        data = conn.read(worksheet="Sheet1", ttl=0)
        data.columns = [str(c).strip().lower() for c in data.columns]
        return data

    df = load_cleaned_data()
except Exception as e:
    st.error(f"Erreur de connexion au référentiel : {e}")
    st.stop()

# --- INTERFACE PRINCIPALE ---
st.title("🏢 Système de Gestion des Ressources Humaines")
st.markdown(f"**Dernière mise à jour :** {datetime.now().strftime('%d/%m/%Y %H:%M')}")

# Vue d'ensemble avec filtres
with st.expander("🔍 Consulter la base de données employés", expanded=False):
    st.dataframe(df, use_container_width=True, hide_index=True)

st.divider()

# --- ZONE D'ACTION ---
col_form, col_summary = st.columns([2, 1])

with col_form:
    st.subheader("📝 Mise à jour du dossier employé")
    
    # Sélections intelligentes
    noms = df['nom'].tolist()
    matricules = df['matricule'].astype(str).tolist()
    liste_options = [f"{m} - {n}" for m, n in zip(matricules, noms)]
    
    selection = st.selectbox("Rechercher un collaborateur", options=[""] + liste_options)

    if selection:
        m_id = selection.split(" - ")[0]
        emp_data = df[df['matricule'].astype(str) == m_id].iloc[0]
        
        # Extraction sécurisée des colonnes sensibles
        rel_key = 'reliquat des congés'
        solde_actuel = float(emp_data.get(rel_key, 0))

        with st.form("pro_update_form"):
            st.markdown(f"### Dossier : {emp_data['nom']}")
            
            c1, c2 = st.columns(2)
            with c1:
                d_start = st.date_input("Début du congé", datetime.now())
                d_end = st.date_input("Fin du congé", datetime.now() + timedelta(days=1))
                
                # Calcul temps réel (prévisualisation)
                duree, reprise = calculate_leave_metrics(d_start, d_end)
                st.write(f"**Analyse :** {duree} jours demandés.")
            
            with c2:
                # Logique de décision intelligente
                current_service = emp_data.get('service affecté', "Non défini")
                
                if solde_actuel <= 0:
                    st.warning(f"⚠️ {get_status_badge(solde_actuel)}")
                    target_service = st.text_input("Réaffectation obligatoire vers :", placeholder="Saisir nouveau service")
                    remarque = "RÉAFFECTATION SYSTÉMATIQUE : Solde de congés nul."
                else:
                    st.info(f"✅ {get_status_badge(solde_actuel)} ({solde_actuel}j)")
                    target_service = st.text_input("Service affecté", value=current_service)
                    remarque = st.text_input("Remarque / Note interne", value="")

            # Validation finale
            if st.form_submit_button("Confirmer la mise à jour"):
                if d_start > d_end:
                    st.error("Erreur critique : La date de début ne peut pas être après la date de fin.")
                elif solde_actuel <= 0 and not target_service:
                    st.error("Le changement de service est obligatoire pour les soldes nuls.")
                else:
                    # Traitement de la donnée
                    idx = df.index[df['matricule'].astype(str) == m_id].tolist()[0]
                    
                    df.at[idx, 'date début congé'] = str(d_start)
                    df.at[idx, 'date fin congé'] = str(d_end)
                    df.at[idx, 'date reprise'] = str(reprise)
                    df.at[idx, 'durrée'] = duree
                    df.at[idx, 'reliquat des congés'] = solde_actuel - duree
                    df.at[idx, 'service affecté'] = target_service
                    
                    # Trçabilité (Audit)
                    df.at[idx, 'derniere_maj'] = datetime.now().strftime('%Y-%m-%d %H:%M')

                    with st.spinner("Synchronisation avec Google Cloud..."):
                        conn.update(worksheet="Sheet1", data=df)
                        st.success(f"Dossier de {emp_data['nom']} synchronisé avec succès.")
                        st.cache_data.clear()
                        st.rerun()

with col_summary:
    st.subheader("ℹ️ Aide au calcul")
    if selection:
        st.metric("Solde actuel", f"{solde_actuel} j")
        if solde_actuel <= 0:
            st.error("L'employé a épuisé ses droits. Le système impose une réaffectation de service conformément à la politique interne.")
        else:
            nouveau_solde_virtuel = solde_actuel - duree
            st.metric("Solde après validation", f"{nouveau_solde_virtuel} j", delta=-duree)
    else:
        st.info("Sélectionnez un employé pour voir l'analyse prédictive de son solde.")
