import sqlite3
import os
import tempfile
from azure.storage.blob import BlobServiceClient
import io

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
        
        c.execute('''CREATE TABLE IF NOT EXISTS Location
                     (locationId INTEGER PRIMARY KEY,
                      name TEXT,
                      address TEXT,
                      city TEXT,
                      state TEXT,
                      zipcode TEXT)''')
        
        # Create Equipment table
        c.execute('''CREATE TABLE IF NOT EXISTS Equipment
                     (equipmentId INTEGER PRIMARY KEY,
                      name TEXT,
                      type TEXT,
                      status TEXT,
                      purchaseDate TEXT,
                      locationId INTEGER,
                      FOREIGN KEY(locationId) REFERENCES Location(locationId))''')
        
        conn.commit()
        
        # Save the new database to Azure Blob Storage
        buffer = io.BytesIO()
        for line in conn.iterdump():
            buffer.write(f'{line}\n'.encode('utf-8'))
        buffer.seek(0)
        upload_database(buffer.getvalue())
    else:
        print("Database found in Azure Blob Storage.")

def get_db_connection():
    db_data = download_database()
    if db_data is None:
        raise Exception("Failed to download database")
    
    temp_db = tempfile.NamedTemporaryFile(delete=False)
    temp_db.write(db_data)
    temp_db.close()
    
    conn = sqlite3.connect(temp_db.name)
    return conn, temp_db.name
