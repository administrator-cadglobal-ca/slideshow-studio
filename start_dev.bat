@echo off
echo Starting Slideshow Studio...
call venv\Scripts\activate.bat
set FLASK_ENV=development
python run.py
pause
