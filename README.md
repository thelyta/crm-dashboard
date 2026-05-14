PrimeServ CRM
A fully functional CRM web application for PrimeServ Agency — built to manage and fix client acquisition systems for US realtors.
✨ New Features (Latest Update)
1. Editable Last Contact Date
Last Contact Date field in prospect form — manually set when you last reached out
Auto-calculates Next Follow-Up date based on assigned sequence
Displays days since last contact in kanban cards and table view
2. Enhanced CSV Import
Auto-detects Status column from CSV and maps to CRM status
Auto-detects Date Sent / Last Contact column and maps to Last Contact Date
Supports multiple date formats: YYYY-MM-DD, MM/DD/YYYY, Month DD, YYYY, etc.
Preview shows column mapping before import
Import with sequence assignment for automatic follow-up scheduling
3. Follow-Up & Nurture Sequence Improvements
Sequence Progress Tracking: Visual step indicator (Step 2/7) on cards and details
One-Click Advance: ⏭️ button to move prospect to next sequence step
Bulk Actions: Select multiple prospects and advance sequences, update status, or delete
Smart Next Follow-Up: Automatically calculated from sequence steps + last contact date
Re-engagement Nurture: Final step auto-sets to "Nurture" status for long-term follow-up
Contact Logging: Log interactions — auto-updates last contact date and recalculates next follow-up
Follow-Up Alerts: Color-coded urgency (Red=Overdue, Yellow=Due Soon, Green=On Track)
Core Features
Multi-Pipeline System: Create unlimited custom pipelines (LinkedIn Outreach, Email Campaign, Instagram DMs, etc.)
Custom Follow-Up Sequences: Per-pipeline sequences with customizable steps and day intervals
Prospect Management: Full contact details, tags, status tracking, notes, last contact history
Smart Follow-Up Alerts: Color-coded urgency indicators
Dual Views: Kanban Pipeline View + Table View with inline editing
Advanced Filtering: Search, status, tag, month, year filters
CSV Import: Drag & drop with column auto-detection
Activity Logging: Full audit trail of all changes
User Management: Admin can create users with role-based access
Session-Based Authentication: Secure login/logout
Default Login
Username: admin
Password: admin123
Local Setup
Clone or extract the project files
Install dependencies:
bash
Copy
pip install -r requirements.txt
Run the application:
bash
Copy
flask run --port=8080
Or:
bash
Copy
python app.py
Open your browser to http://localhost:8080
Login with admin / admin123
Database
The SQLite database auto-initializes on first run with:
Default admin user
Default "LinkedIn Outreach" pipeline
Default 7-step follow-up sequence (0, 1, 3, 7, 14, 30, 45 days)
Deploy to Render.com (Free Tier)
Push your code to GitHub
Go to Render.com and create a new Web Service
Connect your GitHub repository
Set the following:
Runtime: Python 3
Build Command: pip install -r requirements.txt
Start Command: gunicorn app:app
Add environment variable:
SECRET_KEY: Generate a random string (e.g., from openssl rand -hex 32)
Click "Create Web Service"
Alternative: Deploy to PythonAnywhere
Upload files to PythonAnywhere
Create a new web app with Flask
Update WSGI file to point to your app.py
Set SECRET_KEY in environment variables
Reload the web app
Tech Stack
Backend: Python Flask + SQLite (auto-upgrades to PostgreSQL on Render)
Frontend: Vanilla JavaScript, HTML, CSS
Authentication: Session-based with Werkzeug password hashing
Deployment: Ready for Render.com, Railway, or PythonAnywhere free tier
File Structure
plain
Copy
primeserv-crm/
├── app.py                  # Main Flask application
├── requirements.txt        # Python dependencies
├── README.md              # This file
├── crm.db                 # SQLite database (auto-created)
├── templates/
│   ├── login.html         # Login page
│   └── index.html         # Main CRM dashboard
├── static/
│   ├── css/
│   │   └── style.css      # All styles
│   └── js/
│       └── app.js         # All JavaScript
CSV Import Format
Expected columns (case-insensitive, auto-detected):
First Name / first_name / firstname
Last Name / last_name / lastname
Email / email
LinkedIn / LinkedIn URL / linkedin_url
Phone / phone
Company / company / organization
Tags / tags
NEW: Status / stage → Maps to CRM Status
NEW: Date Sent / date_sent / last_contact / sent_date → Maps to Last Contact Date
Sequence System
Default sequence steps:
Day 0: New Lead — Initial Contact
Day 1: Sent — First Message
Day 3: Sent 1 — Follow Up 1
Day 7: Sent 2 — Follow Up 2
Day 14: Sent 3 — Follow Up 3
Day 30: Sent 4+ — Final Follow Up
Day 45: Nurture — Re-engage
License
Built for PrimeServ Agency. All rights reserved.