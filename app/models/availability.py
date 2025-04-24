from app import db
from datetime import datetime, time

# Days of the week constants (0 = Monday, 6 = Sunday)
MONDAY = 0
TUESDAY = 1
WEDNESDAY = 2
THURSDAY = 3
FRIDAY = 4
SATURDAY = 5
SUNDAY = 6

class BusinessHours(db.Model):
    __tablename__ = 'business_hours'
    
    id = db.Column(db.Integer, primary_key=True)
    day_of_week = db.Column(db.Integer, nullable=False)  # 0-6 (Monday-Sunday)
    open_time = db.Column(db.Time, nullable=False)
    close_time = db.Column(db.Time, nullable=False)
    is_closed = db.Column(db.Boolean, default=False)
    
    def __init__(self, day_of_week, open_time, close_time, is_closed=False):
        self.day_of_week = day_of_week
        self.open_time = open_time
        self.close_time = close_time
        self.is_closed = is_closed
    
    @classmethod
    def get_business_hours(cls):
        """Returns a dictionary of business hours by day of week"""
        hours = cls.query.all()
        result = {}
        for hour in hours:
            result[hour.day_of_week] = hour
        return result
    
    def __repr__(self):
        if self.is_closed:
            return f'<BusinessHours: Day {self.day_of_week} - CLOSED>'
        return f'<BusinessHours: Day {self.day_of_week} - {self.open_time} to {self.close_time}>'


class BlockedTime(db.Model):
    __tablename__ = 'blocked_times'
    
    id = db.Column(db.Integer, primary_key=True)
    stylist_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime, nullable=False)
    reason = db.Column(db.String(255), nullable=True)
    is_holiday = db.Column(db.Boolean, default=False)  # True if set by admin as holiday
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __init__(self, stylist_id, start_time, end_time, reason=None, is_holiday=False):
        self.stylist_id = stylist_id
        self.start_time = start_time
        self.end_time = end_time
        self.reason = reason
        self.is_holiday = is_holiday
    
    def __repr__(self):
        if self.is_holiday:
            return f'<Holiday: {self.start_time.date()} - {self.reason}>'
        return f'<BlockedTime: {self.start_time} to {self.end_time}>'