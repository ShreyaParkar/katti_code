from flask import Flask, request, jsonify, session
from flask_cors import CORS
from pymongo import MongoClient
from bson.objectid import ObjectId
import qrcode
import os
from datetime import datetime
import io
from flask import send_file  # Import send_file to serve images
from bson.binary import Binary  # Import Binary to store binary data in MongoDB

# Initialize Flask app
app = Flask(__name__)
app.secret_key = 'your_secret_key'

# ✅ Configure CORS
CORS(app, supports_credentials=True)

# ✅ Configure MongoDB
client = MongoClient("mongodb+srv://shrinidhi:Lenovoapple@cluster0.wnom9.mongodb.net/bus_transport?retryWrites=true&w=majority")
db = client["bus_transport"]

# ✅ User Registration with QR Code
@app.route('/register', methods=['POST'])
def register_user():
    try:
        data = request.get_json()
        name, email = data.get('name'), data.get('email')

        if not name or not email:
            return jsonify({"error": "Name and email are required"}), 400

        if db.users.find_one({"email": email}):
            return jsonify({"error": "Email already registered"}), 400

        # Generate QR Code as binary
        qr_data = f"user_id:{email}"
        qr = qrcode.make(qr_data)
        qr_bytes = io.BytesIO()
        qr.save(qr_bytes, format='PNG')
        qr_binary = Binary(qr_bytes.getvalue())  # Store as BSON Binary

        user = {"name": name, "email": email, "wallet": 0, "qr_code": qr_binary}
        user_id = db.users.insert_one(user).inserted_id

        return jsonify({
            "message": "User registered successfully!",
            "user_id": str(user_id),
            "wallet_balance": user["wallet"]
        }), 201

    except Exception as e:
        return jsonify({"error": str(e)}), 500



# ✅ Fetch and Serve User QR Code
@app.route('/get_qr/<user_id>', methods=['GET'])
def get_qr(user_id):
    try:
        user = db.users.find_one({"_id": ObjectId(user_id)})
        if not user or "qr_code" not in user:
            return jsonify({"error": "QR code not found"}), 404

        qr_binary = user["qr_code"]

        return send_file(io.BytesIO(qr_binary), mimetype='image/png')  # Serve as image
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ✅ User Sign-In
@app.route('/sign-in', methods=['POST'])
def sign_in():
    data = request.get_json()
    email = data.get('email')

    user = db.users.find_one({"email": email})
    if not user:
        return jsonify({"error": "User not found. Please register first."}), 401

    session['user_id'] = str(user['_id'])

    return jsonify({
        "message": "Login successful",
        "user_id": str(user['_id']),
        "user_name": user['name'],
        "user_email": user['email'],
        "wallet_balance": user['wallet']
    }), 200

# ✅ Get Bus Passes
@app.route('/bus_pass', methods=['GET'])
def get_bus_passes():
    bus_passes = list(db.bus_passes.find({}, {"_id": 1, "start_destination": 1, "end_destination": 1, "price": 1}))
    for pass_ in bus_passes:
        pass_["id"] = str(pass_["_id"])
        del pass_["_id"]
    return jsonify({"bus_passes": bus_passes}), 200

@app.route('/purchase_pass', methods=['POST'])
def purchase_pass():
    try:
        data = request.get_json()
        user_id, bus_pass_id = data.get('user_id'), data.get('bus_pass_id')

        user = db.users.find_one({"_id": ObjectId(user_id)})
        bus_pass = db.bus_passes.find_one({"_id": ObjectId(bus_pass_id)})

        if not user:
            return jsonify({"error": "User not found."}), 404
        if not bus_pass:
            return jsonify({"error": "Bus pass not found."}), 404
        if user['wallet'] < bus_pass['price']:
            return jsonify({"error": "Insufficient wallet balance."}), 400

        # Check if user already purchased this pass
        if db.user_passes.find_one({"user_id": user_id, "bus_pass_id": bus_pass_id}):
            return jsonify({"error": "You have already purchased this pass."}), 400

        # Deduct price from wallet and store the purchase
        db.users.update_one({"_id": ObjectId(user_id)}, {"$inc": {"wallet": -bus_pass['price']}})
        db.user_passes.insert_one({"user_id": user_id, "bus_pass_id": bus_pass_id, "purchase_date": datetime.utcnow()})

        return jsonify({
            "message": "Bus pass purchased successfully!",
            "wallet_balance": user['wallet'] - bus_pass['price']
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/purchase_ticket', methods=['POST'])
def purchase_ticket():
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        from_location = data.get('from_location')
        to_location = data.get('to_location')

        if not user_id or not from_location or not to_location:
            return jsonify({"error": "Missing required fields"}), 400
        if from_location == to_location:
            return jsonify({"error": "From and To locations cannot be the same"}), 400

        if not db.users.find_one({"_id": ObjectId(user_id)}):
            return jsonify({"error": "User not found"}), 404

        db.tickets.insert_one({
            "user_id": user_id,
            "from_location": from_location,
            "to_location": to_location,
            "purchase_time": datetime.utcnow()
        })

        return jsonify({"message": "Ticket Purchased Successfully!"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    # Insert predefined bus passes if not exist
    predefined_passes = [
        {"start_destination": "MARGAO", "end_destination": "PANAJI", "price": 1000},
        {"start_destination": "MARGAO", "end_destination": "CANCONA", "price": 1200},
        {"start_destination": "MARGAO", "end_destination": "VASCO", "price": 950}
    ]
    for pass_data in predefined_passes:
        if not db.bus_passes.find_one(pass_data):
            db.bus_passes.insert_one(pass_data)
    
    app.run(debug=True)
