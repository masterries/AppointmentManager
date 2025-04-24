from app import db
from datetime import datetime
import json
from app.utils.json_utils import DecimalEncoder

class AuditLog(db.Model):
    """Model for tracking audit logs of system events"""
    __tablename__ = 'audit_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    action = db.Column(db.String(50), nullable=False)  # create, update, delete, etc.
    entity_type = db.Column(db.String(50), nullable=False)  # user, appointment, service, etc.
    entity_id = db.Column(db.Integer, nullable=True)
    details = db.Column(db.Text, nullable=True)  # JSON-serialized additional details
    ip_address = db.Column(db.String(50), nullable=True)
    
    # Relationship
    user = db.relationship('User', backref=db.backref('audit_logs', lazy=True))
    
    def __init__(self, action, entity_type, user_id=None, entity_id=None, details=None, ip_address=None):
        self.user_id = user_id
        self.action = action
        self.entity_type = entity_type
        self.entity_id = entity_id
        self.details = json.dumps(details, cls=DecimalEncoder) if isinstance(details, (dict, list)) else details
        self.ip_address = ip_address
        
    def get_details_dict(self):
        """Convert stored JSON details back to dictionary"""
        if not self.details:
            return {}
        try:
            return json.loads(self.details)
        except:
            return {"raw": self.details}
    
    def __repr__(self):
        return f'<AuditLog {self.action} {self.entity_type} {self.entity_id}>'