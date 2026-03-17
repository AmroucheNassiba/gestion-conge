import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd

st.set_page_config(page_title="Gestion Conges", layout="wide")

st.title("📋 Gestion des Congés et Affectations")

# Connexion avec le Service Account configuré dans les Secrets
conn = st.connection("gsheets", type=GSheetsConnection)

def load_data():
    # On lit la feuille principale (Sheet1)
    data = conn.read(worksheet="Sheet1", ttl="0")
    # On nettoie les espaces invisibles dans les noms de colonnes
    data.columns = data.columns.str.strip()
    return data

df = load_data()

st.subheader("Tableau de bord des employés")
st.dataframe(df, use_container_width=True)

st.divider()

with st.form("update_form"):
    # Récupération sécurisée du prénom (avec ou sans accent)
    col_prenom = 'prénom' if 'prénom' in df.columns else 'prenom'
    liste_employes = df['matricule'].astype(str) + " - " + df['nom'] + " " + df[col_prenom]
    
    choix = st.selectbox("Sélectionner l'employé", options=liste_employes)
    matricule_sel = choix.split(" - ")[0]

    col1, col2 = st.columns(2)
    with col1:
        d_debut = st.date_input("Date début congé")
        d_fin = st.date_input("Date fin congé")
        service_aff = st.text_input("Service affecté")

    with col2:
        reliquat = st.number_input("Reliquat des congés", min_value=0)
        duree = st.number_input("durréenbr des congés", min_value=0)

    submit = st.form_submit_button("Sauvegarder les modifications")

    if submit:
        new_df = df.copy()
        idx = new_df.index[new_df['matricule'].astype(str) == matricule_sel].tolist()[0]

        # Mise à jour des colonnes exactes
        new_df.at[idx, 'date début congé'] = str(d_debut)
        new_df.at[idx, 'date fin congé'] = str(d_fin)
        new_df.at[idx, 'reliquat des congés'] = reliquat
        new_df.at[idx, 'durréenbr des congés'] = duree
        if service_aff:
            new_df.at[idx, 'service affecté'] = service_aff

        try:
            # Maintenant l'opération est supportée grâce au Service Account !
            conn.update(worksheet="Sheet1", data=new_df)
            st.success(f"✅ Enregistré pour le matricule {matricule_sel} !")
            st.cache_data.clear()
            st.rerun()
        except Exception as e:
            st.error(f"Erreur de sauvegarde : {e}")
