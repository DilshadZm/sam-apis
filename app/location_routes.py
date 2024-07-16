from flask import Blueprint, jsonify, request
import sqlite3
import os
import tempfile
from werkzeug.utils import secure_filename
from app.database import get_db_connection, upload_database, download_database

location_bp = Blueprint('location', __name__)

def row_to_dict(row):
    return {
        "locationId": row[0],
        "name": row[1],
        "address": row[2],
        "city": row[3],
        "state": row[4],
        "zipcode": row[5]
    }

@location_bp.route('/api/locations', methods=['GET'])
def get_locations():
    conn, temp_db_name = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM Location")
    locations = [row_to_dict(row) for row in c.fetchall()]
    conn.close()
    os.unlink(temp_db_name)
    return jsonify(locations)

@location_bp.route('/api/locations', methods=['POST'])
def add_location():
    location_data = request.get_json()
    
    if not location_data:
        return jsonify({"message": "Invalid input"}), 400
    
    conn, temp_db_name = get_db_connection()
    c = conn.cursor()
    
    try:
        c.execute("SELECT * FROM Location WHERE locationId = ?", (location_data['locationId'],))
        if c.fetchone():
            conn.close()
            os.unlink(temp_db_name)
            return jsonify({"message": "Location with this ID already exists"}), 409
        
        c.execute('''INSERT INTO Location (locationId, name, address, city, state, zipcode)
                     VALUES (?, ?, ?, ?, ?, ?)''',
                  (location_data['locationId'], location_data['name'], location_data['address'],
                   location_data['city'], location_data['state'], location_data['zipcode']))
        conn.commit()
        
        # Upload the updated database to Azure Blob Storage
        with open(temp_db_name, 'rb') as file:
            db_content = file.read()
        upload_success = upload_database(db_content)
        
        conn.close()
        os.unlink(temp_db_name)
        
        if upload_success:
            return jsonify({"message": "Location added successfully"}), 201
        else:
            return jsonify({"message": "Location added but failed to update cloud storage"}), 500
    except Exception as e:
        conn.close()
        os.unlink(temp_db_name)
        return jsonify({"message": f"Error: {str(e)}"}), 500

@location_bp.route('/api/bulk-import', methods=['POST'])
def bulk_import():
    if 'file' not in request.files:
        return jsonify({"message": "No file part"}), 400
    
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({"message": "No selected file"}), 400
    
    if not file.filename.endswith('.db'):
        return jsonify({"message": "Invalid file type. Please upload a SQLite database file"}), 400

    # Create a temporary directory to store the uploaded file
    temp_dir = tempfile.mkdtemp()
    temp_path = os.path.join(temp_dir, secure_filename(file.filename))
    file.save(temp_path)

    try:
        # Connect to the uploaded database
        temp_conn = sqlite3.connect(temp_path)
        temp_cursor = temp_conn.cursor()

        # Define the tables to import
        tables_to_import = ['Location', 'Equipment']  # Add more tables here in the future

        # Check if the required tables exist in the uploaded database
        for table in tables_to_import:
            temp_cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}'")
            if not temp_cursor.fetchone():
                return jsonify({"message": f"The uploaded database does not contain a '{table}' table"}), 400

        # Download the current database from Azure Blob Storage
        current_db_data = download_database()
        if current_db_data is None:
            return jsonify({"message": "Failed to download current database from Azure"}), 500

        # Create a temporary file for the current database
        current_temp_db = tempfile.NamedTemporaryFile(delete=False)
        current_temp_db.write(current_db_data)
        current_temp_db.close()

        # Connect to the current database
        main_conn = sqlite3.connect(current_temp_db.name)
        main_cursor = main_conn.cursor()

        # Begin transaction
        main_conn.execute('BEGIN TRANSACTION')

        import_counts = {}

        try:
            for table in tables_to_import:
                # Fetch all rows from the uploaded database
                temp_cursor.execute(f"SELECT * FROM {table}")
                new_rows = temp_cursor.fetchall()

                # Get column names
                temp_cursor.execute(f"PRAGMA table_info({table})")
                columns = [column[1] for column in temp_cursor.fetchall()]

                import_counts[table] = 0

                for row in new_rows:
                    # Check if the row already exists (assuming first column is the primary key)
                    main_cursor.execute(f"SELECT * FROM {table} WHERE {columns[0]} = ?", (row[0],))
                    if main_cursor.fetchone():
                        # Update existing row
                        set_clause = ', '.join([f"{col} = ?" for col in columns[1:]])
                        main_cursor.execute(f'''UPDATE {table} 
                                               SET {set_clause}
                                               WHERE {columns[0]} = ?''', 
                                            row[1:] + (row[0],))
                    else:
                        # Insert new row
                        placeholders = ', '.join(['?' for _ in row])
                        main_cursor.execute(f'''INSERT INTO {table} 
                                               ({', '.join(columns)})
                                               VALUES ({placeholders})''', row)
                    
                    import_counts[table] += 1

            # Commit the transaction
            main_conn.commit()

            # Upload the updated database to Azure Blob Storage
            with open(current_temp_db.name, 'rb') as updated_db_file:
                upload_success = upload_database(updated_db_file.read())

            if upload_success:
                message = '; '.join([f"Imported {count} {table}s" for table, count in import_counts.items()])
                return jsonify({"message": f"Successfully {message}"}), 200
            else:
                return jsonify({"message": "Import successful but failed to update cloud storage"}), 500

        except Exception as e:
            # If any error occurs, rollback the transaction
            main_conn.rollback()
            return jsonify({"message": f"An error occurred during import: {str(e)}"}), 500

        finally:
            main_conn.close()
            os.unlink(current_temp_db.name)

    except Exception as e:
        return jsonify({"message": f"An error occurred while processing the file: {str(e)}"}), 500

    finally:
        temp_conn.close()
        os.remove(temp_path)
        os.rmdir(temp_dir)