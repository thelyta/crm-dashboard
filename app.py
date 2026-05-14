from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import os
import csv
import io
import json

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')

# Database configuration - automatically uses PostgreSQL on Render, SQLite locally
DATABASE_URL = os.environ.get('DATABASE_URL')
if DATABASE_URL and DATABASE_URL.startswith('postgres'):
    # Fix for Render's PostgreSQL URL (postgres:// vs postgresql://)
    if DATABASE_URL.startswith('postgres://'):
        DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)
    app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
else:
    # Local development - use SQLite
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///crm.db'

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# ============ MODELS ============
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), default='user')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Prospect(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100))
    phone = db.Column(db.String(20))
    company = db.Column(db.String(100))
    status = db.Column(db.String(50), default='New')
    pipeline = db.Column(db.String(50), default='LinkedIn Outreach')
    next_followup = db.Column(db.DateTime)
    notes = db.Column(db.Text)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Activity(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    prospect_id = db.Column(db.Integer, db.ForeignKey('prospect.id'))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    action = db.Column(db.String(200))
    details = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# ============ HELPER FUNCTIONS ============
def init_db():
    """Create tables and default admin user"""
    db.create_all()
    # Check if admin exists
    if not User.query.filter_by(username='admin').first():
        admin = User(username='admin', role='admin')
        admin.set_password('admin123')
        db.session.add(admin)
        db.session.commit()
        print("Default admin user created: admin / admin123")

# ============ ROUTES ============
@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    prospects = Prospect.query.all()
    
    # Calculate follow-up statuses
    for p in prospects:
        if p.next_followup:
            days_until = (p.next_followup - datetime.utcnow()).days
            if days_until < 0:
                p.followup_status = 'overdue'
            elif days_until <= 2:
                p.followup_status = 'due-soon'
            else:
                p.followup_status = 'on-track'
        else:
            p.followup_status = 'none'
    
    return render_template('index.html', user=user, prospects=prospects)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            session['user_id'] = user.id
            session['username'] = user.username
            session['role'] = user.role
            return redirect(url_for('index'))
        return render_template('login.html', error='Invalid credentials')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/api/prospects', methods=['GET', 'POST'])
def api_prospects():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    if request.method == 'GET':
        prospects = Prospect.query.all()
        return jsonify([{
            'id': p.id,
            'name': p.name,
            'email': p.email,
            'phone': p.phone,
            'company': p.company,
            'status': p.status,
            'pipeline': p.pipeline,
            'next_followup': p.next_followup.isoformat() if p.next_followup else None,
            'notes': p.notes
        } for p in prospects])
    
    if request.method == 'POST':
        data = request.json
        prospect = Prospect(
            name=data['name'],
            email=data.get('email'),
            phone=data.get('phone'),
            company=data.get('company'),
            status=data.get('status', 'New'),
            pipeline=data.get('pipeline', 'LinkedIn Outreach'),
            notes=data.get('notes'),
            created_by=session['user_id']
        )
        if data.get('next_followup'):
            prospect.next_followup = datetime.fromisoformat(data['next_followup'])
        db.session.add(prospect)
        db.session.commit()
        return jsonify({'id': prospect.id}), 201

@app.route('/api/prospects/<int:prospect_id>', methods=['PUT', 'DELETE'])
def api_prospect_detail(prospect_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    prospect = Prospect.query.get_or_404(prospect_id)
    
    if request.method == 'PUT':
        data = request.json
        prospect.name = data.get('name', prospect.name)
        prospect.email = data.get('email', prospect.email)
        prospect.phone = data.get('phone', prospect.phone)
        prospect.company = data.get('company', prospect.company)
        prospect.status = data.get('status', prospect.status)
        prospect.pipeline = data.get('pipeline', prospect.pipeline)
        prospect.notes = data.get('notes', prospect.notes)
        if data.get('next_followup'):
            prospect.next_followup = datetime.fromisoformat(data['next_followup'])
        db.session.commit()
        return jsonify({'success': True})
    
    if request.method == 'DELETE':
        db.session.delete(prospect)
        db.session.commit()
        return jsonify({'success': True})

@app.route('/api/import-csv', methods=['POST'])
def import_csv():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    if not file.filename.endswith('.csv'):
        return jsonify({'error': 'File must be CSV'}), 400
    
    stream = io.StringIO(file.stream.read().decode("UTF8"), newline=None)
    csv_input = csv.reader(stream)
    headers = next(csv_input)
    
    imported = 0
    for row in csv_input:
        try:
            prospect = Prospect(
                name=row[0],
                email=row[1] if len(row) > 1 else None,
                phone=row[2] if len(row) > 2 else None,
                company=row[3] if len(row) > 3 else None,
                created_by=session['user_id']
            )
            db.session.add(prospect)
            imported += 1
        except:
            pass
    
    db.session.commit()
    return jsonify({'imported': imported})

@app.route('/api/activities', methods=['GET'])
def get_activities():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    activities = Activity.query.order_by(Activity.created_at.desc()).limit(50).all()
    return jsonify([{
        'id': a.id,
        'action': a.action,
        'details': a.details,
        'created_at': a.created_at.isoformat()
    } for a in activities])

@app.route('/api/users', methods=['GET', 'POST'])
def manage_users():
    if 'user_id' not in session or session.get('role') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 401
    
    if request.method == 'GET':
        users = User.query.all()
        return jsonify([{
            'id': u.id,
            'username': u.username,
            'role': u.role,
            'created_at': u.created_at.isoformat()
        } for u in users])
    
    if request.method == 'POST':
        data = request.json
        if User.query.filter_by(username=data['username']).first():
            return jsonify({'error': 'Username exists'}), 400
        user = User(username=data['username'], role=data.get('role', 'user'))
        user.set_password(data['password'])
        db.session.add(user)
        db.session.commit()
        return jsonify({'id': user.id}), 201

# ============ INITIALIZATION ============
with app.app_context():
    init_db()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))
