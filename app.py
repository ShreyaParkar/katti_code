from flask import Flask, request, jsonify, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
import qrcode
import os
import requests
from flask import Flask, render_template, request, jsonify, make_response

# Initialize Flask application
app = Flask(__name__)
 
# Enable CORS for the app
CORS(app)  # Allow all origins and all routes

 
# Configure SQLite database
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///bus_transport.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False  # Disable unnecessary warnings
 
# Initialize SQLAlchemy
db = SQLAlchemy(app)
 
# Define User model with wallet column
class User(db.Model):
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    wallet = db.Column(db.Integer, default=0)
 
    travel_records = db.relationship('TravelRecord', backref='user', lazy=True)
 
    def __repr__(self):
        return f'<User {self.name}, {self.email}, Wallet: {self.wallet}>'
 
# Define TravelRecord model
class TravelRecord(db.Model):
    __tablename__ = 'travel_record'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    start_lat = db.Column(db.Float, nullable=True)
    start_lng = db.Column(db.Float, nullable=True)
    end_lat = db.Column(db.Float, nullable=True)
    end_lng = db.Column(db.Float, nullable=True)
    distance = db.Column(db.Float, nullable=True)
 
    def __repr__(self):
        return f'<TravelRecord {self.user_id}, {self.start_lat}, {self.start_lng}, {self.end_lat}, {self.end_lng}, {self.distance}>'
 
# Define BusPass model with validity_days column
class BusPass(db.Model):
    __tablename__ = 'bus_pass'
    id = db.Column(db.Integer, primary_key=True)
    start_destination = db.Column(db.String(100), nullable=False)
    end_destination = db.Column(db.String(100), nullable=False)
    validity_days = db.Column(db.Integer, nullable=False)
 
    def __repr__(self):
        return f'<BusPass {self.start_destination} -> {self.end_destination}, {self.validity_days} days>'
 
# Create the database tables
with app.app_context():
    db.create_all()
 
# Route for User Registration
@app.route('/register', methods=['POST'])
def register_user():
    try:
        data = request.get_json()
        name = data.get('name')
        email = data.get('email')
 
        # Check if email already exists
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            return jsonify({"error": "Email already registered"}), 400
 
        # Create new user and add to the database
        user = User(name=name, email=email)
        db.session.add(user)
        db.session.commit()
 
        # Generate QR code
        user_qr = qrcode.make(f"user_id:{user.id}")
        qr_folder = "static/qr_codes"
        os.makedirs(qr_folder, exist_ok=True)
        qr_file = os.path.join(qr_folder, f"{user.id}.png")
        user_qr.save(qr_file)
 
        # Prepare the data to send back
        travel_history = [{"start_lat": r.start_lat, "start_lng": r.start_lng, "end_lat": r.end_lat, "end_lng": r.end_lng, "distance": r.distance} for r in user.travel_records]
        return jsonify({
            "user_id": user.id,
            "user_name": user.name,
            "user_email": user.email,
            "wallet_balance": user.wallet,
            "qr_code": f"/static/qr_codes/{user.id}.png",
            "travel_history": travel_history
        }), 201
    except Exception as e:
        return jsonify({"error": f"An error occurred: {str(e)}"}), 500
 
# Route for Sign-In (User Login)
@app.route('/sign-in', methods=['POST'])
def sign_in_user():
    try:
        data = request.get_json()
        email = data.get('email')
 
        # Fetch user by email
        user = User.query.filter_by(email=email).first()
 
        if not user:
            return jsonify({"error": "User not found"}), 404
 
        travel_history = [{"start_lat": r.start_lat, "start_lng": r.start_lng, "end_lat": r.end_lat, "end_lng": r.end_lng, "distance": r.distance} for r in user.travel_records]
        return jsonify({
            "user_id": user.id,
            "user_name": user.name,
            "user_email": user.email,
            "wallet_balance": user.wallet,
            "qr_code": f"/static/qr_codes/{user.id}.png",
            "travel_history": travel_history
        }), 200
    except Exception as e:
        return jsonify({"error": f"An error occurred: {str(e)}"}), 500
 
# Route for Dashboard (User-specific)
@app.route('/dashboard/<int:user_id>', methods=['GET'])
def get_dashboard(user_id):
    try:
        user = User.query.get(user_id)
        if not user:
            return jsonify({"error": "User not found"}), 404
 
        travel_history = [{"start_lat": r.start_lat, "start_lng": r.start_lng, "end_lat": r.end_lat, "end_lng": r.end_lng, "distance": r.distance} for r in user.travel_records]
        return jsonify({
            "user_id": user.id,
            "user_name": user.name,
            "user_email": user.email,
            "wallet_balance": user.wallet,
            "qr_code": f"/static/qr_codes/{user.id}.png",
            "travel_history": travel_history
        }), 200
    except Exception as e:
        return jsonify({"error": f"An error occurred: {str(e)}"}), 500
 
# Run the app
if __name__ == "__main__":
    app.run(debug=True)
 
def build_preflight_response():
    response = make_response()
    response.headers.add("Access-Control-Allow-Origin", "*")
    response.headers.add('Access-Control-Allow-Headers', "*")
    response.headers.add('Access-Control-Allow-Methods', "*")
    return response
def build_actual_response(response):
    response.headers.add("Access-Control-Allow-Origin", "*")
    return response