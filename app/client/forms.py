from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SelectField, SubmitField, DateTimeField
from wtforms.validators import DataRequired, Length, ValidationError, Email
from datetime import datetime, timedelta

class AppointmentForm(FlaskForm):
    """Form for booking a new appointment"""
    stylist_id = SelectField('Select Stylist', validators=[DataRequired()], coerce=int)
    service_id = SelectField('Select Service', validators=[DataRequired()], coerce=int)
    start_time = DateTimeField('Appointment Time', validators=[DataRequired()], format='%Y-%m-%d %H:%M')
    notes = TextAreaField('Special Requests/Notes', validators=[Length(max=500)])
    submit = SubmitField('Book Appointment')
    
    def validate_start_time(self, start_time):
        # Ensure appointment is in the future
        if start_time.data <= datetime.now():
            raise ValidationError('Appointment time must be in the future.')
        
        # Ensure appointment is at least 1 hour in the future
        if start_time.data <= datetime.now() + timedelta(hours=1):
            raise ValidationError('Appointments must be booked at least 1 hour in advance.')
        
        # Additional validation could check business hours, stylist availability, etc.

class ProfileUpdateForm(FlaskForm):
    """Form for updating client profile information"""
    first_name = StringField('First Name', validators=[DataRequired(), Length(min=1, max=50)])
    last_name = StringField('Last Name', validators=[DataRequired(), Length(min=1, max=50)])
    phone = StringField('Phone Number', validators=[Length(max=20)])
    submit = SubmitField('Update Profile')