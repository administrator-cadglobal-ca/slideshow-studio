@echo off
echo ============================================
echo  Slideshow Studio - Windows Dev Setup
echo ============================================
echo.

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found. Install from python.org
    pause & exit /b 1
)

echo Step 1: Creating virtual environment...
python -m venv venv
call venv\Scripts\activate.bat

echo.
echo Step 2: Installing dependencies...
pip install -r requirements.txt

echo.
echo Step 3: Creating .env file...
if not exist .env (
    (
        echo FLASK_ENV=development
        echo FLASK_DEBUG=1
        echo SECRET_KEY=slideshowstudio-dev-key-change-this-later
        echo.
        echo DATABASE_URL=sqlite:///slideshow_studio.db
        echo.
        echo STORAGE_ROOT=P:\slideshow
        echo TEMP_ROOT=D:\Temp\slideshow_render
        echo.
        echo SLIDESHOW_MAKER_PATH=P:\slideshow\Slideshow_MP4_Generator_v2.5\slideshow_maker.py
        echo FFMPEG_PATH=ffmpeg
        echo.
        echo ADMIN_EMAIL=gurmeet.singh@cadglobal.ca
        echo ADMIN_PHONE=+14034721845
        echo.
        echo APP_URL=http://localhost:5000
        echo GOOGLE_REDIRECT_URI=http://localhost:5000/auth/google/callback
        echo.
        echo TWILIO_ACCOUNT_SID=
        echo TWILIO_AUTH_TOKEN=
        echo TWILIO_FROM_NUMBER=
        echo.
        echo REDIS_URL=redis://localhost:6379/0
        echo.
        echo MAIL_SERVER=smtp.gmail.com
        echo MAIL_PORT=587
        echo MAIL_USERNAME=
        echo MAIL_PASSWORD=
        echo MAIL_DEFAULT_SENDER=
    ) > .env
    echo .env created with your settings.
) else (
    echo .env already exists - skipping.
)

echo.
echo Step 4: Creating storage folder on pCloud...
if not exist "P:\slideshow" (
    mkdir "P:\slideshow"
    echo Created P:\slideshow
) else (
    echo P:\slideshow already exists.
)

echo.
echo Step 5: Creating temp render folder...
if not exist "D:\Temp\slideshow_render" (
    mkdir "D:\Temp\slideshow_render"
    echo Created D:\Temp\slideshow_render
) else (
    echo D:\Temp\slideshow_render already exists.
)

echo.
echo ============================================
echo  Setup complete!
echo ============================================
echo.
echo  Admin email : gurmeet.singh@cadglobal.ca
echo  Admin phone : +14034721845
echo  Storage     : P:\slideshow
echo  Temp        : D:\Temp\slideshow_render
echo.
echo  Next: edit .env to set your real ADMIN_PHONE
echo  Then: run start_dev.bat
echo  Open: http://localhost:5000
echo.
pause
