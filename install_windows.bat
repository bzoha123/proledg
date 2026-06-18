@echo off
echo ============================================
echo  Seller Master System - Windows Installer
echo ============================================
echo.

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found. Install from https://python.org
    pause
    exit /b 1
)

echo [1/4] Creating virtual environment...
python -m venv venv
call venv\Scripts\activate.bat

echo [2/4] Upgrading pip...
python -m pip install --upgrade pip --quiet

echo [3/4] Installing dependencies...
pip install Flask==3.0.3 --quiet
pip install Flask-SQLAlchemy==3.1.1 --quiet
pip install Flask-Login==0.6.3 --quiet
pip install Flask-WTF==1.2.1 --quiet
pip install Flask-Migrate==4.0.7 --quiet
pip install Werkzeug==3.0.3 --quiet
pip install SQLAlchemy==2.0.36 --quiet
pip install WTForms==3.1.2 --quiet
pip install Babel==2.16.0 --quiet
pip install Flask-Babel==4.0.0 --quiet
pip install python-dotenv==1.0.1 --quiet
pip install Pillow --quiet

echo [4/4] Creating folders...
if not exist "database" mkdir database
if not exist "uploads" mkdir uploads

echo.
echo ============================================
echo  Installation complete!
echo  Run:  python app.py
echo  Open: http://localhost:5000
echo  Login: admin / Admin@123
echo ============================================
pause
