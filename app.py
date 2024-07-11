from flask import Flask, jsonify, request
import json
app = Flask(__name__)

# Route to return an array from a JSON
@app.route('/api/locations', methods=['GET'])
def get_array():
    with open('locations.json', 'r') as file:
        data = json.load(file)
    return jsonify(data)

# Route for login
@app.route('/api/login', methods=['POST'])
def login():
    # Predefined username and password
    predefined_username = "admin"
    predefined_password = "password"

    # Get the JSON data from the request
    auth_data = request.get_json()

    if auth_data is None:
        return jsonify({"message": "Invalid input"}), 400

    username = auth_data.get('username')
    password = auth_data.get('password')

    if username == predefined_username and password == predefined_password:
        return jsonify({"message": "Login successful"}), 200
    else:
        return jsonify({"message": "Invalid credentials"}), 401

if __name__ == '__main__':
    app.run(debug=True)
