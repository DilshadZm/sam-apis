from flask import Blueprint, jsonify, request
from app.database import get_db_connection, upload_database
import os

equipment_bp = Blueprint('equipment', __name__)

@equipment_bp.route('/api/equipment', methods=['GET'])
def get_equipment():
    conn, temp_db_name = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM Equipment")
    equipment = [dict(zip([column[0] for column in c.description], row)) for row in c.fetchall()]
    conn.close()
    os.unlink(temp_db_name)
    return jsonify(equipment)

@equipment_bp.route('/api/equipment', methods=['POST'])
def add_equipment():
    equipment_data = request.get_json()
    
    if not equipment_data:
        return jsonify({"message": "Invalid input"}), 400
    
    conn, temp_db_name = get_db_connection()
    c = conn.cursor()
    
    try:
        c.execute("SELECT * FROM Equipment WHERE equipmentId = ?", (equipment_data['equipmentId'],))
        if c.fetchone():
            conn.close()
            os.unlink(temp_db_name)
            return jsonify({"message": "Equipment with this ID already exists"}), 409
        
        c.execute('''INSERT INTO Equipment (equipmentId, name, type, status, purchaseDate, locationId)
                     VALUES (?, ?, ?, ?, ?, ?)''',
                  (equipment_data['equipmentId'], equipment_data['name'], equipment_data['type'],
                   equipment_data['status'], equipment_data['purchaseDate'], equipment_data['locationId']))
        conn.commit()
        
        with open(temp_db_name, 'rb') as file:
            db_content = file.read()
        upload_success = upload_database(db_content)
        
        conn.close()
        os.unlink(temp_db_name)
        
        if upload_success:
            return jsonify({"message": "Equipment added successfully"}), 201
        else:
            return jsonify({"message": "Equipment added but failed to update cloud storage"}), 500
    except Exception as e:
        conn.close()
        os.unlink(temp_db_name)
        return jsonify({"message": f"Error: {str(e)}"}), 500