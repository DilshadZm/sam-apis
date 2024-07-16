from flask import Blueprint, jsonify, request

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/api/login', methods=['POST'])
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
