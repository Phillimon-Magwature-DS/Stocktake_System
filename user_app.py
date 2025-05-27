import streamlit as st
from db_utils import get_db_connection
import pandas as pd
from datetime import datetime
import time

# Page configuration
st.set_page_config(
    page_title="Hospital Stocktake - User",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded"
)

DEPARTMENTS = [
    "ER", "ADMISSION", "MARTENITY", "THEATRE", 
    "LAB", "RADIOLOGY", "DENTIST"
]

def home_page():
    st.title("🏥 Hospital Stocktake System")
    st.markdown("### Welcome to the Stocktake Portal")
    if st.session_state.authenticated:
        st.info(f"Currently working in: {st.session_state.department}")

def stocktake_page():
    if not st.session_state.authenticated:
        st.warning("Please select a department first")
        return
    
    st.title("📝 Stocktake Entry")
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    search_term = st.text_input("Search Drugs")
    
    cursor.execute('''
        SELECT sr.id, d.drug_name, sr.packs, sr.singles, sr.expiry_date
        FROM stocktake_records sr
        JOIN drugs d ON sr.drug_id = d.id
        WHERE sr.table_id = %s
        ORDER BY d.drug_name
    ''', (st.session_state.current_table_id,))
    records = cursor.fetchall()
    
    if search_term:
        records = [r for r in records if search_term.lower() in r["drug_name"].lower()]
    
    if not records:
        st.info("No drugs found")
    else:
        for record in records:
            cols = st.columns([3, 1, 1, 1, 2])
            with cols[0]:
                st.markdown(f"**{record['drug_name']}**")
            with cols[1]:
                packs = st.number_input("Packs", min_value=0, value=record["packs"], key=f"packs_{record['id']}")
            with cols[2]:
                singles = st.number_input("Singles", min_value=0, value=record["singles"], key=f"singles_{record['id']}")
            with cols[3]:
                expiry = st.text_input("Expiry", value=record["expiry_date"] or "", key=f"expiry_{record['id']}")
            with cols[4]:
                if st.button("Update", key=f"update_{record['id']}"):
                    cursor.execute('''
                        UPDATE stocktake_records 
                        SET packs = %s, singles = %s, expiry_date = %s, last_updated = %s
                        WHERE id = %s
                    ''', (packs, singles, expiry if expiry else None, datetime.now(), record["id"]))
                    conn.commit()
                    st.success("Updated!")
                    time.sleep(1)
                    st.rerun()
    
    cursor.close()
    conn.close()

def data_page():
    if not st.session_state.authenticated:
        st.warning("Please select a department first")
        return
    
    st.title("📊 View Stocktake Data")
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute(
        "SELECT id, table_name, created_at FROM stocktake_tables WHERE department = %s ORDER BY created_at DESC",
        (st.session_state.department,)
    )
    tables = cursor.fetchall()
    
    if tables:
        table_options = {f"{t['table_name']} ({t['created_at']})": t['id'] for t in tables}
        selected_table = st.selectbox("Select Table", list(table_options.keys()))
        
        if selected_table:
            cursor.execute('''
                SELECT d.drug_name, sr.packs, sr.singles, sr.expiry_date, sr.last_updated
                FROM stocktake_records sr
                JOIN drugs d ON sr.drug_id = d.id
                WHERE sr.table_id = %s
                ORDER BY d.drug_name
            ''', (table_options[selected_table],))
            records = cursor.fetchall()
            
            if records:
                df = pd.DataFrame(records)
                df["Last Updated"] = pd.to_datetime(df["last_updated"]).dt.strftime('%Y-%m-%d %H:%M')
                st.dataframe(df.drop(columns=["last_updated"]), hide_index=True)
            else:
                st.info("No records found")
    else:
        st.info("No tables available")
    
    cursor.close()
    conn.close()

def about_page():
    st.title("ℹ️ About")
    st.markdown("""
    ### Hospital Stocktake System
    **Version:** 1.0  
    **Developed by:** Corporate 24 Healthcare
    """)

def main():
    if 'authenticated' not in st.session_state:
        st.session_state.update({
            'authenticated': False,
            'department': None,
            'current_table': None,
            'current_table_id': None
        })

    st.sidebar.title("Stocktake System")
    
    if not st.session_state.authenticated:
        department = st.sidebar.selectbox("Department", DEPARTMENTS)
        access_code = st.sidebar.text_input("Access Code", type="password")
        
        if st.sidebar.button("Start Stocktake"):
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                "SELECT id, table_name, department FROM stocktake_tables WHERE access_code = %s",
                (access_code,)
            )
            table = cursor.fetchone()
            cursor.close()
            conn.close()
            
            if table:
                if table["department"] == department:
                    st.session_state.update({
                        'authenticated': True,
                        'department': department,
                        'current_table': table["table_name"],
                        'current_table_id': table["id"]
                    })
                    st.sidebar.success(f"Access granted to {table['table_name']}")
                    st.rerun()
                else:
                    st.sidebar.error("Code doesn't match department")
            else:
                st.sidebar.error("Invalid access code")
    
    if st.session_state.authenticated:
        st.sidebar.success(f"Department: {st.session_state.department}")
        st.sidebar.info(f"Table: {st.session_state.current_table}")
        
        if st.sidebar.button("Switch Department"):
            st.session_state.authenticated = False
            st.rerun()
    
    pages = {
        "Home": home_page,
        "Stocktake": stocktake_page,
        "Data": data_page,
        "About": about_page
    }
    
    selected_page = st.sidebar.radio("Go to", list(pages.keys()))
    pages[selected_page]()

if __name__ == "__main__":
    main()