# from app.main import create_app

# app = create_app()

# if __name__ == '__main__':
#     app.run(debug=True)
from flask import Flask, jsonify
import json
import os

app = Flask(__name__)

# Define the directory containing the JSON files
data_dir = os.path.join(os.path.dirname(__file__), 'data')

# Helper function to load JSON data from a file
def load_json(filename):
    filepath = os.path.join(data_dir, filename)
    with open(filepath, 'r') as file:
        return json.load(file)

# Routes for each model
@app.route('/api/areas', methods=['GET'])
def get_areas():
    areas = load_json('Area.json')
    return jsonify(areas)

@app.route('/api/manufacturers', methods=['GET'])
def get_manufacturers():
    manufacturers = load_json('Manufacturer.json')
    return jsonify(manufacturers)

@app.route('/api/sites', methods=['GET'])
def get_sites():
    sites = load_json('Site.json')
    return jsonify(sites)

@app.route('/api/locations', methods=['GET'])
def get_locations():
    locations = load_json('Location.json')
    return jsonify(locations)

if __name__ == '__main__':
    app.run(debug=True)
