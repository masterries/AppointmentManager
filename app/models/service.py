from app import db
from datetime import datetime

class Service(db.Model):
    __tablename__ = 'services'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    price = db.Column(db.Numeric(10, 2), nullable=False)
    duration_minutes = db.Column(db.Integer, nullable=False)  # Duration in minutes
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    appointments = db.relationship('Appointment', backref='service', lazy='dynamic')
    
    def __init__(self, name, price, duration_minutes, description=None, is_active=True):
        self.name = name
        self.price = price
        self.duration_minutes = duration_minutes
        self.description = description
        self.is_active = is_active
    
    def __repr__(self):
        return f'<Service {self.name}>'