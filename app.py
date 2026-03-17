import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import timedelta

st.set_page_config(page_title="Gestion Congés Pro", layout="wide", initial_sidebar_state="collapsed")

# Style pour forcer le mode clair et améliorer le design
st.markdown("""
    <style>
    .stApp { background-color: #f8f9fa; }
    .main { padding: 2rem; }
    .stDataFrame { border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
    </style>
    """, unsafe_allow_html=True)

st.title("📂 Gestion Intelligente des Congés")

# Connexion
conn = st.connection("gsheets", type=GSheetsConnection)

def load_data():
    data = conn.read(worksheet="Sheet1", ttl="0")
    data.columns = data.columns.str.strip()
    return data

df = load_data()

# --- VUE TABLEAU ---
st.subheader("📊 État des effectifs")
st.dataframe(df, use_container_width=True, hide_index=True)

st.divider()

# --- FORMULAIRE D'ACTION ---
st.subheader("✍️ Affectation & Mise à jour")

# Sélection de l'employé
col_prenom = 'prénom' if 'prénom' in df.columns else 'prenom'
liste_employes = df['matricule'].astype(str) + " - " + df['nom'] + " " + df[col_prenom]
choix = st.selectbox("Rechercher un employé par matricule ou nom", options=liste_employes)

if choix:
    matricule_sel = choix.split(" - ")[0]
    info_emp = df[df['matricule'].astype(str) == matricule_sel].iloc[0]
    
    reliquat_actuel = int(info_emp['reliquat des congés'])

    # Interface du formulaire
    with st.expander(f"Modifier le dossier de {info_emp['nom']} (Reliquat actuel : {reliquat_actuel} jours)", expanded=True):
        with st.form("conge_form"):
            c1, c2, c3 = st.columns(3)
            
            with c1:
                d_debut = st.date_input("Date de début de congé")
                # Alerte si le reliquat est épuisé
                if reliquat_actuel <= 0:
                    st.error("⚠️ Reliquat épuisé !")
                    nouveau_service = st.text_input("Service d'affectation forcé", placeholder="Ex: Logistique")
                    remarque = st.text_area("Remarque", value="Affectation suite à épuisement de crédit congé")
                else:
                    nouveau_service = st.text_input("Changer de service (optionnel)", value=info_emp['service affecté'])
                    remarque = st.text_area("Remarque", value="")

            with c2:
                d_fin = st.date_input("Date de fin de congé")
                # CALCUL AUTOMATIQUE
                duree_calculee = (d_fin - d_debut).days
                if duree_calculee < 0: duree_calculee = 0
                st.info(f"Durée calculée : {duree_calculee} jours")

            with c3:
                # REPRISE AUTOMATIQUE (lendemain de la fin)
                date_reprise = d_fin + timedelta(days=1)
                st.info(f"Reprise prévue le : {date_reprise.strftime('%d/%m/%Y')}")
                nouveau_reliquat = reliquat_actuel - duree_calculee

            submit = st.form_submit_button("🚀 Enregistrer la mise à jour")

            if submit:
                new_df = df.copy()
                idx = new_df.index[new_df['matricule'].astype(str) == matricule_sel].tolist()[0]
                
                # Mise à jour des données
                new_df.at[idx, 'date début congé'] = str(d_debut)
                new_df.at[idx, 'date fin congé'] = str(d_fin)
                new_df.at[idx, 'date reprise'] = str(date_reprise)
                new_df.at[idx, 'durréenbr des congés'] = duree_calculee
                new_df.at[idx, 'reliquat des congés'] = nouveau_reliquat
                new_df.at[idx, 'service affecté'] = nouveau_service
                # Ajout de la remarque si nécessaire (ajoute une colonne si elle n'existe pas)
                new_df.at[idx, 'remarque'] = remarque

                try:
                    conn.update(worksheet="Sheet1", data=new_df)
                    st.balloons()
                    st.success(f"Dossier de {info_emp['nom']} mis à jour avec succès !")
                    st.cache_data.clear()
                    st.rerun()
                except Exception as e:
                    st.error(f"Erreur lors de l'écriture : {e}")
