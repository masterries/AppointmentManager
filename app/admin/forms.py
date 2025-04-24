from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SelectField, SubmitField, BooleanField, PasswordField, DecimalField, IntegerField, DateField, HiddenField
from wtforms.validators import DataRequired, Email, Length, Optional, NumberRange, ValidationError, EqualTo
from app.models.user import User, ROLE_CLIENT, ROLE_STYLIST, ROLE_ADMIN
from datetime import datetime

class UserCreateForm(FlaskForm):
    """Form for creating a new user"""
    email = StringField('Email', validators=[DataRequired(), Email(), Length(max=120)])
    first_name = StringField('First Name', validators=[DataRequired(), Length(min=1, max=50)])
    last_name = StringField('Last Name', validators=[DataRequired(), Length(min=1, max=50)])
    phone = StringField('Phone Number', validators=[Length(max=20)])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=8)])
    role = SelectField('Role', choices=[
        (ROLE_CLIENT, 'Client'),
        (ROLE_STYLIST, 'Stylist'),
        (ROLE_ADMIN, 'Administrator')
    ], validators=[DataRequired()])
    submit = SubmitField('Create User')
    
    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user:
            raise ValidationError('Email already registered. Please use a different email.')

class UserUpdateForm(FlaskForm):
    """Form for updating an existing user"""
    id = HiddenField()
    email = StringField('Email', validators=[DataRequired(), Email(), Length(max=120)])
    first_name = StringField('First Name', validators=[DataRequired(), Length(min=1, max=50)])
    last_name = StringField('Last Name', validators=[DataRequired(), Length(min=1, max=50)])
    phone = StringField('Phone Number', validators=[Length(max=20)])
    password = PasswordField('New Password (leave blank to keep current)', validators=[Optional(), Length(min=8)])
    confirm_password = PasswordField('Confirm New Password', 
                                    validators=[Optional(), EqualTo('password', message='Passwords must match')])
    role = SelectField('Role', choices=[
        (ROLE_CLIENT, 'Client'),
        (ROLE_STYLIST, 'Stylist'),
        (ROLE_ADMIN, 'Administrator')
    ], validators=[DataRequired()])
    is_active = BooleanField('Account Active')
    submit = SubmitField('Update User')
    
    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user and user.id != int(self.id.data):
            raise ValidationError('Email already registered. Please use a different email.')

class ServiceForm(FlaskForm):
    """Form for creating or updating a salon service"""
    name = StringField('Service Name', validators=[DataRequired(), Length(max=100)])
    description = TextAreaField('Description', validators=[Optional(), Length(max=500)])
    price = DecimalField('Price ($)', validators=[DataRequired(), NumberRange(min=0)])
    duration_minutes = IntegerField('Duration (minutes)', validators=[
        DataRequired(),
        NumberRange(min=5, message='Service duration must be at least 5 minutes')
    ])
    is_active = BooleanField('Active')
    submit = SubmitField('Save Service')

class BusinessHoursForm(FlaskForm):
    """Form for updating business hours"""
    # This form is handled differently in the routes, using individual form fields
    # for each day of the week
    submit = SubmitField('Update Business Hours')

class HolidayForm(FlaskForm):
    """Form for adding salon holidays"""
    date = DateField('Date', validators=[DataRequired()])
    description = StringField('Description', validators=[DataRequired(), Length(max=255)])
    submit = SubmitField('Add Holiday')
    
    def validate_date(self, date):
        if date.data < datetime.now().date():
            raise ValidationError('Holiday date cannot be in the past.')