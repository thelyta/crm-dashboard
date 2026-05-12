# PrimeServ CRM

A fully functional CRM web application for PrimeServ Agency — built to manage and fix client acquisition systems for US realtors.

## Features

- **Multi-Pipeline System**: Create unlimited custom pipelines (LinkedIn Outreach, Email Campaign, Instagram DMs, etc.)
- **Custom Follow-Up Sequences**: Per-pipeline sequences with customizable steps
- **Prospect Management**: Full contact details, tags, status tracking, notes
- **Smart Follow-Up Alerts**: Color-coded urgency indicators (Red=Overdue, Yellow=Due Soon, Green=On Track)
- **Dual Views**: Kanban Pipeline View + Table View with inline editing
- **Advanced Filtering**: Search, status, tag, month, year filters
- **CSV Import**: Drag & drop CSV import with preview
- **Activity Logging**: Full audit trail of all changes
- **User Management**: Admin can create users with role-based access
- **Session-Based Authentication**: Secure login/logout

## Default Login

- **Username**: `admin`
- **Password**: `admin123`

## Local Setup

1. Clone or extract the project files
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Run the application:
   ```bash
   flask run --port=8080
   ```
   Or:
   ```bash
   python app.py
   ```
4. Open your browser to `http://localhost:8080`
5. Login with `admin` / `admin123`

## Database

The SQLite database auto-initializes on first run. No manual setup needed.

## Deploy to Render.com (Free Tier)

1. Push your code to GitHub
2. Go to [Render.com](https://render.com) and create a new Web Service
3. Connect your GitHub repository
4. Set the following:
   - **Runtime**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app:app`
5. Add environment variable:
   - `SECRET_KEY`: Generate a random string (e.g., from `openssl rand -hex 32`)
6. Click "Create Web Service"

### Alternative: Deploy to PythonAnywhere

1. Upload files to PythonAnywhere
2. Create a new web app with Flask
3. Update WSGI file to point to your `app.py`
4. Set `SECRET_KEY` in environment variables
5. Reload the web app

## Tech Stack

- **Backend**: Python Flask + SQLite
- **Frontend**: Vanilla JavaScript, HTML, CSS
- **Authentication**: Session-based with Werkzeug password hashing
- **Deployment**: Ready for Render.com, Railway, or PythonAnywhere free tier

## File Structure

```
primeserv-crm/
├── app.py                  # Main Flask application
├── requirements.txt        # Python dependencies
├── README.md              # This file
├── primeserv_crm.db       # SQLite database (auto-created)
├── templates/
│   ├── login.html         # Login page
│   └── index.html         # Main CRM dashboard
├── static/
│   ├── css/
│   │   └── style.css      # All styles
│   └── js/
│       └── app.js         # All JavaScript
```

## CSV Import Format

Expected columns (case-insensitive):
- `First Name` / `first_name`
- `Last Name` / `last_name`
- `Email` / `email`
- `LinkedIn` / `LinkedIn URL` / `linkedin_url`
- `Phone` / `phone`
- `Company` / `company`
- `Tags` / `tags`

## License

Built for PrimeServ Agency. All rights reserved.
