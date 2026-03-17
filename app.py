import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime, timedelta

# Configuration de la page
st.set_page_config(page_title="Gestion Congés", layout="wide")

# Forcer le mode clair via CSS
st.markdown("""
    <style>
    .stApp { background-color: white; color: black; }
    [data-testid="stHeader"] { background-color: white; }
    </style>
    """, unsafe_allow_html=True)

st.title("📋 Système de Gestion des Congés")

try:
    # Connexion
    conn = st.connection("gsheets", type=GSheetsConnection)

    def load_data():
        # On lit la feuille
        data = conn.read(worksheet="Sheet1", ttl=0)
        # Nettoyage automatique des noms de colonnes
        data.columns = [str(c).strip() for c in data.columns]
        return data

    df = load_data()

    # Affichage du tableau
    st.subheader("Tableau des Employés")
    st.dataframe(df, use_container_width=True)

    st.divider()

    # --- FORMULAIRE ---
    st.subheader("Affectation de Congé")
    
    # On gère l'affichage pour la sélection
    col_nom = 'nom' if 'nom' in df.columns else df.columns[1]
    liste_employes = df['matricule'].astype(str) + " - " + df[col_nom].astype(str)
    
    choix = st.selectbox("Sélectionnez un employé", options=liste_employes)

    if choix:
        matricule_sel = choix.split(" - ")[0]
        # Extraire les infos de l'employé
        emp_row = df[df['matricule'].astype(str) == matricule_sel].iloc[0]
        
        # Récupération sécurisée du reliquat
        col_rel = 'reliquat des congés'
        reliquat_actuel = float(emp_row[col_rel]) if col_rel in emp_row else 0

        with st.form("form_update"):
            col1, col2 = st.columns(2)
            
            with col1:
                d_debut = st.date_input("Date début congé", datetime.now())
                d_fin = st.date_input("Date fin congé", datetime.now() + timedelta(days=1))
                
                # Calculs automatiques
                duree = (d_fin - d_debut).days
                date_reprise = d_fin + timedelta(days=1)
                
                st.write(f"**Durée calculée :** {duree} jours")
                st.write(f"**Date reprise automatique :** {date_reprise.strftime('%d/%m/%Y')}")

            with col2:
                # Logique Reliquat / Changement de service
                nouveau_service = emp_row.get('service affecté', "")
                remarque = ""
                
                if reliquat_actuel <= 0:
                    st.error("⚠️ Reliquat épuisé ! Veuillez affecter à un autre service.")
                    nouveau_service = st.text_input("Nouveau service d'affectation", value="")
                    remarque = "Affectation suite à épuisement de reliquat"
                else:
                    nouveau_service = st.text_input("Service affecté", value=nouveau_service)
                    st.success(f"Reliquat disponible : {reliquat_actuel} jours")

            # Bouton de validation
            if st.form_submit_button("Enregistrer les modifications"):
                # Mise à jour du DataFrame
                idx = df.index[df['matricule'].astype(str) == matricule_sel].tolist()[0]
                
                df.at[idx, 'date début congé'] = str(d_debut)
                df.at[idx, 'date fin congé'] = str(d_fin)
                df.at[idx, 'date reprise'] = str(date_reprise)
                df.at[idx, 'durréenbr des congés'] = duree
                df.at[idx, 'reliquat des congés'] = reliquat_actuel - duree
                df.at[idx, 'service affecté'] = nouveau_service
                
                # Sauvegarde
                conn.update(worksheet="Sheet1", data=df)
                st.success("Mise à jour réussie !")
                st.cache_data.clear()
                st.rerun()

except Exception as e:
    st.error("Une erreur est survenue lors du chargement.")
    st.exception(e) # Cela affichera l'erreur précise au lieu d'une page blanche
