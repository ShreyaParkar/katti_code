from flask import Flask, request, jsonify, session
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
import qrcode
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

# Initialize Flask app
app = Flask(__name__)
app.secret_key = 'your_secret_key'

# ✅ Configure CORS
CORS(app, supports_credentials=True)

# Configure SQLite database
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///bus_transport.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Define User model
class User(db.Model):
    user_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    wallet = db.Column(db.Integer, default=0)

# Define BusPass model (for bus routes)
class BusPass(db.Model):
    bus_pass_id = db.Column(db.Integer, primary_key=True)
    start_destination = db.Column(db.String(100), nullable=False)
    end_destination = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Integer, nullable=False)

# Define UserBusPass model (for purchased passes)
class UserBusPass(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.user_id'), nullable=False)
    bus_pass_id = db.Column(db.Integer, db.ForeignKey('bus_pass.bus_pass_id'), nullable=False)
    purchase_date = db.Column(db.DateTime, default=datetime.utcnow)

# Define TravelHistory model (for user travel history)
class TravelHistory(db.Model):
    travel_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.user_id'), nullable=False)
    bus_pass_id = db.Column(db.Integer, db.ForeignKey('bus_pass.bus_pass_id'), nullable=False)
    travel_date = db.Column(db.DateTime, default=datetime.utcnow)

# Define Ticket model (for one-time ticket purchases)
class Ticket(db.Model):
    ticket_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.user_id'), nullable=False)
    from_location = db.Column(db.String(100), nullable=False)
    to_location = db.Column(db.String(100), nullable=False)
    purchase_time = db.Column(db.DateTime, default=datetime.utcnow)

# ✅ Handle CORS preflight requests
@app.route('/register', methods=['OPTIONS'])
@app.route('/sign-in', methods=['OPTIONS'])
@app.route('/purchase_pass', methods=['OPTIONS'])
@app.route('/user_passes', methods=['OPTIONS'])
def handle_options():
    return jsonify({"message": "CORS preflight passed"}), 200

# ✅ User Registration
@app.route('/register', methods=['POST'])
def register_user():
    try:
        data = request.get_json()
        name, email = data.get('name'), data.get('email')

        if not name or not email:
            return jsonify({"error": "Name and email are required"}), 400

        if User.query.filter_by(email=email).first():
            return jsonify({"error": "Email already registered"}), 400

        user = User(name=name, email=email)
        db.session.add(user)
        db.session.commit()

        # Generate QR Code
        qr_path = f"static/qr_codes/{user.user_id}.png"
        os.makedirs(os.path.dirname(qr_path), exist_ok=True)
        qrcode.make(f"user_id:{user.user_id}").save(qr_path)

        return jsonify({
            "message": "User registered successfully!",
            "user_id": user.user_id,
            "qr_code": qr_path,
            "wallet_balance": user.wallet
        }), 201

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ✅ User Sign-In
@app.route('/sign-in', methods=['POST'])
def sign_in():
    data = request.get_json()
    email = data.get('email')

    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({"error": "User not found. Please register first."}), 401

    session['user_id'] = user.user_id  # Store user session

    return jsonify({
        "message": "Login successful",
        "user_id": user.user_id,
        "user_name": user.name,
        "user_email": user.email,
        "wallet_balance": user.wallet
    }), 200

# ✅ Get Bus Passes
@app.route('/bus_pass', methods=['GET'])
def get_bus_passes():
    bus_passes = BusPass.query.all()
    return jsonify({"bus_passes": [{
        "id": pass_.bus_pass_id,
        "start_destination": pass_.start_destination,
        "end_destination": pass_.end_destination,
        "price": pass_.price
    } for pass_ in bus_passes]}), 200

@app.route('/purchase_pass', methods=['POST'])
def purchase_pass():
    try:
        data = request.get_json()
        user_id, bus_pass_id = data.get('user_id'), data.get('bus_pass_id')

        print("Received user_id:", user_id)
        print("Received bus_pass_id:", bus_pass_id)

        user = User.query.get(user_id)
        bus_pass = BusPass.query.get(bus_pass_id)

        if not user:
            print("Error: User not found.")
            return jsonify({"error": "User not found."}), 404
        
        if not bus_pass:
            print("Error: Bus pass not found.")
            return jsonify({"error": "Bus pass not found."}), 404

        if user.wallet < bus_pass.price:
            print("Error: Insufficient wallet balance.")
            return jsonify({"error": "Insufficient wallet balance."}), 400

        # Check if user already purchased this pass
        existing_pass = UserBusPass.query.filter_by(user_id=user_id, bus_pass_id=bus_pass_id).first()
        if existing_pass:
            print("Error: Pass already purchased.")
            return jsonify({"error": "You have already purchased this pass."}), 400

        # Deduct price from wallet and store the purchase
        user.wallet -= bus_pass.price
        new_pass = UserBusPass(user_id=user_id, bus_pass_id=bus_pass_id)
        db.session.add(new_pass)
        db.session.commit()

        print("Success: Pass purchased successfully!")

        return jsonify({
            "message": "Bus pass purchased successfully!",
            "wallet_balance": user.wallet
        }), 200

    except Exception as e:
        print("Error:", str(e))  # Print the actual error in the Flask terminal
        return jsonify({"error": str(e)}), 500

# ✅ Get Purchased Passes for User (Dashboard)
@app.route('/user_passes/<int:user_id>', methods=['GET'])
def get_user_passes(user_id):
    try:
        user_passes = UserBusPass.query.filter_by(user_id=user_id).all()

        if not user_passes:
            return jsonify({"message": "No passes purchased yet."}), 200

        passes_data = []
        for user_pass in user_passes:
            bus_pass = BusPass.query.get(user_pass.bus_pass_id)
            passes_data.append({
                "id": bus_pass.bus_pass_id,
                "start_destination": bus_pass.start_destination,
                "end_destination": bus_pass.end_destination,
                "price": bus_pass.price,
                "purchase_date": user_pass.purchase_date.strftime("%Y-%m-%d %H:%M:%S")
            })

        return jsonify({"purchased_passes": passes_data}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ✅ Insert Predefined Bus Passes
def insert_bus_passes():
    predefined_passes = [
        {"start_destination": "MARGAO", "end_destination": "PANAJI", "price": 1000},
        {"start_destination": "MARGAO", "end_destination": "CANCONA", "price": 1200},
        {"start_destination": "MARGAO", "end_destination": "VASCO", "price": 950}
    ]

    for pass_data in predefined_passes:
        if not BusPass.query.filter_by(start_destination=pass_data["start_destination"], end_destination=pass_data["end_destination"], price=pass_data["price"]).first():
            db.session.add(BusPass(**pass_data))

    db.session.commit()
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

        user = User.query.get(user_id)
        if not user:
            return jsonify({"error": "User not found"}), 404

        # Ticket purchase time
        purchase_time = datetime.now()

        # Store ticket in database
        new_ticket = Ticket(
            user_id=user_id,
            from_location=from_location,
            to_location=to_location,
            purchase_time=purchase_time
        )

        db.session.add(new_ticket)
        db.session.commit()

        return jsonify({
            "message": "Ticket Purchased Successfully!",
            "ticket": {
                "from": from_location,
                "to": to_location,
                "purchase_time": purchase_time.strftime("%Y-%m-%d %H:%M:%S")
            }
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/user_tickets/<int:user_id>', methods=['GET'])
def get_user_tickets(user_id):
    try:
        tickets = Ticket.query.filter_by(user_id=user_id).all()

        if not tickets:
            return jsonify({"message": "No tickets purchased yet."}), 200

        return jsonify({
            "tickets": [{
                "from": ticket.from_location,
                "to": ticket.to_location,
                "purchase_time": ticket.purchase_time.strftime("%Y-%m-%d %H:%M:%S")
            } for ticket in tickets]
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
 
# ✅ Run Flask App
if __name__ == '__main__':
    with app.app_context():
        db.create_all()  # Create all tables
        insert_bus_passes()  # Insert predefined bus passes
    app.run(debug=True)