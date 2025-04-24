from app import db
from datetime import datetime

# Appointment status constants
STATUS_SCHEDULED = 'scheduled'
STATUS_COMPLETED = 'completed'
STATUS_CANCELLED = 'cancelled'
STATUS_NO_SHOW = 'no_show'

class Appointment(db.Model):
    __tablename__ = 'appointments'
    
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    stylist_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    service_id = db.Column(db.Integer, db.ForeignKey('services.id'), nullable=False)
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(20), default=STATUS_SCHEDULED)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __init__(self, client_id, stylist_id, service_id, start_time, end_time, notes=None):
        self.client_id = client_id
        self.stylist_id = stylist_id
        self.service_id = service_id
        self.start_time = start_time
        self.end_time = end_time
        self.notes = notes
    
    def cancel(self):
        self.status = STATUS_CANCELLED
    
    def complete(self):
        self.status = STATUS_COMPLETED
    
    def mark_no_show(self):
        self.status = STATUS_NO_SHOW
    
    def is_active(self):
        return self.status == STATUS_SCHEDULED
    
    def __repr__(self):
        return f'<Appointment {self.id}: {self.start_time} - {self.end_time}>'