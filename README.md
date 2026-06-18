# Seller Master Management System

A professional Flask-based ERP/CRM Seller Management System with full bilingual (English/Arabic) support.

---

## Features

- **Authentication** – Login, logout, remember-me, role-based (Admin/Staff)
- **Dashboard** – Stats cards, recent sellers, quick actions
- **Seller CRUD** – Add, edit, delete, view with 5-section tabbed form
- **Document Management** – Upload, view, download, delete (PDF/JPG/PNG)
- **Multiple Contacts** – Per-seller contact management
- **Activity Logs** – Full audit trail per seller
- **Search & Filters** – Real-time search by code/name/email, filter by status/type/country
- **Pagination & Sorting** – Sortable columns with paginated results
- **Export to CSV** – One-click seller data export
- **Bilingual** – Full English/Arabic with RTL Bootstrap support
- **Security** – CSRF protection, password hashing, file type validation, SQL injection protection

---

## Quick Start

### 1. Clone / Extract

```bash
cd seller_ms
```

### 2. Create Virtual Environment

```bash
python -m venv venv
source venv/bin/activate       # Linux/Mac
venv\Scripts\activate          # Windows
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Run the Application

```bash
python app.py
```

The app will automatically:
- Create the SQLite database
- Create default admin and staff users
- Start the development server on `http://localhost:5000`

---

## Default Login Credentials

| Role  | Username | Password   |
|-------|----------|------------|
| Admin | admin    | Admin@123  |
| Staff | staff    | Staff@123  |

> **Change these passwords immediately in production!**

---

## Project Structure

```
seller_ms/
├── app.py                  # Application factory & entry point
├── config.py               # Configuration classes
├── models.py               # SQLAlchemy database models
├── forms.py                # WTForms form classes
├── requirements.txt        # Python dependencies
│
├── routes/
│   ├── __init__.py
│   ├── auth.py             # Login/logout/language routes
│   ├── dashboard.py        # Dashboard statistics
│   └── sellers.py          # Seller CRUD + documents + contacts
│
├── templates/
│   ├── base.html           # Master layout with sidebar
│   ├── auth/login.html     # Login page
│   ├── dashboard/index.html
│   ├── sellers/
│   │   ├── list.html       # Seller list with search/filter
│   │   ├── form.html       # Add/Edit form (5 tab sections)
│   │   └── view.html       # Profile with contacts/docs/activity
│   └── errors/404.html, 403.html
│
├── static/
│   ├── css/style.css       # Complete custom stylesheet
│   └── js/app.js           # Frontend interactions
│
├── uploads/                # Uploaded documents (auto-created)
└── database/               # SQLite database (auto-created)
    └── sellers.db
```

---

## Database Schema

| Table            | Description                          |
|------------------|--------------------------------------|
| users            | Admin and staff accounts             |
| sellers          | Core seller master records           |
| seller_contacts  | Multiple contacts per seller         |
| seller_documents | Uploaded files with metadata         |
| activity_logs    | Audit trail of all changes           |

---

## Role Permissions

| Feature              | Admin | Staff |
|----------------------|-------|-------|
| View sellers         | ✅    | ✅    |
| Search & filter      | ✅    | ✅    |
| Export CSV           | ✅    | ✅    |
| Add seller           | ✅    | ❌    |
| Edit seller (full)   | ✅    | ❌    |
| Edit contact info    | ✅    | ✅    |
| Delete seller        | ✅    | ❌    |
| Manage documents     | ✅    | Upload only |
| Delete documents     | ✅    | ❌    |

---

## Production Deployment

### Environment Variables

```bash
export SECRET_KEY="your-very-secret-key-here"
export FLASK_ENV=production
```

### Using Gunicorn

```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:8000 "app:app"
```

### Nginx Configuration

```nginx
server {
    listen 80;
    server_name yourdomain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /uploads/ {
        alias /path/to/seller_ms/uploads/;
    }

    location /static/ {
        alias /path/to/seller_ms/static/;
    }
}
```

---

## Tech Stack

- **Backend**: Python 3.10+, Flask 3.x, SQLAlchemy 2.x
- **Auth**: Flask-Login, Werkzeug password hashing, Flask-WTF CSRF
- **Frontend**: Bootstrap 5.3 (LTR & RTL), Font Awesome 6, Vanilla JS
- **Database**: SQLite (development), easily switchable to PostgreSQL/MySQL
- **i18n**: Flask-Babel with Arabic/English support

---

## Language Switching

Click the globe icon (🌐) in the top navbar to switch between English and Arabic. The preference is saved in the session. Arabic mode uses Bootstrap RTL automatically.

---

## Security Features

- ✅ CSRF tokens on all forms
- ✅ Bcrypt password hashing
- ✅ File type & size validation for uploads
- ✅ SQLAlchemy ORM (no raw SQL → no injection)
- ✅ Role-based access control
- ✅ Secure filename handling (uuid-based filenames)
- ✅ Login required on all protected routes

---

## Customization

- **Colors**: Edit CSS variables in `static/css/style.css` (`:root` block)
- **Items per page**: Change `ITEMS_PER_PAGE` in `config.py`
- **Allowed file types**: Edit `ALLOWED_EXTENSIONS` in `config.py`
- **Max upload size**: Edit `MAX_CONTENT_LENGTH` in `config.py`
- **Add seller fields**: Update `models.py` → `forms.py` → `templates/sellers/form.html`
