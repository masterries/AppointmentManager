from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from app import db, login_manager

# User roles
ROLE_CLIENT = 'client'
ROLE_STYLIST = 'stylist'
ROLE_ADMIN = 'admin'

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    phone = db.Column(db.String(20), nullable=True)
    role = db.Column(db.String(20), default=ROLE_CLIENT)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Stylist specific fields
    bio = db.Column(db.Text, nullable=True)
    profile_image = db.Column(db.String(255), nullable=True)
    specialties = db.Column(db.String(255), nullable=True)
    
    # Relationships
    appointments_as_client = db.relationship('Appointment', foreign_keys='Appointment.client_id', backref='client', lazy='dynamic')
    appointments_as_stylist = db.relationship('Appointment', foreign_keys='Appointment.stylist_id', backref='stylist', lazy='dynamic')
    blocked_times = db.relationship('BlockedTime', backref='stylist', lazy='dynamic')
    client_notes = db.relationship('ClientNote', foreign_keys='ClientNote.stylist_id', backref='stylist', lazy='dynamic')
    
    def __init__(self, email, first_name, last_name, password, role=ROLE_CLIENT, phone=None):
        self.email = email
        self.first_name = first_name
        self.last_name = last_name
        self.set_password(password)
        self.role = role
        self.phone = phone
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
        
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def is_admin(self):
        return self.role == ROLE_ADMIN
    
    def is_stylist(self):
        return self.role == ROLE_STYLIST
    
    def is_client(self):
        return self.role == ROLE_CLIENT
    
    def get_full_name(self):
        return f"{self.first_name} {self.last_name}"
    
    def __repr__(self):
        return f'<User {self.email}>'

@login_manager.user_loader
def load_user(id):
    return User.query.get(int(id))