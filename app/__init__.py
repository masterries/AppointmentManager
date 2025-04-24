# Import important modules and create app package
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from dotenv import load_dotenv
import os
from datetime import datetime

# Load environment variables
load_dotenv()

# Initialize extensions
db = SQLAlchemy()
login_manager = LoginManager()
migrate = Migrate()

def create_app():
    # Initialize app
    app = Flask(__name__)
    
    # Configure app
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-key')
    
    # Use SQLite database directly without trying PostgreSQL
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///salon_booking.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # Initialize extensions with app
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this page.'
    migrate.init_app(app, db)
    
    # Register blueprints
    from app.auth.routes import auth_bp
    from app.client.routes import client_bp
    from app.stylist.routes import stylist_bp
    from app.admin.routes import admin_bp
    from app.main.routes import main_bp
    
    app.register_blueprint(auth_bp)
    app.register_blueprint(client_bp)
    app.register_blueprint(stylist_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(main_bp)
    
    # Add context processor for template variables
    @app.context_processor
    def inject_now():
        return {'now': datetime.utcnow()}
    
    # Create database tables
    with app.app_context():
        db.create_all()
        print("SQLite database tables created successfully")
    
    return app