import os
import sqlite3
import csv
import io
import json
from datetime import datetime, timedelta
from functools import wraps

from flask import Flask, render_template, request, jsonify, session, redirect, url_for, g, flash
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'primeserv-crm-secret-key-2024')
app.config['SESSION_TYPE'] = 'filesystem'

DATABASE = 'primeserv_crm.db'

# ─── DATABASE ───

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def init_db():
    """Initialize database with all tables and default data."""
    if os.path.exists(DATABASE):
        return

    db = sqlite3.connect(DATABASE)
    cursor = db.cursor()

    # Users table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'user',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Pipelines table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pipelines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_by INTEGER,
            FOREIGN KEY (created_by) REFERENCES users(id)
        )
    """)

    # Sequences table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sequences (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pipeline_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            steps TEXT NOT NULL,
            is_default INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (pipeline_id) REFERENCES pipelines(id) ON DELETE CASCADE
        )
    """)

    # Prospects table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS prospects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pipeline_id INTEGER NOT NULL,
            first_name TEXT NOT NULL,
            last_name TEXT,
            email TEXT,
            linkedin_url TEXT,
            phone TEXT,
            company TEXT,
            tags TEXT DEFAULT '',
            status TEXT DEFAULT 'New Lead',
            notes TEXT,
            last_contact_date TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_by INTEGER,
            sequence_id INTEGER,
            current_step INTEGER DEFAULT 0,
            next_followup_date TIMESTAMP,
            FOREIGN KEY (pipeline_id) REFERENCES pipelines(id) ON DELETE CASCADE,
            FOREIGN KEY (created_by) REFERENCES users(id),
            FOREIGN KEY (sequence_id) REFERENCES sequences(id)
        )
    """)

    # Activity log table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS activity_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            prospect_id INTEGER,
            user_id INTEGER,
            action TEXT NOT NULL,
            details TEXT,
            old_value TEXT,
            new_value TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (prospect_id) REFERENCES prospects(id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    # Insert default admin user
    admin_hash = generate_password_hash('admin123')
    cursor.execute("""
        INSERT OR IGNORE INTO users (id, username, password, role) 
        VALUES (1, 'admin', ?, 'admin')
    """, (admin_hash,))

    # Insert sample pipelines
    cursor.execute("""
        INSERT INTO pipelines (name, description, created_by) 
        VALUES 
            ('LinkedIn Outreach', 'LinkedIn DM outreach pipeline for realtors', 1),
            ('Email Campaign', 'Cold email sequences for agent acquisition', 1),
            ('Instagram DMs', 'Instagram direct message outreach', 1)
    """)

    # Insert default sequences for each pipeline
    default_steps = json.dumps([
        {"days": 0, "status": "New Lead", "label": "Initial Contact"},
        {"days": 3, "status": "Sent", "label": "Follow Up 1"},
        {"days": 7, "status": "Sent 1", "label": "Follow Up 2"},
        {"days": 7, "status": "Sent 2", "label": "Follow Up 3"},
        {"days": 14, "status": "Sent 3", "label": "Follow Up 4"},
        {"days": 30, "status": "Nurture", "label": "Nurture"}
    ])

    for pipeline_id in [1, 2, 3]:
        cursor.execute("""
            INSERT INTO sequences (pipeline_id, name, steps, is_default)
            VALUES (?, 'Default Sequence', ?, 1)
        """, (pipeline_id, default_steps))

    # Insert sample prospects
    sample_prospects = [
        (1, 'John', 'Smith', 'john.smith@email.com', 'https://linkedin.com/in/johnsmith', '555-0101', 'Keller Williams', 'hot', 'New Lead', 'High-value prospect in Dallas', 1, 1),
        (1, 'Sarah', 'Johnson', 'sarah.j@email.com', 'https://linkedin.com/in/sarahj', '555-0102', 'RE/MAX', 'warm', 'Sent', 'Sent initial LinkedIn message', 1, 1),
        (2, 'Mike', 'Davis', 'mike.davis@email.com', 'https://linkedin.com/in/mikedavis', '555-0103', 'Coldwell Banker', 'cold', 'Sent 1', 'Email campaign day 3', 1, 2),
        (2, 'Lisa', 'Anderson', 'lisa.a@email.com', 'https://linkedin.com/in/lisaa', '555-0104', 'Century 21', 'hot', 'Responded', 'Interested in our services', 1, 2),
        (3, 'David', 'Wilson', 'david.w@email.com', 'https://linkedin.com/in/davidw', '555-0105', 'eXp Realty', 'warm', 'Meeting', 'Scheduled demo for next week', 1, 3),
        (1, 'Emma', 'Brown', 'emma.brown@email.com', 'https://linkedin.com/in/emmab', '555-0106', 'Berkshire Hathaway', 'cold', 'New Lead', 'New lead from referral', 1, 1),
        (2, 'James', 'Taylor', 'james.t@email.com', 'https://linkedin.com/in/jamest', '555-0107', 'Compass', 'hot', 'Proposal', 'Sent proposal yesterday', 1, 2),
        (3, 'Olivia', 'Martinez', 'olivia.m@email.com', 'https://linkedin.com/in/oliviam', '555-0108', 'Sotheby\'s', 'warm', 'Closed-Won', 'Signed contract last week', 1, 3),
    ]

    for p in sample_prospects:
        cursor.execute("""
            INSERT INTO prospects (pipeline_id, first_name, last_name, email, linkedin_url, phone, company, tags, status, notes, created_by, sequence_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, p)

    db.commit()
    db.close()
    print("Database initialized successfully!")

# Call init_db at module level - runs on import regardless of how app is started
init_db()

# ─── AUTH DECORATORS ───

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'error': 'Unauthorized'}), 401
            return redirect(url_for('login_page'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'Unauthorized'}), 401
        db = get_db()
        user = db.execute('SELECT role FROM users WHERE id = ?', (session['user_id'],)).fetchone()
        if not user or user['role'] != 'admin':
            return jsonify({'error': 'Admin access required'}), 403
        return f(*args, **kwargs)
    return decorated_function

# ─── ROUTES ───

@app.route('/login', methods=['GET', 'POST'])
def login_page():
    if request.method == 'GET':
        if 'user_id' in session:
            return redirect(url_for('index'))
        return render_template('login.html')

    data = request.get_json() or request.form
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()

    if not username or not password:
        return jsonify({'error': 'Username and password required'}), 400

    db = get_db()
    user = db.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()

    if user and check_password_hash(user['password'], password):
        session['user_id'] = user['id']
        session['username'] = user['username']
        session['role'] = user['role']
        return jsonify({'success': True, 'role': user['role']})

    return jsonify({'error': 'Invalid credentials'}), 401

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login_page'))

@app.route('/')
@login_required
def index():
    return render_template('index.html')

# ─── API: USERS ───

@app.route('/api/users', methods=['GET'])
@admin_required
def get_users():
    db = get_db()
    users = db.execute('SELECT id, username, role, created_at FROM users').fetchall()
    return jsonify([dict(u) for u in users])

@app.route('/api/users', methods=['POST'])
@admin_required
def create_user():
    data = request.get_json()
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()
    role = data.get('role', 'user')

    if not username or not password:
        return jsonify({'error': 'Username and password required'}), 400

    if role not in ('admin', 'user'):
        role = 'user'

    db = get_db()
    try:
        db.execute('INSERT INTO users (username, password, role) VALUES (?, ?, ?)',
                   (username, generate_password_hash(password), role))
        db.commit()
        return jsonify({'success': True})
    except sqlite3.IntegrityError:
        return jsonify({'error': 'Username already exists'}), 409

# ─── API: PIPELINES ───

@app.route('/api/pipelines', methods=['GET'])
@login_required
def get_pipelines():
    db = get_db()
    pipelines = db.execute("""
        SELECT p.*, COUNT(pr.id) as prospect_count 
        FROM pipelines p 
        LEFT JOIN prospects pr ON p.id = pr.pipeline_id 
        GROUP BY p.id 
        ORDER BY p.created_at DESC
    """).fetchall()
    return jsonify([dict(p) for p in pipelines])

@app.route('/api/pipelines', methods=['POST'])
@login_required
def create_pipeline():
    data = request.get_json()
    name = data.get('name', '').strip()
    description = data.get('description', '').strip()

    if not name:
        return jsonify({'error': 'Pipeline name required'}), 400

    db = get_db()
    cursor = db.execute(
        'INSERT INTO pipelines (name, description, created_by) VALUES (?, ?, ?)',
        (name, description, session['user_id'])
    )
    pipeline_id = cursor.lastrowid

    # Create default sequence for new pipeline
    default_steps = json.dumps([
        {"days": 0, "status": "New Lead", "label": "Initial Contact"},
        {"days": 3, "status": "Sent", "label": "Follow Up 1"},
        {"days": 7, "status": "Sent 1", "label": "Follow Up 2"},
        {"days": 7, "status": "Sent 2", "label": "Follow Up 3"},
        {"days": 14, "status": "Sent 3", "label": "Follow Up 4"},
        {"days": 30, "status": "Nurture", "label": "Nurture"}
    ])
    db.execute("""
        INSERT INTO sequences (pipeline_id, name, steps, is_default)
        VALUES (?, 'Default Sequence', ?, 1)
    """, (pipeline_id, default_steps))

    db.commit()
    return jsonify({'success': True, 'id': pipeline_id})

@app.route('/api/pipelines/<int:id>', methods=['DELETE'])
@login_required
def delete_pipeline(id):
    db = get_db()
    db.execute('DELETE FROM pipelines WHERE id = ?', (id,))
    db.commit()
    return jsonify({'success': True})

# ─── API: SEQUENCES ───

@app.route('/api/sequences', methods=['GET'])
@login_required
def get_sequences():
    pipeline_id = request.args.get('pipeline_id')
    db = get_db()

    if pipeline_id:
        sequences = db.execute(
            'SELECT * FROM sequences WHERE pipeline_id = ? ORDER BY is_default DESC, created_at DESC',
            (pipeline_id,)
        ).fetchall()
    else:
        sequences = db.execute('SELECT * FROM sequences ORDER BY created_at DESC').fetchall()

    result = []
    for s in sequences:
        row = dict(s)
        row['steps'] = json.loads(row['steps'])
        result.append(row)
    return jsonify(result)

@app.route('/api/sequences', methods=['POST'])
@login_required
def save_sequence():
    data = request.get_json()
    pipeline_id = data.get('pipeline_id')
    name = data.get('name', '').strip()
    steps = data.get('steps', [])
    sequence_id = data.get('id')

    if not name or not pipeline_id:
        return jsonify({'error': 'Name and pipeline required'}), 400

    steps_json = json.dumps(steps)
    db = get_db()

    if sequence_id:
        db.execute("""
            UPDATE sequences SET name = ?, steps = ? WHERE id = ?
        """, (name, steps_json, sequence_id))
    else:
        db.execute("""
            INSERT INTO sequences (pipeline_id, name, steps, is_default)
            VALUES (?, ?, ?, 0)
        """, (pipeline_id, name, steps_json))

    db.commit()
    return jsonify({'success': True})

# ─── API: PROSPECTS ───

STATUS_ORDER = [
    'New Lead', 'Sent', 'Sent 1', 'Sent 2', 'Sent 3', 'Sent 4+',
    'Responded', 'Meeting', 'Proposal', 'Closed-Won', 'Closed-Lost', 'Nurture'
]

def calculate_next_followup(created_at, sequence_steps, current_step):
    if not sequence_steps or current_step >= len(sequence_steps):
        return None

    total_days = sum(step['days'] for step in sequence_steps[:current_step + 1])
    next_date = datetime.strptime(created_at, '%Y-%m-%d %H:%M:%S') + timedelta(days=total_days)
    return next_date.strftime('%Y-%m-%d %H:%M:%S')

def get_followup_status(next_date_str):
    if not next_date_str:
        return 'on-track'

    next_date = datetime.strptime(next_date_str, '%Y-%m-%d %H:%M:%S')
    now = datetime.now()
    diff = (next_date - now).days

    if diff < 0:
        return 'overdue'
    elif diff <= 2:
        return 'due-soon'
    else:
        return 'on-track'

@app.route('/api/prospects', methods=['GET'])
@login_required
def get_prospects():
    pipeline_id = request.args.get('pipeline_id')
    search = request.args.get('search', '').strip()
    status = request.args.get('status', '').strip()
    tag = request.args.get('tag', '').strip()
    month = request.args.get('month', '').strip()
    year = request.args.get('year', '').strip()

    db = get_db()
    query = """
        SELECT p.*, s.name as sequence_name, s.steps as sequence_steps
        FROM prospects p
        LEFT JOIN sequences s ON p.sequence_id = s.id
        WHERE 1=1
    """
    params = []

    if pipeline_id:
        query += ' AND p.pipeline_id = ?'
        params.append(pipeline_id)

    if search:
        query += """ AND (
            p.first_name LIKE ? OR p.last_name LIKE ? OR 
            p.email LIKE ? OR p.company LIKE ?
        )"""
        like = f'%{search}%'
        params.extend([like, like, like, like])

    if status:
        query += ' AND p.status = ?'
        params.append(status)

    if tag:
        query += ' AND p.tags LIKE ?'
        params.append(f'%{tag}%')

    if month:
        query += ' AND strftime("%m", p.created_at) = ?'
        params.append(month.zfill(2))

    if year:
        query += ' AND strftime("%Y", p.created_at) = ?'
        params.append(year)

    query += ' ORDER BY p.created_at DESC'

    prospects = db.execute(query, params).fetchall()

    result = []
    for p in prospects:
        row = dict(p)
        row['tags'] = row['tags'].split(',') if row['tags'] else []
        row['tags'] = [t.strip() for t in row['tags'] if t.strip()]

        # Calculate follow-up status
        sequence_steps = json.loads(row['sequence_steps']) if row['sequence_steps'] else []
        row['sequence_steps'] = sequence_steps

        if row['next_followup_date']:
            row['followup_status'] = get_followup_status(row['next_followup_date'])
        else:
            row['followup_status'] = 'on-track'

        result.append(row)

    return jsonify(result)

@app.route('/api/prospects', methods=['POST'])
@login_required
def create_prospect():
    data = request.get_json()

    pipeline_id = data.get('pipeline_id')
    first_name = data.get('first_name', '').strip()
    last_name = data.get('last_name', '').strip()
    email = data.get('email', '').strip()
    linkedin_url = data.get('linkedin_url', '').strip()
    phone = data.get('phone', '').strip()
    company = data.get('company', '').strip()
    tags = data.get('tags', [])
    status = data.get('status', 'New Lead')
    notes = data.get('notes', '').strip()
    sequence_id = data.get('sequence_id')

    if not first_name or not pipeline_id:
        return jsonify({'error': 'First name and pipeline required'}), 400

    tags_str = ','.join(tags) if isinstance(tags, list) else str(tags)

    db = get_db()
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # Get sequence steps for follow-up calculation
    sequence_steps = []
    if sequence_id:
        seq = db.execute('SELECT steps FROM sequences WHERE id = ?', (sequence_id,)).fetchone()
        if seq:
            sequence_steps = json.loads(seq['steps'])

    next_followup = calculate_next_followup(now, sequence_steps, 0) if sequence_steps else None

    cursor = db.execute("""
        INSERT INTO prospects 
        (pipeline_id, first_name, last_name, email, linkedin_url, phone, company, tags, status, notes, created_by, sequence_id, current_step, next_followup_date, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (pipeline_id, first_name, last_name, email, linkedin_url, phone, company, tags_str, status, notes, session['user_id'], sequence_id, 0, next_followup, now, now))

    prospect_id = cursor.lastrowid

    # Log activity
    db.execute("""
        INSERT INTO activity_log (prospect_id, user_id, action, details, new_value)
        VALUES (?, ?, 'created', 'Prospect created', ?)
    """, (prospect_id, session['user_id'], json.dumps(data)))

    db.commit()
    return jsonify({'success': True, 'id': prospect_id})

@app.route('/api/prospects/<int:id>', methods=['PUT'])
@login_required
def update_prospect(id):
    data = request.get_json()
    db = get_db()

    # Get old values for activity log
    old = db.execute('SELECT * FROM prospects WHERE id = ?', (id,)).fetchone()
    if not old:
        return jsonify({'error': 'Prospect not found'}), 404

    updates = []
    params = []

    fields = ['first_name', 'last_name', 'email', 'linkedin_url', 'phone', 'company', 'status', 'notes', 'sequence_id']

    for field in fields:
        if field in data:
            updates.append(f'{field} = ?')
            params.append(data[field])

    if 'tags' in data:
        tags = data['tags']
        tags_str = ','.join(tags) if isinstance(tags, list) else str(tags)
        updates.append('tags = ?')
        params.append(tags_str)

    if 'status' in data and data['status'] != old['status']:
        updates.append('last_contact_date = ?')
        params.append(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

        # Log status change
        db.execute("""
            INSERT INTO activity_log (prospect_id, user_id, action, old_value, new_value)
            VALUES (?, ?, 'status_change', ?, ?)
        """, (id, session['user_id'], old['status'], data['status']))

    if updates:
        updates.append('updated_at = ?')
        params.append(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        params.append(id)

        db.execute(f"""
            UPDATE prospects SET {', '.join(updates)} WHERE id = ?
        """, params)

        # Log update
        db.execute("""
            INSERT INTO activity_log (prospect_id, user_id, action, details)
            VALUES (?, ?, 'updated', ?)
        """, (id, session['user_id'], json.dumps(data)))

        db.commit()

    return jsonify({'success': True})

@app.route('/api/prospects/<int:id>', methods=['DELETE'])
@login_required
def delete_prospect(id):
    db = get_db()
    db.execute('DELETE FROM prospects WHERE id = ?', (id,))
    db.execute("""
        INSERT INTO activity_log (user_id, action, details)
        VALUES (?, 'deleted', ?)
    """, (session['user_id'], f'Prospect {id} deleted'))
    db.commit()
    return jsonify({'success': True})

@app.route('/api/prospects/<int:id>/log-contact', methods=['POST'])
@login_required
def log_contact(id):
    data = request.get_json()
    notes = data.get('notes', '').strip()

    db = get_db()
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    db.execute("""
        UPDATE prospects SET last_contact_date = ?, updated_at = ? WHERE id = ?
    """, (now, now, id))

    db.execute("""
        INSERT INTO activity_log (prospect_id, user_id, action, details)
        VALUES (?, ?, 'contact_logged', ?)
    """, (id, session['user_id'], notes or 'Contact logged'))

    db.commit()
    return jsonify({'success': True})

# ─── API: IMPORT CSV ───

@app.route('/api/import-csv', methods=['POST'])
@login_required
def import_csv():
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    file = request.files['file']
    pipeline_id = request.form.get('pipeline_id')
    sequence_id = request.form.get('sequence_id')

    if not pipeline_id:
        return jsonify({'error': 'Pipeline required'}), 400

    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    try:
        stream = io.StringIO(file.stream.read().decode('UTF-8'), newline=None)
        csv_reader = csv.DictReader(stream)

        db = get_db()
        imported = 0
        errors = []
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # Get sequence steps
        sequence_steps = []
        if sequence_id:
            seq = db.execute('SELECT steps FROM sequences WHERE id = ?', (sequence_id,)).fetchone()
            if seq:
                sequence_steps = json.loads(seq['steps'])

        next_followup = calculate_next_followup(now, sequence_steps, 0) if sequence_steps else None

        for i, row in enumerate(csv_reader, 1):
            try:
                first_name = row.get('First Name', row.get('first_name', '')).strip()
                if not first_name:
                    first_name = row.get('Name', '').strip().split()[0] if row.get('Name') else ''

                if not first_name:
                    errors.append(f'Row {i}: Missing first name')
                    continue

                last_name = row.get('Last Name', row.get('last_name', '')).strip()
                if not last_name and 'Name' in row:
                    parts = row['Name'].strip().split()
                    if len(parts) > 1:
                        last_name = ' '.join(parts[1:])

                email = row.get('Email', row.get('email', '')).strip()
                linkedin = row.get('LinkedIn', row.get('LinkedIn URL', row.get('linkedin_url', ''))).strip()
                phone = row.get('Phone', row.get('phone', '')).strip()
                company = row.get('Company', row.get('company', '')).strip()
                tags = row.get('Tags', row.get('tags', '')).strip()

                cursor = db.execute("""
                    INSERT INTO prospects 
                    (pipeline_id, first_name, last_name, email, linkedin_url, phone, company, tags, status, created_by, sequence_id, current_step, next_followup_date, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'New Lead', ?, ?, ?, ?, ?, ?)
                """, (pipeline_id, first_name, last_name, email, linkedin, phone, company, tags, session['user_id'], sequence_id, 0, next_followup, now, now))

                prospect_id = cursor.lastrowid
                db.execute("""
                    INSERT INTO activity_log (prospect_id, user_id, action, details)
                    VALUES (?, ?, 'imported', 'Imported via CSV')
                """, (prospect_id, session['user_id']))

                imported += 1
            except Exception as e:
                errors.append(f'Row {i}: {str(e)}')

        db.commit()
        return jsonify({'success': True, 'imported': imported, 'errors': errors})

    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ─── API: ACTIVITY LOG ───

@app.route('/api/activity-log', methods=['GET'])
@login_required
def get_activity_log():
    prospect_id = request.args.get('prospect_id')
    db = get_db()

    if prospect_id:
        logs = db.execute("""
            SELECT al.*, u.username 
            FROM activity_log al
            LEFT JOIN users u ON al.user_id = u.id
            WHERE al.prospect_id = ?
            ORDER BY al.created_at DESC
        """, (prospect_id,)).fetchall()
    else:
        logs = db.execute("""
            SELECT al.*, u.username 
            FROM activity_log al
            LEFT JOIN users u ON al.user_id = u.id
            ORDER BY al.created_at DESC
            LIMIT 100
        """).fetchall()

    return jsonify([dict(l) for l in logs])

# ─── API: STATS ───

@app.route('/api/stats', methods=['GET'])
@login_required
def get_stats():
    pipeline_id = request.args.get('pipeline_id')
    db = get_db()

    query = 'SELECT * FROM prospects WHERE 1=1'
    params = []

    if pipeline_id:
        query += ' AND pipeline_id = ?'
        params.append(pipeline_id)

    prospects = db.execute(query, params).fetchall()

    total = len(prospects)
    overdue = 0
    due_soon = 0
    on_track = 0

    for p in prospects:
        status = get_followup_status(p['next_followup_date']) if p['next_followup_date'] else 'on-track'
        if status == 'overdue':
            overdue += 1
        elif status == 'due-soon':
            due_soon += 1
        else:
            on_track += 1

    return jsonify({
        'total': total,
        'overdue': overdue,
        'due_soon': due_soon,
        'on_track': on_track
    })

# ─── ERROR HANDLERS ───

@app.errorhandler(404)
def not_found(e):
    if request.is_json:
        return jsonify({'error': 'Not found'}), 404
    return render_template('login.html'), 404

@app.errorhandler(500)
def server_error(e):
    if request.is_json:
        return jsonify({'error': 'Internal server error'}), 500
    return render_template('login.html'), 500

# ─── MAIN ───

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=True)
