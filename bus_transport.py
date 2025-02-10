from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
import qrcode
import os
 
# Initialize Flask application
app = Flask(__name__)
 
# Enable CORS for the app
CORS(app, resources={r"/*": {"origins": "*"}})
 
# Configure SQLite database
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///bus_transport.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False  # Disable unnecessary warnings
 
# Initialize SQLAlchemy
db = SQLAlchemy(app)
 
# Define User model
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
 
# Define BusPass model
class BusPass(db.Model):
    __tablename__ = 'bus_pass'
    id = db.Column(db.Integer, primary_key=True)
    start_destination = db.Column(db.String(100), nullable=False)
    end_destination = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Float, nullable=False)
 
    def __repr__(self):
        return f'<BusPass {self.start_destination} to {self.end_destination}, Price: {self.price}>'
 
# Route for the home page
@app.route('/')
def home():
    return "Welcome to the Bus Transport System!"
 
# Route for user registration
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
 
        user = User(name=name, email=email)
        db.session.add(user)
        db.session.commit()
 
        # Generate QR code
        user_qr = qrcode.make(f"user_id:{user.id}")
        qr_folder = "static/qr_codes"
        os.makedirs(qr_folder, exist_ok=True)
        qr_file = os.path.join(qr_folder, f"{user.id}.png")
        user_qr.save(qr_file)
 
        return jsonify({
            "message": "User registered successfully!",
            "user_id": user.id,
            "qr_code": f"/static/qr_codes/{user.id}.png",
            "wallet_balance": user.wallet
        }), 201
 
    except Exception as e:
        return jsonify({"error": f"An error occurred: {str(e)}"}), 500
 
# Route to list all bus passes
@app.route('/bus-passes', methods=['GET'])
def list_bus_passes():
    try:
        bus_passes = BusPass.query.all()
        passes = [{
            "id": bp.id,
            "start_destination": bp.start_destination,
            "end_destination": bp.end_destination,
            "price": bp.price
        } for bp in bus_passes]
 
        return jsonify({"bus_passes": passes}), 200
 
    except Exception as e:
        return jsonify({"error": f"An error occurred: {str(e)}"}), 500
 
# Route to add a new bus pass
@app.route('/add-bus-pass', methods=['POST'])
def add_bus_pass():
    try:
        data = request.get_json()
        start_destination = data.get('start_destination')
        end_destination = data.get('end_destination')
        price = data.get('price')
 
        # Create a new bus pass
        new_pass = BusPass(
            start_destination=start_destination,
            end_destination=end_destination,
            price=price
        )
        db.session.add(new_pass)
        db.session.commit()
 
        return jsonify({"message": "Bus pass added successfully!"}), 201
 
    except Exception as e:
        return jsonify({"error": f"An error occurred: {str(e)}"}), 500
 
# Route for the user dashboard
@app.route('/dashboard/<int:user_id>', methods=['GET'])
def dashboard(user_id):
    try:
        user = User.query.get(user_id)
        if not user:
            return jsonify({"error": "User not found"}), 404
 
        travel_history = TravelRecord.query.filter_by(user_id=user.id).all()
        travel_history_list = [{
            "start_lat": record.start_lat,
            "start_lng": record.start_lng,
            "end_lat": record.end_lat,
            "end_lng": record.end_lng,
            "distance": record.distance
        } for record in travel_history]
 
        return jsonify({
            "user_name": user.name,
            "wallet_balance": user.wallet,
            "travel_history": travel_history_list
        }), 200
 
    except Exception as e:
        return jsonify({"error": f"An error occurred: {str(e)}"}), 500
 
# Function to initialize the database
def initialize_database():
    with app.app_context():
        db.create_all()
        print("Database initialized successfully!")
 
# Initialize the database and run the app
if __name__ == '__main__':
    initialize_database()
    app.run(debug=True)
 
