from flask import Flask, request, jsonify, render_template, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
import qrcode
import os
from datetime import datetime

# Initialize Flask application
app = Flask(__name__)
app.secret_key = 'your_secret_key'  # For session management

# Enable CORS for the app
CORS(app, resources={r"/*": {"origins": "http://127.0.0.1:5500"}})

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
    bus_passes = db.relationship('BusPass', secondary='user_bus_pass', backref='users')
    
    def __repr__(self):
        return f'<User {self.name}, {self.email}, Wallet: {self.wallet}>'
    
    def purchase_bus_pass(self, bus_pass_id):
        """Purchase a bus pass and deduct from the wallet."""
        bus_pass = BusPass.query.get(bus_pass_id)
        if bus_pass:
            if self.wallet >= bus_pass.price:
                self.wallet -= bus_pass.price  # Deduct wallet balance
                db.session.commit()
                return True
            else:
                return False  # Not enough balance
        return False  # Invalid bus pass
    
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
    
    def add_travel(self, start_lat, start_lng, end_lat, end_lng, distance):
        """Add travel record and deduct from wallet."""
        self.start_lat = start_lat
        self.start_lng = start_lng
        self.end_lat = end_lat
        self.end_lng = end_lng
        self.distance = distance
        db.session.add(self)
        
        # Deduct wallet for travel distance, assuming a fixed rate per km
        rate_per_km = 10  # example rate
        cost = distance * rate_per_km
        user = User.query.get(self.user_id)
        if user.wallet >= cost:
            user.wallet -= cost
            db.session.commit()
            return True
        else:
            db.session.rollback()  # Rollback the record if insufficient funds
            return False

# Define BusPass model
class BusPass(db.Model):
    __tablename__ = 'bus_pass'
    id = db.Column(db.Integer, primary_key=True)
    start_destination = db.Column(db.String(100), nullable=False)
    end_destination = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Float, nullable=False)
    validity_days = db.Column(db.Integer, nullable=False, default=30)  # Validity of 30 days
    
    def __repr__(self):
        return f'<BusPass {self.start_destination} to {self.end_destination}, Price: {self.price}>'

# Define the association table between User and BusPass (Many-to-Many)
class UserBusPass(db.Model):
    __tablename__ = 'user_bus_pass'
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), primary_key=True)
    bus_pass_id = db.Column(db.Integer, db.ForeignKey('bus_pass.id'), primary_key=True)
    purchase_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    
    user = db.relationship('User', backref='user_bus_passes')
    bus_pass = db.relationship('BusPass', backref='user_bus_passes')

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

        return jsonify({
            "message": "User registered successfully!",
            "user_id": user.id,
            "qr_code": f"/static/qr_codes/{user.id}.png",
            "wallet_balance": user.wallet
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

        return jsonify({
            "user_id": user.id,
            "user_name": user.name,
            "user_email": user.email,
            "wallet_balance": user.wallet,
            "qr_code": f"/static/qr_codes/{user.id}.png",
        }), 200
    except Exception as e:
        return jsonify({"error": f"An error occurred: {str(e)}"}), 500

# Route for purchasing bus pass
@app.route('/purchase_bus_pass', methods=['POST'])
def purchase_bus_pass():
    data = request.get_json()
    user_id = data.get('user_id')
    bus_pass_id = data.get('bus_pass_id')
    
    user = User.query.get(user_id)
    if user:
        success = user.purchase_bus_pass(bus_pass_id)
        if success:
            return jsonify({'message': 'Bus pass purchased successfully'}), 200
        else:
            return jsonify({'message': 'Insufficient funds or invalid bus pass'}), 400
    return jsonify({'message': 'User not found'}), 404

# Route to add a travel record
@app.route('/add_travel', methods=['POST'])
def add_travel():
    data = request.get_json()
    user_id = data.get('user_id')
    start_lat = data.get('start_lat')
    start_lng = data.get('start_lng')
    end_lat = data.get('end_lat')
    end_lng = data.get('end_lng')
    distance = data.get('distance')

    travel_record = TravelRecord(user_id=user_id)
    success = travel_record.add_travel(start_lat, start_lng, end_lat, end_lng, distance)
    if success:
        return jsonify({'message': 'Travel record added successfully'}), 200
    else:
        return jsonify({'message': 'Insufficient funds for travel'}), 400

# Route for the dashboard
@app.route('/dashboard')
def dashboard():
    user_id = session.get('user_id')  # Get user_id from session
    if not user_id:
        return redirect(url_for('login'))  # Redirect to login if not logged in
    
    user = User.query.get(user_id)
    if user:
        travel_records = TravelRecord.query.filter_by(user_id=user.id).all()  # Get travel records for user
        return render_template('dashboard.html', user=user, travel_records=travel_records)
    return redirect(url_for('login'))

# Route for user login
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        user = User.query.filter_by(email=email).first()
        if user:
            session['user_id'] = user.id  # Store user_id in session
            return redirect(url_for('dashboard'))
        else:
            return "Invalid email", 400
    return render_template('login.html')

# Function to initialize the database
def initialize_database():
    with app.app_context():
        db.create_all()
        print("Database initialized successfully!")

# Run the app
if __name__ == '__main__':
    initialize_database()
    app.run(debug=True)
