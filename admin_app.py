import streamlit as st
from db_utils import get_db_connection
import pandas as pd
import random
import string
from datetime import datetime
import io
import mysql.connector

# Page configuration
st.set_page_config(
    page_title="Hospital Stocktake - Admin",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Departments
DEPARTMENTS = [
    "ER", "ADMISSION", "MARTENITY", "THEATRE", 
    "LAB", "RADIOLOGY", "DENTIST"
]

def generate_access_code(length=8):
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

def authenticate(username, password):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM users WHERE username = %s AND password = %s", (username, password))
    user = cursor.fetchone()
    conn.close()
    return user["department"] if user else None

def login_page():
    st.title("Hospital Stocktake System - Admin Login")
    
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submit_button = st.form_submit_button("Login")
        
        if submit_button:
            department = authenticate(username, password)
            if department:
                st.session_state.authenticated = True
                st.session_state.department = department
                st.session_state.username = username
                st.session_state.current_page = "Home"
                st.success(f"Logged in successfully as {department} admin!")
                st.rerun()
            else:
                st.error("Invalid username or password")

def home_page():
    st.title("🏥 Hospital Stocktake System - Admin Portal")
    st.markdown("""
    ### Welcome to the Admin Portal
    
    Use the sidebar to navigate through different sections:
    - **Admin**: Manage stocktake tables and access codes
    - **Data**: View and export stocktake data
    - **Database**: Manage the master drug list
    - **About**: Learn more about the system
    """)
    
    st.info(f"Logged in as: {st.session_state.username} ({st.session_state.department} admin)")

def admin_page():
    st.title("📋 Stocktake Table Management")
    
    with st.expander("Create New Stocktake Table"):
        with st.form("new_table_form", clear_on_submit=True):
            table_name = st.text_input("Table Name")
            department = st.selectbox("Department", DEPARTMENTS, 
                                    index=DEPARTMENTS.index(st.session_state.department) 
                                    if st.session_state.department in DEPARTMENTS else 0)
            
            col1, col2 = st.columns(2)
            with col1:
                access_code = st.text_input("Access Code", value=generate_access_code())
            with col2:
                st.markdown("###")
                if st.form_submit_button("Generate New Code"):
                    access_code = generate_access_code()
                    st.session_state.new_access_code = access_code
            
            if 'new_access_code' in st.session_state:
                access_code = st.session_state.new_access_code
            
            submit_button = st.form_submit_button("Create Table")
            
            if submit_button:
                if not table_name or not department or not access_code:
                    st.error("Please fill in all fields")
                else:
                    conn = get_db_connection()
                    cursor = conn.cursor(dictionary=True)
                    try:
                        # Insert new stocktake table
                        cursor.execute(
                            "INSERT INTO stocktake_tables (table_name, department, access_code, created_by) VALUES (%s, %s, %s, %s)",
                            (table_name, department, access_code, st.session_state.username)
                        )
                        conn.commit()
                        
                        # Get the newly created table ID
                        table_id = cursor.lastrowid
                        
                        # Get all drugs from database
                        cursor.execute("SELECT id FROM drugs")
                        drug_ids = [row['id'] for row in cursor.fetchall()]
                        
                        # Insert records for all drugs
                        for drug_id in drug_ids:
                            cursor.execute(
                                "INSERT INTO stocktake_records (table_id, drug_id) VALUES (%s, %s)",
                                (table_id, drug_id)
                            )
                        conn.commit()
                        
                        st.success(f"Table '{table_name}' created with access code: {access_code}")
                        if 'new_access_code' in st.session_state:
                            del st.session_state.new_access_code
                    except mysql.connector.Error as e:
                        st.error(f"Database error: {e}")
                    finally:
                        cursor.close()
                        conn.close()

    # View existing tables code remains the same...

    st.subheader("Existing Stocktake Tables")
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        "SELECT id, table_name, department, access_code, created_at FROM stocktake_tables ORDER BY created_at DESC"
    )
    tables = cursor.fetchall()
    cursor.close()
    conn.close()
    
    if not tables:
        st.info("No tables created yet.")
    else:
        if st.session_state.department != "SUPER_ADMIN":
            tables = [t for t in tables if t["department"] == st.session_state.department]
        
        if tables:
            df = pd.DataFrame(tables)
            df["Created At"] = pd.to_datetime(df["created_at"]).dt.strftime('%Y-%m-%d %H:%M')
            st.dataframe(df.drop(columns=["id", "created_at"]), hide_index=True)

def data_page():
    st.title("📊 Stocktake Data")
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute(
        "SELECT id, table_name, department, created_at FROM stocktake_tables ORDER BY created_at DESC"
    )
    tables = cursor.fetchall()
    
    if st.session_state.department != "SUPER_ADMIN":
        tables = [t for t in tables if t["department"] == st.session_state.department]
    
    if not tables:
        st.info("No tables available.")
        cursor.close()
        conn.close()
        return
    
    table_options = {f"{t['table_name']} ({t['department']}, {t['created_at']})": t['id'] for t in tables}
    selected_table = st.selectbox("Select Table", list(table_options.keys()))
    
    if selected_table:
        table_id = table_options[selected_table]
        
        cursor.execute('''
            SELECT d.drug_name, sr.packs, sr.singles, sr.expiry_date, sr.last_updated
            FROM stocktake_records sr
            JOIN drugs d ON sr.drug_id = d.id
            WHERE sr.table_id = %s
            ORDER BY d.drug_name
        ''', (table_id,))
        records = cursor.fetchall()
        
        if records:
            df = pd.DataFrame(records)
            df["Last Updated"] = pd.to_datetime(df["last_updated"]).dt.strftime('%Y-%m-%d %H:%M')
            st.dataframe(df.drop(columns=["last_updated"]), hide_index=True)
            
            st.subheader("Export Data")
            col1, col2, col3 = st.columns(3)
            with col1:
                csv = df.to_csv(index=False).encode('utf-8')
                st.download_button("Export to CSV", data=csv, file_name="stocktake.csv", mime="text/csv")
            with col2:
                excel_buffer = io.BytesIO()
                with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                    df.to_excel(writer, index=False)
                st.download_button("Export to Excel", data=excel_buffer.getvalue(), 
                                 file_name="stocktake.xlsx", 
                                 mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            with col3:
                if st.button("Delete Table"):
                    if st.checkbox("Confirm deletion"):
                        cursor.execute("DELETE FROM stocktake_records WHERE table_id = %s", (table_id,))
                        cursor.execute("DELETE FROM stocktake_tables WHERE id = %s", (table_id,))
                        conn.commit()
                        st.success("Table deleted!")
                        st.rerun()
        else:
            st.info("No records found.")
    
    cursor.close()
    conn.close()

def database_page():
    st.title("💾 Drug Database")
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("SELECT id, drug_name, department FROM drugs ORDER BY drug_name")
    drugs = cursor.fetchall()
    
    search_term = st.text_input("Search Drugs")
    if search_term:
        drugs = [d for d in drugs if search_term.lower() in d["drug_name"].lower()]
    
    department_filter = st.selectbox("Filter Department", ["All"] + DEPARTMENTS)
    if department_filter != "All":
        drugs = [d for d in drugs if d["department"] == department_filter]
    
    if drugs:
        df = pd.DataFrame(drugs)
        st.dataframe(df.drop(columns=["id"]), hide_index=True)
    else:
        st.info("No drugs found.")
    
    with st.expander("Add New Drug"):
        with st.form("add_drug_form", clear_on_submit=True):
            drug_name = st.text_input("Drug Name")
            department = st.selectbox("Department", ["None"] + DEPARTMENTS)
            if st.form_submit_button("Add"):
                if drug_name:
                    try:
                        cursor.execute(
                            "INSERT INTO drugs (drug_name, department) VALUES (%s, %s)",
                            (drug_name, department if department != "None" else None)
                        )
                        conn.commit()
                        st.success("Drug added!")
                        st.rerun()
                    except mysql.connector.IntegrityError:
                        st.error("Drug already exists")
    
    st.subheader("Export Drug List")
    if drugs:
        csv = pd.DataFrame(drugs).to_csv(index=False).encode('utf-8')
        st.download_button("Export CSV", data=csv, file_name="drugs.csv", mime="text/csv")
    
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
            'username': None,
            'current_page': "Home"
        })

    st.sidebar.title("Navigation")
    if st.session_state.authenticated:
        st.sidebar.success(f"Logged in as {st.session_state.username}")
        
        pages = {
            "Home": home_page,
            "Admin": admin_page,
            "Data": data_page,
            "Database": database_page,
            "About": about_page
        }
        
        selected_page = st.sidebar.radio("Go to", list(pages.keys()))
        
        st.sidebar.markdown("---")
        if st.sidebar.button("Logout"):
            st.session_state.authenticated = False
            st.rerun()
        
        pages[selected_page]()
    else:
        login_page()

if __name__ == "__main__":
    main()