from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import StringField, TextAreaField, SelectField, SubmitField, DateTimeField
from wtforms.validators import DataRequired, Length, ValidationError
from datetime import datetime, timedelta

class BlockTimeForm(FlaskForm):
    """Form for blocking out unavailable time periods"""
    start_time = DateTimeField('Start Time', validators=[DataRequired()], format='%Y-%m-%d %H:%M')
    end_time = DateTimeField('End Time', validators=[DataRequired()], format='%Y-%m-%d %H:%M')
    reason = StringField('Reason (optional)', validators=[Length(max=255)])
    submit = SubmitField('Block Time')
    
    def validate_start_time(self, start_time):
        # Ensure start time is in the future
        if start_time.data <= datetime.now():
            raise ValidationError('Start time must be in the future.')
    
    def validate_end_time(self, end_time):
        # Ensure end time is after start time
        if end_time.data <= self.start_time.data:
            raise ValidationError('End time must be after start time.')

class ClientNoteForm(FlaskForm):
    """Form for adding notes about a client"""
    note = TextAreaField('Add Note', validators=[DataRequired(), Length(max=1000)])
    submit = SubmitField('Save Note')

class AppointmentStatusForm(FlaskForm):
    """Form for updating appointment status"""
    status = SelectField('Status', validators=[DataRequired()], choices=[])
    submit = SubmitField('Update Status')

class ProfileUpdateForm(FlaskForm):
    """Form for updating stylist profile information"""
    first_name = StringField('First Name', validators=[DataRequired(), Length(min=1, max=50)])
    last_name = StringField('Last Name', validators=[DataRequired(), Length(min=1, max=50)])
    phone = StringField('Phone Number', validators=[Length(max=20)])
    bio = TextAreaField('Bio/About Me', validators=[Length(max=500)])
    specialties = StringField('Specialties', validators=[Length(max=255)])
    profile_image = FileField('Profile Picture', validators=[
        FileAllowed(['jpg', 'png', 'jpeg'], 'Images only!')
    ])
    submit = SubmitField('Update Profile')