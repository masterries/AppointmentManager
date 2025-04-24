from app import db
from datetime import datetime

class ClientNote(db.Model):
    __tablename__ = 'client_notes'
    
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    stylist_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    note = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship to client
    client = db.relationship('User', foreign_keys=[client_id], backref=db.backref('notes_about_me', lazy='dynamic'))
    
    def __init__(self, client_id, stylist_id, note):
        self.client_id = client_id
        self.stylist_id = stylist_id
        self.note = note
    
    def __repr__(self):
        return f'<ClientNote: {self.id}>'