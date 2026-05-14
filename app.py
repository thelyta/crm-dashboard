from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import os
import csv
import io
import json
import re

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

class Pipeline(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Sequence(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    pipeline_id = db.Column(db.Integer, db.ForeignKey('pipeline.id'))
    is_default = db.Column(db.Boolean, default=False)
    steps = db.Column(db.Text, default='[]')  # JSON array of {days, status, label}
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Prospect(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    first_name = db.Column(db.String(50))
    last_name = db.Column(db.String(50))
    email = db.Column(db.String(100))
    phone = db.Column(db.String(20))
    linkedin_url = db.Column(db.String(200))
    company = db.Column(db.String(100))
    status = db.Column(db.String(50), default='New Lead')
    pipeline_id = db.Column(db.Integer, db.ForeignKey('pipeline.id'))
    pipeline = db.Column(db.String(50), default='LinkedIn Outreach')
    sequence_id = db.Column(db.Integer, db.ForeignKey('sequence.id'))
    sequence_step_index = db.Column(db.Integer, default=0)
    tags = db.Column(db.Text, default='[]')  # JSON array
    next_followup = db.Column(db.DateTime)
    last_contact_date = db.Column(db.DateTime)  # NEW: Editable last contact date
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
    """Create tables and default data"""
    db.create_all()

    # Create default admin user
    if not User.query.filter_by(username='admin').first():
        admin = User(username='admin', role='admin')
        admin.set_password('admin123')
        db.session.add(admin)
        db.session.commit()
        print("Default admin user created: admin / admin123")

    # Create default pipeline if none exists
    if not Pipeline.query.first():
        default_pipeline = Pipeline(name='LinkedIn Outreach', description='Default outreach pipeline')
        db.session.add(default_pipeline)
        db.session.commit()
        print("Default pipeline created")

        # Create default sequence
        default_sequence = Sequence(
            name='Standard Follow-Up',
            pipeline_id=default_pipeline.id,
            is_default=True,
            steps=json.dumps([
                {"days": 0, "status": "New Lead", "label": "Initial Contact"},
                {"days": 1, "status": "Sent", "label": "Day 1: First Message"},
                {"days": 3, "status": "Sent 1", "label": "Day 3: Follow Up 1"},
                {"days": 7, "status": "Sent 2", "label": "Day 7: Follow Up 2"},
                {"days": 14, "status": "Sent 3", "label": "Day 14: Follow Up 3"},
                {"days": 30, "status": "Sent 4+", "label": "Day 30: Final Follow Up"},
                {"days": 45, "status": "Nurture", "label": "Day 45: Nurture/Re-engage"}
            ])
        )
        db.session.add(default_sequence)
        db.session.commit()
        print("Default sequence created")

def calculate_next_followup(prospect):
    """Calculate next follow-up date based on sequence and last contact"""
    if not prospect.sequence_id or not prospect.last_contact_date:
        return None

    sequence = Sequence.query.get(prospect.sequence_id)
    if not sequence:
        return None

    try:
        steps = json.loads(sequence.steps)
        current_step = prospect.sequence_step_index or 0

        if current_step < len(steps):
            days_to_wait = steps[current_step].get('days', 0)
            return prospect.last_contact_date + timedelta(days=days_to_wait)
    except:
        pass

    return None

def get_followup_status(prospect):
    """Determine follow-up urgency status"""
    if not prospect.next_followup:
        return 'none'

    days_until = (prospect.next_followup - datetime.utcnow()).days
    if days_until < 0:
        return 'overdue'
    elif days_until <= 2:
        return 'due-soon'
    else:
        return 'on-track'

def prospect_to_dict(p):
    """Convert prospect to dictionary with computed fields"""
    followup_status = get_followup_status(p)

    return {
        'id': p.id,
        'name': p.name,
        'first_name': p.first_name,
        'last_name': p.last_name,
        'email': p.email,
        'phone': p.phone,
        'linkedin_url': p.linkedin_url,
        'company': p.company,
        'status': p.status,
        'pipeline_id': p.pipeline_id,
        'pipeline': p.pipeline,
        'sequence_id': p.sequence_id,
        'sequence_step_index': p.sequence_step_index,
        'tags': json.loads(p.tags) if p.tags else [],
        'next_followup': p.next_followup.isoformat() if p.next_followup else None,
        'last_contact_date': p.last_contact_date.isoformat() if p.last_contact_date else None,
        'notes': p.notes,
        'followup_status': followup_status,
        'created_at': p.created_at.isoformat() if p.created_at else None,
        'updated_at': p.updated_at.isoformat() if p.updated_at else None
    }

def log_activity(prospect_id, action, details=None):
    """Log an activity"""
    user_id = session.get('user_id')
    activity = Activity(
        prospect_id=prospect_id,
        user_id=user_id,
        action=action,
        details=details
    )
    db.session.add(activity)
    db.session.commit()

# ============ AUTH MIDDLEWARE ============
def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'Unauthorized'}), 401
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session or session.get('role') != 'admin':
            return jsonify({'error': 'Admin access required'}), 403
        return f(*args, **kwargs)
    return decorated

# ============ ROUTES ============
@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    return render_template('index.html', user=user)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # Support both form data and JSON
        if request.is_json:
            data = request.get_json()
            username = data.get('username')
            password = data.get('password')
        else:
            username = request.form.get('username')
            password = request.form.get('password')

        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            session['user_id'] = user.id
            session['username'] = user.username
            session['role'] = user.role
            if request.is_json:
                return jsonify({'success': True, 'username': user.username, 'role': user.role})
            return redirect(url_for('index'))

        if request.is_json:
            return jsonify({'success': False, 'error': 'Invalid credentials'}), 401
        return render_template('login.html', error='Invalid credentials')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# ============ PIPELINE API ============
@app.route('/api/pipelines', methods=['GET', 'POST'])
@login_required
def api_pipelines():
    if request.method == 'GET':
        pipelines = Pipeline.query.all()
        result = []
        for p in pipelines:
            count = Prospect.query.filter_by(pipeline_id=p.id).count()
            result.append({
                'id': p.id,
                'name': p.name,
                'description': p.description,
                'prospect_count': count,
                'created_at': p.created_at.isoformat() if p.created_at else None
            })
        return jsonify(result)

    if request.method == 'POST':
        data = request.get_json()
        pipeline = Pipeline(name=data['name'], description=data.get('description'))
        db.session.add(pipeline)
        db.session.commit()
        log_activity(None, 'pipeline_created', f"Created pipeline: {data['name']}")
        return jsonify({'id': pipeline.id, 'name': pipeline.name}), 201

# ============ SEQUENCE API ============
@app.route('/api/sequences', methods=['GET', 'POST'])
@login_required
def api_sequences():
    if request.method == 'GET':
        pipeline_id = request.args.get('pipeline_id')
        query = Sequence.query
        if pipeline_id:
            query = query.filter_by(pipeline_id=pipeline_id)
        sequences = query.all()
        return jsonify([{
            'id': s.id,
            'name': s.name,
            'pipeline_id': s.pipeline_id,
            'is_default': s.is_default,
            'steps': json.loads(s.steps) if s.steps else [],
            'created_at': s.created_at.isoformat() if s.created_at else None
        } for s in sequences])

    if request.method == 'POST':
        data = request.get_json()
        sequence = Sequence(
            name=data['name'],
            pipeline_id=data.get('pipeline_id'),
            steps=json.dumps(data.get('steps', []))
        )
        db.session.add(sequence)
        db.session.commit()
        return jsonify({'id': sequence.id}), 201

# ============ PROSPECT API ============
@app.route('/api/prospects', methods=['GET', 'POST'])
@login_required
def api_prospects():
    if request.method == 'GET':
        query = Prospect.query

        # Apply filters
        pipeline_id = request.args.get('pipeline_id')
        if pipeline_id:
            query = query.filter_by(pipeline_id=pipeline_id)

        search = request.args.get('search')
        if search:
            search_filter = f'%{search}%'
            query = query.filter(
                db.or_(
                    Prospect.name.ilike(search_filter),
                    Prospect.first_name.ilike(search_filter),
                    Prospect.last_name.ilike(search_filter),
                    Prospect.email.ilike(search_filter),
                    Prospect.company.ilike(search_filter)
                )
            )

        status = request.args.get('status')
        if status:
            query = query.filter_by(status=status)

        tag = request.args.get('tag')
        if tag:
            query = query.filter(Prospect.tags.ilike(f'%"{tag}"%'))

        month = request.args.get('month')
        year = request.args.get('year')
        if month or year:
            if month:
                query = query.filter(db.extract('month', Prospect.created_at) == int(month))
            if year:
                query = query.filter(db.extract('year', Prospect.created_at) == int(year))

        prospects = query.order_by(Prospect.created_at.desc()).all()

        # Recalculate next_followup for all prospects
        for p in prospects:
            if p.sequence_id and p.last_contact_date:
                p.next_followup = calculate_next_followup(p)

        return jsonify([prospect_to_dict(p) for p in prospects])

    if request.method == 'POST':
        data = request.get_json()

        # Build name from first/last
        first_name = data.get('first_name', '').strip()
        last_name = data.get('last_name', '').strip()
        name = f"{first_name} {last_name}".strip() or first_name or 'Unknown'

        prospect = Prospect(
            name=name,
            first_name=first_name,
            last_name=last_name,
            email=data.get('email'),
            phone=data.get('phone'),
            linkedin_url=data.get('linkedin_url'),
            company=data.get('company'),
            status=data.get('status', 'New Lead'),
            pipeline_id=data.get('pipeline_id'),
            pipeline=data.get('pipeline', 'LinkedIn Outreach'),
            sequence_id=data.get('sequence_id'),
            sequence_step_index=data.get('sequence_step_index', 0),
            tags=json.dumps(data.get('tags', [])),
            notes=data.get('notes'),
            created_by=session['user_id']
        )

        # Handle last_contact_date
        if data.get('last_contact_date'):
            try:
                prospect.last_contact_date = datetime.fromisoformat(data['last_contact_date'].replace('Z', '+00:00').replace('+00:00', ''))
            except:
                pass

        # Calculate next follow-up if sequence assigned
        if prospect.sequence_id and prospect.last_contact_date:
            prospect.next_followup = calculate_next_followup(prospect)
        elif data.get('next_followup'):
            try:
                prospect.next_followup = datetime.fromisoformat(data['next_followup'].replace('Z', '+00:00').replace('+00:00', ''))
            except:
                pass

        db.session.add(prospect)
        db.session.commit()

        log_activity(prospect.id, 'created', f"Added prospect: {name}")

        return jsonify({'id': prospect.id}), 201

@app.route('/api/prospects/<int:prospect_id>', methods=['GET', 'PUT', 'DELETE'])
@login_required
def api_prospect_detail(prospect_id):
    prospect = Prospect.query.get_or_404(prospect_id)

    if request.method == 'GET':
        return jsonify(prospect_to_dict(prospect))

    if request.method == 'PUT':
        data = request.get_json()

        # Track what changed for activity log
        changes = []

        if 'first_name' in data:
            prospect.first_name = data['first_name']
            changes.append('first_name')
        if 'last_name' in data:
            prospect.last_name = data['last_name']
            changes.append('last_name')
        if 'first_name' in data or 'last_name' in data:
            prospect.name = f"{prospect.first_name or ''} {prospect.last_name or ''}".strip() or 'Unknown'

        if 'email' in data:
            prospect.email = data['email']
            changes.append('email')
        if 'phone' in data:
            prospect.phone = data['phone']
            changes.append('phone')
        if 'linkedin_url' in data:
            prospect.linkedin_url = data['linkedin_url']
            changes.append('linkedin_url')
        if 'company' in data:
            prospect.company = data['company']
            changes.append('company')
        if 'status' in data:
            old_status = prospect.status
            prospect.status = data['status']
            if old_status != data['status']:
                changes.append(f'status: {old_status} → {data["status"]}')
        if 'pipeline_id' in data:
            prospect.pipeline_id = data['pipeline_id']
            changes.append('pipeline')
        if 'sequence_id' in data:
            prospect.sequence_id = data['sequence_id']
            changes.append('sequence')
        if 'sequence_step_index' in data:
            prospect.sequence_step_index = data['sequence_step_index']
            changes.append('sequence_step')
        if 'tags' in data:
            prospect.tags = json.dumps(data['tags'])
            changes.append('tags')
        if 'notes' in data:
            prospect.notes = data['notes']
            changes.append('notes')

        # NEW: Handle last_contact_date update
        if 'last_contact_date' in data:
            if data['last_contact_date']:
                try:
                    prospect.last_contact_date = datetime.fromisoformat(data['last_contact_date'].replace('Z', '+00:00').replace('+00:00', ''))
                    changes.append('last_contact_date')
                except Exception as e:
                    print(f"Error parsing last_contact_date: {e}")
            else:
                prospect.last_contact_date = None
                changes.append('last_contact_date cleared')

        # Recalculate next follow-up if sequence and last contact exist
        if prospect.sequence_id and prospect.last_contact_date:
            prospect.next_followup = calculate_next_followup(prospect)
        elif 'next_followup' in data:
            if data['next_followup']:
                try:
                    prospect.next_followup = datetime.fromisoformat(data['next_followup'].replace('Z', '+00:00').replace('+00:00', ''))
                except:
                    pass
            else:
                prospect.next_followup = None

        prospect.updated_at = datetime.utcnow()
        db.session.commit()

        if changes:
            log_activity(prospect.id, 'updated', ', '.join(changes))

        return jsonify({'success': True, 'prospect': prospect_to_dict(prospect)})

    if request.method == 'DELETE':
        log_activity(prospect.id, 'deleted', f"Deleted prospect: {prospect.name}")
        db.session.delete(prospect)
        db.session.commit()
        return jsonify({'success': True})

# ============ ADVANCE SEQUENCE ============
@app.route('/api/prospects/<int:prospect_id>/advance-sequence', methods=['POST'])
@login_required
def advance_sequence(prospect_id):
    """Advance prospect to next step in sequence"""
    prospect = Prospect.query.get_or_404(prospect_id)

    if not prospect.sequence_id:
        return jsonify({'error': 'No sequence assigned'}), 400

    sequence = Sequence.query.get(prospect.sequence_id)
    if not sequence:
        return jsonify({'error': 'Sequence not found'}), 404

    try:
        steps = json.loads(sequence.steps)
    except:
        return jsonify({'error': 'Invalid sequence data'}), 500

    current_step = prospect.sequence_step_index or 0

    if current_step >= len(steps) - 1:
        return jsonify({'error': 'Already at final step'}), 400

    # Advance to next step
    prospect.sequence_step_index = current_step + 1
    new_step = steps[prospect.sequence_step_index]

    # Update status based on sequence step
    if 'status' in new_step:
        prospect.status = new_step['status']

    # Update last contact date to now
    prospect.last_contact_date = datetime.utcnow()

    # Recalculate next follow-up
    prospect.next_followup = calculate_next_followup(prospect)

    db.session.commit()

    log_activity(
        prospect.id, 
        'status_change', 
        f"Advanced to step {prospect.sequence_step_index + 1}: {new_step.get('label', 'Unknown')}"
    )

    return jsonify({
        'success': True,
        'prospect': prospect_to_dict(prospect),
        'step_index': prospect.sequence_step_index,
        'step_label': new_step.get('label'),
        'next_followup': prospect.next_followup.isoformat() if prospect.next_followup else None
    })

# ============ LOG CONTACT ============
@app.route('/api/prospects/<int:prospect_id>/log-contact', methods=['POST'])
@login_required
def log_contact(prospect_id):
    data = request.get_json()
    notes = data.get('notes', '')

    prospect = Prospect.query.get_or_404(prospect_id)

    # Update last contact date to now
    prospect.last_contact_date = datetime.utcnow()

    # If sequence exists, recalculate next follow-up
    if prospect.sequence_id:
        prospect.next_followup = calculate_next_followup(prospect)

    db.session.commit()

    log_activity(prospect.id, 'contact_logged', notes)

    return jsonify({
        'success': True,
        'last_contact_date': prospect.last_contact_date.isoformat(),
        'next_followup': prospect.next_followup.isoformat() if prospect.next_followup else None
    })

# ============ CSV IMPORT ============
@app.route('/api/import-csv', methods=['POST'])
@login_required
def import_csv():
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    file = request.files['file']
    if not file.filename.endswith('.csv'):
        return jsonify({'error': 'File must be CSV'}), 400

    pipeline_id = request.form.get('pipeline_id')
    sequence_id = request.form.get('sequence_id')

    stream = io.StringIO(file.stream.read().decode("UTF8"), newline=None)
    csv_input = csv.reader(stream)

    try:
        headers = [h.strip().lower() for h in next(csv_input)]
    except StopIteration:
        return jsonify({'error': 'Empty CSV file'}), 400

    # Map common column names
    def find_column(possible_names):
        for name in possible_names:
            for i, header in enumerate(headers):
                if name.lower() in header or header in name.lower():
                    return i
        return None

    first_name_idx = find_column(['first name', 'first_name', 'firstname', 'first'])
    last_name_idx = find_column(['last name', 'last_name', 'lastname', 'last'])
    name_idx = find_column(['name', 'full name', 'full_name'])
    email_idx = find_column(['email', 'e-mail', 'mail'])
    phone_idx = find_column(['phone', 'telephone', 'mobile', 'cell'])
    company_idx = find_column(['company', 'organization', 'firm', 'brokerage'])
    linkedin_idx = find_column(['linkedin', 'linkedin url', 'linkedin_url', 'linked'])
    status_idx = find_column(['status', 'stage', 'pipeline stage'])
    date_sent_idx = find_column(['date sent', 'date_sent', 'sent date', 'sent_date', 'last contact', 'last_contact', 'contact date', 'date'])
    tags_idx = find_column(['tags', 'tag', 'label', 'labels'])

    imported = 0
    errors = []

    for row_num, row in enumerate(csv_input, start=2):
        if not row or not any(cell.strip() for cell in row):
            continue

        try:
            # Extract name
            first_name = ''
            last_name = ''

            if first_name_idx is not None and len(row) > first_name_idx:
                first_name = row[first_name_idx].strip()
            if last_name_idx is not None and len(row) > last_name_idx:
                last_name = row[last_name_idx].strip()

            if not first_name and name_idx is not None and len(row) > name_idx:
                full_name = row[name_idx].strip()
                parts = full_name.split(None, 1)
                first_name = parts[0] if parts else full_name
                last_name = parts[1] if len(parts) > 1 else ''

            name = f"{first_name} {last_name}".strip() or 'Unknown'

            # Extract other fields
            email = row[email_idx].strip() if email_idx is not None and len(row) > email_idx else None
            phone = row[phone_idx].strip() if phone_idx is not None and len(row) > phone_idx else None
            company = row[company_idx].strip() if company_idx is not None and len(row) > company_idx else None
            linkedin_url = row[linkedin_idx].strip() if linkedin_idx is not None and len(row) > linkedin_idx else None

            # NEW: Extract status from CSV
            status = 'New Lead'
            if status_idx is not None and len(row) > status_idx:
                csv_status = row[status_idx].strip()
                if csv_status:
                    status = csv_status

            # NEW: Extract date sent / last contact date from CSV
            last_contact_date = None
            if date_sent_idx is not None and len(row) > date_sent_idx:
                date_str = row[date_sent_idx].strip()
                if date_str:
                    # Try multiple date formats
                    date_formats = [
                        '%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y', '%m-%d-%Y',
                        '%Y/%m/%d', '%d-%m-%Y', '%m/%d/%y', '%d/%m/%y',
                        '%B %d, %Y', '%b %d, %Y', '%d %B %Y', '%d %b %Y'
                    ]
                    for fmt in date_formats:
                        try:
                            last_contact_date = datetime.strptime(date_str, fmt)
                            break
                        except ValueError:
                            continue

            # Extract tags
            tags = []
            if tags_idx is not None and len(row) > tags_idx:
                tags_str = row[tags_idx].strip()
                if tags_str:
                    tags = [t.strip().lower() for t in tags_str.split(',') if t.strip()]

            prospect = Prospect(
                name=name,
                first_name=first_name,
                last_name=last_name,
                email=email,
                phone=phone,
                linkedin_url=linkedin_url,
                company=company,
                status=status,
                pipeline_id=pipeline_id,
                sequence_id=sequence_id,
                sequence_step_index=0,
                tags=json.dumps(tags),
                last_contact_date=last_contact_date,
                created_by=session['user_id']
            )

            # Calculate next follow-up if sequence and date exist
            if sequence_id and last_contact_date:
                prospect.next_followup = calculate_next_followup(prospect)

            db.session.add(prospect)
            imported += 1

        except Exception as e:
            errors.append(f"Row {row_num}: {str(e)}")

    db.session.commit()

    # Log bulk import
    if imported > 0:
        log_activity(None, 'imported', f"Imported {imported} prospects from CSV")

    return jsonify({
        'success': True,
        'imported': imported,
        'errors': errors,
        'headers': headers
    })

# ============ STATS API ============
@app.route('/api/stats')
@login_required
def get_stats():
    pipeline_id = request.args.get('pipeline_id')
    query = Prospect.query
    if pipeline_id:
        query = query.filter_by(pipeline_id=pipeline_id)

    total = query.count()

    # Get all prospects to calculate follow-up statuses
    prospects = query.all()
    overdue = 0
    due_soon = 0
    on_track = 0

    for p in prospects:
        status = get_followup_status(p)
        if status == 'overdue':
            overdue += 1
        elif status == 'due-soon':
            due_soon += 1
        elif status == 'on-track':
            on_track += 1

    # Get pipeline breakdown
    pipeline_stats = []
    pipelines = Pipeline.query.all()
    for pl in pipelines:
        count = Prospect.query.filter_by(pipeline_id=pl.id).count()
        pipeline_stats.append({'name': pl.name, 'count': count})

    return jsonify({
        'total': total,
        'overdue': overdue,
        'due_soon': due_soon,
        'on_track': on_track,
        'pipelines': pipeline_stats
    })

# ============ ACTIVITY LOG API ============
@app.route('/api/activity-log')
@login_required
def get_activity_log():
    prospect_id = request.args.get('prospect_id')
    query = Activity.query.order_by(Activity.created_at.desc())

    if prospect_id:
        query = query.filter_by(prospect_id=prospect_id)

    logs = query.limit(100).all()

    result = []
    for log in logs:
        username = None
        if log.user_id:
            user = User.query.get(log.user_id)
            if user:
                username = user.username

        result.append({
            'id': log.id,
            'prospect_id': log.prospect_id,
            'action': log.action,
            'details': log.details,
            'username': username,
            'created_at': log.created_at.isoformat() if log.created_at else None
        })

    return jsonify(result)

# ============ USER MANAGEMENT API ============
@app.route('/api/users', methods=['GET', 'POST'])
@admin_required
def manage_users():
    if request.method == 'GET':
        users = User.query.all()
        return jsonify([{
            'id': u.id,
            'username': u.username,
            'role': u.role,
            'created_at': u.created_at.isoformat() if u.created_at else None
        } for u in users])

    if request.method == 'POST':
        data = request.get_json()
        if User.query.filter_by(username=data['username']).first():
            return jsonify({'error': 'Username exists'}), 400
        user = User(username=data['username'], role=data.get('role', 'user'))
        user.set_password(data['password'])
        db.session.add(user)
        db.session.commit()
        return jsonify({'id': user.id}), 201

# ============ BULK ACTIONS ============
@app.route('/api/bulk/advance-sequence', methods=['POST'])
@login_required
def bulk_advance_sequence():
    """Bulk advance multiple prospects to next sequence step"""
    data = request.get_json()
    prospect_ids = data.get('prospect_ids', [])

    if not prospect_ids:
        return jsonify({'error': 'No prospects selected'}), 400

    advanced = 0
    errors = []

    for pid in prospect_ids:
        prospect = Prospect.query.get(pid)
        if not prospect:
            errors.append(f"Prospect {pid} not found")
            continue

        if not prospect.sequence_id:
            errors.append(f"Prospect {pid} has no sequence")
            continue

        sequence = Sequence.query.get(prospect.sequence_id)
        if not sequence:
            errors.append(f"Sequence not found for prospect {pid}")
            continue

        try:
            steps = json.loads(sequence.steps)
        except:
            errors.append(f"Invalid sequence data for prospect {pid}")
            continue

        current_step = prospect.sequence_step_index or 0

        if current_step >= len(steps) - 1:
            errors.append(f"Prospect {prospect.name} already at final step")
            continue

        prospect.sequence_step_index = current_step + 1
        new_step = steps[prospect.sequence_step_index]

        if 'status' in new_step:
            prospect.status = new_step['status']

        prospect.last_contact_date = datetime.utcnow()
        prospect.next_followup = calculate_next_followup(prospect)

        advanced += 1
        log_activity(
            prospect.id,
            'status_change',
            f"Bulk advance to step {prospect.sequence_step_index + 1}: {new_step.get('label', 'Unknown')}"
        )

    db.session.commit()

    return jsonify({
        'success': True,
        'advanced': advanced,
        'errors': errors
    })

@app.route('/api/bulk/update-status', methods=['POST'])
@login_required
def bulk_update_status():
    """Bulk update status for multiple prospects"""
    data = request.get_json()
    prospect_ids = data.get('prospect_ids', [])
    new_status = data.get('status')

    if not prospect_ids or not new_status:
        return jsonify({'error': 'Prospect IDs and status required'}), 400

    updated = 0
    for pid in prospect_ids:
        prospect = Prospect.query.get(pid)
        if prospect:
            old_status = prospect.status
            prospect.status = new_status
            prospect.updated_at = datetime.utcnow()
            updated += 1
            log_activity(prospect.id, 'status_change', f"Bulk update: {old_status} → {new_status}")

    db.session.commit()
    return jsonify({'success': True, 'updated': updated})

# ============ INITIALIZATION ============
with app.app_context():
    init_db()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))