import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd

st.set_page_config(page_title="Gestion Conges", layout="wide")

st.title("📋 Gestion des Congés et Affectations")

# Connexion à Google Sheets
conn = st.connection("gsheets", type=GSheetsConnection)

def load_data():
    return conn.read(ttl="0")

df = load_data()

# --- AFFICHAGE PRINCIPAL ---
st.subheader("Tableau de bord des employés")
# On affiche le tableau avec les noms de colonnes propres
st.dataframe(df, use_container_width=True)

st.divider()

# --- FORMULAIRE DE MISE À JOUR ---
st.subheader("⚙️ Affecter un congé ou changer de service")

with st.form("update_form"):
    # On sélectionne par matricule pour être précis
    liste_employes = df['matricule'].astype(str) + " - " + df['nom'] + " " + df['prenom']
    choix = st.selectbox("Sélectionner l'employé", options=liste_employes)
    matricule_sel = choix.split(" - ")[0]

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("**Dates de Congés**")
        d_debut = st.date_input("Date début")
        d_fin = st.date_input("Date fin")
        d_reprise = st.date_input("Date reprise")

    with col2:
        st.markdown("**Calculs**")
        duree = st.number_input("Durée (jours)", min_value=0)
        nbr_conges = st.number_input("Nombre de congés pris", min_value=0)
        nouveau_reliquat = st.number_input("Nouveau reliquat", min_value=0)

    with col3:
        st.markdown("**Organisation**")
        nouveau_service = st.text_input("Nouveau service affecté")
        nouvelle_fonction = st.text_input("Nouvelle fonction (si besoin)")

    submit = st.form_submit_button("Enregistrer les modifications")

    if submit:
        # Trouver l'index de la ligne correspondant au matricule
        idx = df.index[df['matricule'].astype(str) == matricule_sel].tolist()[0]

        # Mise à jour des valeurs dans le DataFrame
        df.at[idx, 'date_debut'] = str(d_debut)
        df.at[idx, 'date_fin'] = str(d_fin)
        df.at[idx, 'date_reprise'] = str(d_reprise)
        df.at[idx, 'duree'] = duree
        df.at[idx, 'nbr_conges'] = nbr_conges
        df.at[idx, 'reliquat'] = nouveau_reliquat
        
        if nouveau_service:
            df.at[idx, 'service_affecte'] = nouveau_service
        if nouvelle_fonction:
            df.at[idx, 'fonction'] = nouvelle_fonction

        # Sauvegarde immédiate vers Google Sheets
        conn.update(data=df)
        st.success(f"Mise à jour réussie pour le matricule {matricule_sel} !")
        st.rerun()