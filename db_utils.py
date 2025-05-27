import mysql.connector
import pandas as pd
import os
from dotenv import load_dotenv
from pathlib import Path

load_dotenv()

def get_db_connection():
    return mysql.connector.connect(
        host=os.getenv('DB_HOST'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),
        database=os.getenv('DB_NAME'),
        port=os.getenv('DB_PORT', '3306')
    )

def initialize_database():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Create tables
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS drugs (
            id INT AUTO_INCREMENT PRIMARY KEY,
            drug_name VARCHAR(255) UNIQUE NOT NULL,
            department VARCHAR(50),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS stocktake_tables (
            id INT AUTO_INCREMENT PRIMARY KEY,
            table_name VARCHAR(255) NOT NULL,
            department VARCHAR(50) NOT NULL,
            access_code VARCHAR(50) UNIQUE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_by VARCHAR(100),
            is_active BOOLEAN DEFAULT TRUE
        )
        ''')
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS stocktake_records (
            id INT AUTO_INCREMENT PRIMARY KEY,
            table_id INT NOT NULL,
            drug_id INT NOT NULL,
            packs INT DEFAULT 0,
            singles INT DEFAULT 0,
            expiry_date DATE,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_by VARCHAR(100),
            FOREIGN KEY (table_id) REFERENCES stocktake_tables(id),
            FOREIGN KEY (drug_id) REFERENCES drugs(id)
        )
        ''')
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(100) UNIQUE NOT NULL,
            password VARCHAR(255) NOT NULL,
            department VARCHAR(50) NOT NULL,
            is_admin BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        # Insert admin users
        admins = [
            ("er_admin", "er_password123", "ER"),
            ("admission_admin", "admission_password123", "ADMISSION"),
            ("martenity_admin", "martenity_password123", "MARTENITY"),
            ("theatre_admin", "theatre_password123", "THEATRE"),
            ("lab_admin", "lab_password123", "LAB"),
            ("radiology_admin", "radiology_password123", "RADIOLOGY"),
            ("dentist_admin", "dentist_password123", "DENTIST"),
            ("super_admin", "super_password123", "SUPER_ADMIN")
        ]
        
        for username, password, department in admins:
            try:
                cursor.execute(
                    "INSERT INTO users (username, password, department, is_admin) VALUES (%s, %s, %s, TRUE)",
                    (username, password, department)
                )
            except mysql.connector.IntegrityError:
                conn.rollback()
        
        # Import drug names from Excel
        cursor.execute("SELECT COUNT(*) FROM drugs")
        if cursor.fetchone()['COUNT(*)'] == 0:
            try:
                df = pd.read_excel('STOCK TAKE FILE.xlsx')
                drug_names = df['DRUG NAME'].dropna().unique()
                
                for drug in drug_names:
                    try:
                        cursor.execute("INSERT INTO drugs (drug_name) VALUES (%s)", (drug,))
                    except mysql.connector.IntegrityError:
                        conn.rollback()
                
                conn.commit()
                print(f"✅ Inserted {len(drug_names)} drug names into database.")
            except Exception as e:
                print(f"❌ Error importing drug names: {e}")
                conn.rollback()
        
        conn.commit()
        print("✅ Database initialized successfully.")
        
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    initialize_database()