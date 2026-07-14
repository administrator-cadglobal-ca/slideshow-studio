from flask_sqlalchemy import SQLAlchemy
from flask_login      import LoginManager
from flask_mail       import Mail
from celery           import Celery

db            = SQLAlchemy()
login_manager = LoginManager()
mail          = Mail()
celery_app    = Celery()

login_manager.login_view             = "auth.login"
login_manager.login_message          = "Please sign in to continue."
login_manager.login_message_category = "info"
