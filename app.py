import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime, timedelta

# Configuration de la page
st.set_page_config(page_title="Gestion Congés", layout="wide")

st.title("📋 Système de Gestion des Congés")

try:
    # Connexion à Google Sheets
    conn = st.connection("gsheets", type=GSheetsConnection)

    def load_data():
        # Lecture de la feuille
        data = conn.read(worksheet="Sheet1", ttl=0)
        # Nettoyage des espaces dans les noms de colonnes
        data.columns = [str(c).strip() for c in data.columns]
        return data

    df = load_data()

    # Affichage du tableau de bord
    st.subheader("📊 Tableau des Employés")
    st.dataframe(df, use_container_width=True, hide_index=True)

    st.divider()

    # --- FORMULAIRE D'AFFECTATION ---
    st.subheader("✍️ Affectation de Congé")
    
    # Préparation de la liste de sélection
    col_nom = 'nom' if 'nom' in df.columns else df.columns[1]
    liste_employes = df['matricule'].astype(str) + " - " + df[col_nom].astype(str)
    
    choix = st.selectbox("Sélectionnez un employé pour mettre à jour son dossier", options=liste_employes)

    if choix:
        matricule_sel = choix.split(" - ")[0]
        # Extraction des infos de l'employé sélectionné
        emp_row = df[df['matricule'].astype(str) == matricule_sel].iloc[0]
        
        # Récupération sécurisée du reliquat
        col_rel = 'reliquat des congés'
        reliquat_actuel = float(emp_row[col_rel]) if col_rel in emp_row else 0

        with st.form("form_update"):
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("**Dates & Durée**")
                d_debut = st.date_input("Date début congé", datetime.now())
                d_fin = st.date_input("Date fin congé", datetime.now() + timedelta(days=1))
                
                # --- CALCULS AUTOMATIQUES ---
                duree = (d_fin - d_debut).days
                if duree < 0: duree = 0
                date_reprise = d_fin + timedelta(days=1)
                
                st.info(f"📏 Durée : {duree} jours | 📅 Reprise : {date_reprise.strftime('%d/%m/%Y')}")

            with col2:
                st.markdown("**Statut & Service**")
                nouveau_service = emp_row.get('service affecté', "")
                remarque = ""
                
                # LOGIQUE MÉTIER : Reliquat épuisé
                if reliquat_actuel <= 0:
                    st.error("⚠️ Reliquat épuisé ! Affectation vers un nouveau service requise.")
                    nouveau_service = st.text_input("Nouveau service d'affectation", value="")
                    remarque = "Affectation suite à épuisement de reliquat"
                else:
                    nouveau_service = st.text_input("Service affecté", value=nouveau_service)
                    st.success(f"✅ Reliquat disponible : {reliquat_actuel} jours")

            # Bouton de validation
            if st.form_submit_button("💾 Enregistrer les modifications"):
                # Localisation de la ligne dans le DataFrame d'origine
                idx = df.index[df['matricule'].astype(str) == matricule_sel].tolist()[0]
                
                # Mise à jour des valeurs calculées
                df.at[idx, 'date début congé'] = str(d_debut)
                df.at[idx, 'date fin congé'] = str(d_fin)
                df.at[idx, 'date reprise'] = str(date_reprise)
                df.at[idx, 'durrée'] = duree
                df.at[idx, 'reliquat des congés'] = reliquat_actuel - duree
                df.at[idx, 'service affecté'] = nouveau_service
                
                # Sauvegarde via la connexion Google Sheets
                try:
                    conn.update(worksheet="Sheet1", data=df)
                    st.success(f"Mise à jour réussie pour {emp_row[col_nom]} !")
                    st.cache_data.clear()
                    st.rerun()
                except Exception as save_error:
                    st.error(f"Erreur lors de la sauvegarde : {save_error}")

except Exception as e:
    st.error("🚨 Une erreur est survenue lors du chargement des données.")
    st.exception(e)
