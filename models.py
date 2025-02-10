from flask import Flask, render_template, jsonify, request, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
 
# Initialize the Flask application
app = Flask(__name__)
app.secret_key = 'your_secret_key'  # For session management
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
 
# Define the User model with the wallet column
class User(db.Model):
    __tablename__ = 'user'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    wallet = db.Column(db.Integer, default=0)  # Default wallet value is 0
 
    # Relationship to TravelRecord model
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
 
# Define the TravelRecord model
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
 
# Define the BusPass model with validity_days column
class BusPass(db.Model):
    __tablename__ = 'bus_pass'
    id = db.Column(db.Integer, primary_key=True)
    start_destination = db.Column(db.String(100), nullable=False)
    end_destination = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Float, nullable=False)
    validity_days = db.Column(db.Integer, nullable=False, default=30)  # Validity of 30 days
 
    def __repr__(self):
        return f"<BusPass {self.start_destination} to {self.end_destination}, Price: {self.price}, Validity: {self.validity_days} days>"
 
# Define the association table between User and BusPass (Many-to-Many)
class UserBusPass(db.Model):
    __tablename__ = 'user_bus_pass'
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), primary_key=True)
    bus_pass_id = db.Column(db.Integer, db.ForeignKey('bus_pass.id'), primary_key=True)
    purchase_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
 
    user = db.relationship('User', backref='user_bus_passes')
    bus_pass = db.relationship('BusPass', backref='user_bus_passes')
 
    def __repr__(self):
        return f"<UserBusPass User: {self.user_id}, BusPass: {self.bus_pass_id}>"
 
# Route for the dashboard
@app.route('/dashboard')
def dashboard():
    """Display the user dashboard with wallet balance and travel history."""
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
    """Handle user login."""
    if request.method == 'POST':
        email = request.form['email']
        user = User.query.filter_by(email=email).first()
        if user:
            session['user_id'] = user.id  # Store user_id in session
            return redirect(url_for('dashboard'))
        else:
            return "Invalid email", 400
    return render_template('login.html')
 
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
 
# Route for adding a travel record
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
 
# Route for logging out
@app.route('/logout')
def logout():
    """Handle user logout."""
    session.pop('user_id', None)  # Remove user_id from session
    return redirect(url_for('login'))
 
# Main entry point for the app
if __name__ == '__main__':
    with app.app_context():  # Add this context manager
        db.create_all()  # Create tables if not already created
    app.run(debug=True)
 

