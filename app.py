from flask import Flask, jsonify, request, send_file
import sqlite3
import os
import tempfile

app = Flask(__name__)

# Database setup
def init_db():
    conn = sqlite3.connect('zertify.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS locations
                 (locationId INTEGER PRIMARY KEY,
                  name TEXT,
                  address TEXT,
                  city TEXT,
                  state TEXT,
                  zipcode TEXT)''')
    conn.commit()
    conn.close()

init_db()

# Helper function to convert row to dictionary
def row_to_dict(row):
    return {
        "locationId": row[0],
        "name": row[1],
        "address": row[2],
        "city": row[3],
        "state": row[4],
        "zipcode": row[5]
    }

# Route to return all locations
@app.route('/api/locations', methods=['GET'])
def get_locations():
    conn = sqlite3.connect('zertify.db')
    c = conn.cursor()
    c.execute("SELECT * FROM locations")
    locations = [row_to_dict(row) for row in c.fetchall()]
    conn.close()
    return jsonify(locations)

# Route to add a new location
@app.route('/api/locations', methods=['POST'])
def add_location():
    location_data = request.get_json()
    
    if not location_data:
        return jsonify({"message": "Invalid input"}), 400
    
    conn = sqlite3.connect('zertify.db')
    c = conn.cursor()
    
    # Check if locationId already exists
    c.execute("SELECT * FROM locations WHERE locationId = ?", (location_data['locationId'],))
    if c.fetchone():
        conn.close()
        return jsonify({"message": "Location with this ID already exists"}), 409
    
    # Insert new location
    c.execute('''INSERT INTO locations (locationId, name, address, city, state, zipcode)
                 VALUES (?, ?, ?, ?, ?, ?)''',
              (location_data['locationId'], location_data['name'], location_data['address'],
               location_data['city'], location_data['state'], location_data['zipcode']))
    conn.commit()
    conn.close()
    
    return jsonify({"message": "Location added successfully"}), 201

# Route for login (unchanged)
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

# New route for bulk import from SQLite file
@app.route('/api/bulk-import', methods=['POST'])
def bulk_import():
    if 'file' not in request.files:
        return jsonify({"message": "No file part"}), 400
    
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({"message": "No selected file"}), 400
    
    if not file.filename.endswith('.db'):
        return jsonify({"message": "Invalid file type. Please upload a SQLite database file"}), 400

    # Save the uploaded file temporarily
    temp_dir = tempfile.mkdtemp()
    temp_path = os.path.join(temp_dir, 'temp.db')
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

        # Connect to the main database
        main_conn = sqlite3.connect('zertify.db')
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
            
            return jsonify({"message": f"Successfully imported {len(new_locations)} locations"}), 200

        except Exception as e:
            # If any error occurs, rollback the transaction
            main_conn.rollback()
            return jsonify({"message": f"An error occurred during import: {str(e)}"}), 500

        finally:
            main_conn.close()

    except Exception as e:
        return jsonify({"message": f"An error occurred while processing the file: {str(e)}"}), 500

    finally:
        temp_conn.close()
        os.remove(temp_path)
        os.rmdir(temp_dir)


if __name__ == '__main__':
    app.run(debug=True)