from flask import Flask, jsonify, request
import sqlite3
import os
import tempfile
from azure.storage.blob import BlobServiceClient, BlobClient, ContainerClient
import io
from werkzeug.utils import secure_filename

app = Flask(__name__)


# Azure Blob Storage settings
connection_string = os.environ.get('AZURE_STORAGE_CONNECTION_STRING')
if not connection_string:
    raise ValueError("AZURE_STORAGE_CONNECTION_STRING is not set in the environment variables")
container_name = "images"
blob_name = "zertify.db"

def get_blob_service_client():
    return BlobServiceClient.from_connection_string(connection_string)

def download_database():
    blob_service_client = get_blob_service_client()
    blob_client = blob_service_client.get_blob_client(container=container_name, blob=blob_name)

    try:
        print(f"Attempting to download database from Azure Blob Storage")
        blob_data = blob_client.download_blob()
        return blob_data.readall()
    except Exception as e:
        print(f"Error downloading database file: {str(e)}")
        return None

def upload_database(file_data):
    blob_service_client = get_blob_service_client()
    blob_client = blob_service_client.get_blob_client(container=container_name, blob=blob_name)

    try:
        print(f"Attempting to upload database to Azure Blob Storage")
        blob_client.upload_blob(file_data, overwrite=True)
        print("Database uploaded successfully")
        return True
    except Exception as e:
        print(f"Error uploading database file: {str(e)}")
        return False

def init_db():
    db_data = download_database()
    
    if db_data is None:
        print("Database not found in Azure Blob Storage. Creating a new one.")
        conn = sqlite3.connect(':memory:')
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS locations
                     (locationId INTEGER PRIMARY KEY,
                      name TEXT,
                      address TEXT,
                      city TEXT,
                      state TEXT,
                      zipcode TEXT)''')
        conn.commit()
        
        # Save the new database to Azure Blob Storage
        buffer = io.BytesIO()
        for line in conn.iterdump():
            buffer.write(f'{line}\n'.encode('utf-8'))
        buffer.seek(0)
        upload_database(buffer.getvalue())
    else:
        print("Database found in Azure Blob Storage.")

# Initialize the database
init_db()

def get_db_connection():
    db_data = download_database()
    if db_data is None:
        raise Exception("Failed to download database")
    
    temp_db = tempfile.NamedTemporaryFile(delete=False)
    temp_db.write(db_data)
    temp_db.close()
    
    conn = sqlite3.connect(temp_db.name)
    return conn, temp_db.name

def row_to_dict(row):
    return {
        "locationId": row[0],
        "name": row[1],
        "address": row[2],
        "city": row[3],
        "state": row[4],
        "zipcode": row[5]
    }

@app.route('/api/locations', methods=['GET'])
def get_locations():
    conn, temp_db_name = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM locations")
    locations = [row_to_dict(row) for row in c.fetchall()]
    conn.close()
    os.unlink(temp_db_name)
    return jsonify(locations)

@app.route('/api/locations', methods=['POST'])
def add_location():
    location_data = request.get_json()
    
    if not location_data:
        return jsonify({"message": "Invalid input"}), 400
    
    conn, temp_db_name = get_db_connection()
    c = conn.cursor()
    
    try:
        c.execute("SELECT * FROM locations WHERE locationId = ?", (location_data['locationId'],))
        if c.fetchone():
            conn.close()
            os.unlink(temp_db_name)
            return jsonify({"message": "Location with this ID already exists"}), 409
        
        c.execute('''INSERT INTO locations (locationId, name, address, city, state, zipcode)
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

@app.route('/api/login', methods=['POST'])
def login():
    predefined_username = "admin"
    predefined_password = "password"

    auth_data = request.get_json()

    if auth_data is None:
        return jsonify({"message": "Invalid input"}), 400

    username = auth_data.get('username')
    password = auth_data.get('password')

    if username == predefined_username and password == predefined_password:
        return jsonify({"message": "Login successful"}), 200
    else:
        return jsonify({"message": "Invalid credentials"}), 401

@app.route('/api/bulk-import', methods=['POST'])
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

        # Check if the 'locations' table exists in the uploaded database
        temp_cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='locations'")
        if not temp_cursor.fetchone():
            return jsonify({"message": "The uploaded database does not contain a 'locations' table"}), 400

        # Fetch all locations from the uploaded database
        temp_cursor.execute("SELECT * FROM locations")
        new_locations = temp_cursor.fetchall()

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

        try:
            for location in new_locations:
                # Check if the location already exists
                main_cursor.execute("SELECT * FROM locations WHERE locationId = ?", (location[0],))
                if main_cursor.fetchone():
                    # Update existing location
                    main_cursor.execute('''UPDATE locations 
                                           SET name = ?, address = ?, city = ?, state = ?, zipcode = ?
                                           WHERE locationId = ?''', 
                                        (location[1], location[2], location[3], location[4], location[5], location[0]))
                else:
                    # Insert new location
                    main_cursor.execute('''INSERT INTO locations 
                                           (locationId, name, address, city, state, zipcode)
                                           VALUES (?, ?, ?, ?, ?, ?)''', location)

            # Commit the transaction
            main_conn.commit()

            # Upload the updated database to Azure Blob Storage
            with open(current_temp_db.name, 'rb') as updated_db_file:
                upload_success = upload_database(updated_db_file.read())

            if upload_success:
                return jsonify({"message": f"Successfully imported {len(new_locations)} locations"}), 200
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

if __name__ == '__main__':
    app.run(debug=True)