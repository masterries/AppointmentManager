from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, current_app
from flask_login import login_required, current_user
from app import db
from app.models.user import User, ROLE_CLIENT
from app.models.appointment import Appointment
from app.models.service import Service
from app.models.availability import BusinessHours, BlockedTime
from app.client.forms import AppointmentForm, ProfileUpdateForm
from datetime import datetime, timedelta, time
from functools import wraps
from app.utils.audit import log_audit, audit_log_decorator
import traceback

client_bp = Blueprint('client', __name__, url_prefix='/client')

# Custom decorator to ensure only clients can access these routes
def client_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_client():
            flash('Access denied. This area is for clients only.', 'danger')
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated_function

@client_bp.route('/dashboard')
@login_required
@client_required
def dashboard():
    """Client dashboard showing upcoming appointments"""
    # Get upcoming appointments for the client
    upcoming_appointments = Appointment.query.filter_by(
        client_id=current_user.id
    ).filter(
        Appointment.start_time > datetime.utcnow(), 
        Appointment.status == 'scheduled'
    ).order_by(Appointment.start_time).all()
    
    # Get past appointments for history
    past_appointments = Appointment.query.filter_by(
        client_id=current_user.id
    ).filter(
        Appointment.start_time <= datetime.utcnow()
    ).order_by(Appointment.start_time.desc()).limit(5).all()
    
    return render_template(
        'client/dashboard.html',
        upcoming_appointments=upcoming_appointments,
        past_appointments=past_appointments
    )

@client_bp.route('/appointments')
@login_required
@client_required
def appointments():
    """View all client appointments"""
    # Get all appointments for the client
    all_appointments = Appointment.query.filter_by(
        client_id=current_user.id
    ).order_by(Appointment.start_time.desc()).all()
    
    return render_template('client/appointments.html', appointments=all_appointments)

@client_bp.route('/book', methods=['GET', 'POST'])
@login_required
@client_required
def book_appointment():
    """Book a new appointment"""
    form = AppointmentForm()
    
    # Populate form choices for stylists and services
    stylists = User.query.filter_by(role='stylist').all()
    form.stylist_id.choices = [(s.id, s.get_full_name()) for s in stylists]
    
    services = Service.query.filter_by(is_active=True).all()
    form.service_id.choices = [(s.id, f"{s.name} (${s.price} - {s.duration_minutes} min)") for s in services]
    
    if form.validate_on_submit():
        service = Service.query.get(form.service_id.data)
        
        # Calculate end time based on service duration
        end_time = form.start_time.data + timedelta(minutes=service.duration_minutes)
        
        # Check one more time if the slot is available
        is_available = check_appointment_slot_available(
            form.stylist_id.data,
            form.start_time.data,
            end_time
        )
        
        if not is_available:
            flash('Sorry, this time slot is no longer available. Please select another time.', 'danger')
            return redirect(url_for('client.book_appointment'))
        
        appointment = Appointment(
            client_id=current_user.id,
            stylist_id=form.stylist_id.data,
            service_id=form.service_id.data,
            start_time=form.start_time.data,
            end_time=end_time,
            notes=form.notes.data
        )
        
        db.session.add(appointment)
        db.session.commit()
        
        # Log the appointment booking action
        try:
            audit_details = {
                'service_id': service.id,
                'service_name': service.name,
                'stylist_id': form.stylist_id.data,
                'appointment_time': form.start_time.data.strftime('%Y-%m-%d %H:%M'),
                'price': service.price
            }
            log_success = log_audit('create', 'appointment', entity_id=appointment.id, details=audit_details)
            if not log_success:
                current_app.logger.error(f"Failed to create audit log for appointment {appointment.id}")
        except Exception as e:
            error_trace = traceback.format_exc()
            current_app.logger.error(f"Exception in appointment audit logging: {str(e)}\n{error_trace}")
        
        # Instead of sending email, just show a more detailed confirmation message
        stylist = User.query.get(form.stylist_id.data)
        service = Service.query.get(form.service_id.data)
        
        # Use Windows-compatible date formatting (no %-type specifiers)
        day_name = appointment.start_time.strftime('%A')
        month_name = appointment.start_time.strftime('%B')
        day = appointment.start_time.day
        year = appointment.start_time.year
        hour = appointment.start_time.strftime('%I').lstrip('0')
        minute = appointment.start_time.strftime('%M')
        am_pm = appointment.start_time.strftime('%p')
        
        # Format the date manually without using %-type specifiers
        confirmation_message = f"""
        Appointment booked successfully!
        
        Date & Time: {day_name}, {month_name} {day}, {year} at {hour}:{minute} {am_pm}
        Service: {service.name}
        Duration: {service.duration_minutes} minutes
        Stylist: {stylist.get_full_name()}
        Price: ${service.price}
        
        If you need to reschedule or cancel, please do so at least 24 hours in advance.
        """
        
        flash(confirmation_message, 'success')
        return redirect(url_for('client.dashboard'))
    
    return render_template('client/book_appointment.html', form=form)

@client_bp.route('/cancel/<int:appointment_id>', methods=['POST'])
@login_required
@client_required
def cancel_appointment(appointment_id):
    """Cancel an existing appointment"""
    appointment = Appointment.query.get_or_404(appointment_id)
    
    # Ensure the appointment belongs to the current user
    if appointment.client_id != current_user.id:
        flash('Access denied. You can only cancel your own appointments.', 'danger')
        return redirect(url_for('client.dashboard'))
    
    # Check if appointment can be cancelled (not in the past, etc.)
    if appointment.start_time <= datetime.utcnow():
        flash('Cannot cancel an appointment that has already started or completed.', 'danger')
        return redirect(url_for('client.dashboard'))
    
    # Get details before cancellation for audit log
    stylist = User.query.get(appointment.stylist_id)
    service = Service.query.get(appointment.service_id)
    audit_details = {
        'service_id': service.id,
        'service_name': service.name,
        'stylist_id': appointment.stylist_id,
        'stylist_name': stylist.get_full_name(),
        'appointment_time': appointment.start_time.strftime('%Y-%m-%d %H:%M'),
        'cancellation_time': datetime.utcnow().strftime('%Y-%m-%d %H:%M')
    }
    
    appointment.cancel()
    db.session.commit()
    
    # Log the cancellation action with better error handling
    try:
        log_success = log_audit('cancel', 'appointment', entity_id=appointment.id, details=audit_details)
        if not log_success:
            current_app.logger.error(f"Failed to create audit log for appointment cancellation {appointment.id}")
    except Exception as e:
        error_trace = traceback.format_exc()
        current_app.logger.error(f"Exception in appointment cancellation audit logging: {str(e)}\n{error_trace}")
    
    # Just show a confirmation message instead of sending an email
    # Use Windows-compatible date formatting (no %-type specifiers)
    day_name = appointment.start_time.strftime('%A')
    month_name = appointment.start_time.strftime('%B')
    day = appointment.start_time.day
    year = appointment.start_time.year
    hour = appointment.start_time.strftime('%I').lstrip('0')
    minute = appointment.start_time.strftime('%M')
    am_pm = appointment.start_time.strftime('%p')
    
    # Format the date manually without using %-type specifiers
    cancellation_message = f"""
    Your appointment has been cancelled.
    
    Date & Time: {day_name}, {month_name} {day}, {year} at {hour}:{minute} {am_pm}
    Service: {service.name}
    Stylist: {stylist.get_full_name()}
    
    We hope to see you again soon!
    """
    
    flash(cancellation_message, 'info')
    return redirect(url_for('client.dashboard'))

@client_bp.route('/profile', methods=['GET', 'POST'])
@login_required
@client_required
def profile():
    """Update client profile information"""
    form = ProfileUpdateForm(obj=current_user)
    
    if form.validate_on_submit():
        # Capture old values for audit log
        old_values = {
            'first_name': current_user.first_name,
            'last_name': current_user.last_name,
            'phone': current_user.phone
        }
        
        # Update user data
        current_user.first_name = form.first_name.data
        current_user.last_name = form.last_name.data
        current_user.phone = form.phone.data
        
        # Prepare audit details
        audit_details = {
            'old_values': old_values,
            'new_values': {
                'first_name': form.first_name.data,
                'last_name': form.last_name.data,
                'phone': form.phone.data
            }
        }
        
        db.session.commit()
        
        # Log the profile update
        log_audit('update', 'user_profile', entity_id=current_user.id, details=audit_details)
        
        flash('Your profile has been updated.', 'success')
        return redirect(url_for('client.profile'))
    
    return render_template('client/profile.html', form=form)

@client_bp.route('/get_available_times', methods=['POST'])
@login_required
@client_required
def get_available_times():
    """HTMX endpoint to get available appointment times"""
    stylist_id = request.form.get('stylist_id')
    service_id = request.form.get('service_id')
    date_str = request.form.get('appointment_date')
    
    # Validate inputs
    if not stylist_id or not service_id or not date_str:
        if request.is_json:
            return jsonify({"error": "Missing required parameters"}), 400
        else:
            return render_template('client/partials/available_times.html', 
                                 error_message="Please select a stylist, service, and date")
    
    try:
        # Parse date
        selected_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        
        # Convert to integers
        stylist_id = int(stylist_id)
        service_id = int(service_id)
        
        # Get service for duration
        service = Service.query.get(service_id)
        if not service:
            return render_template('client/partials/available_times.html', 
                                 error_message="Selected service not found")
        
        # Check if this is a business day
        day_of_week = selected_date.weekday()  # 0-6, Monday is 0
        business_hours = BusinessHours.query.filter_by(day_of_week=day_of_week).first()
        
        if not business_hours or business_hours.is_closed:
            return render_template('client/partials/available_times.html', 
                                 error_message="We're closed on this day")
        
        # Check if the date is in the future
        if selected_date < datetime.now().date():
            return render_template('client/partials/available_times.html', 
                                 error_message="Please select a future date")
        
        # Check for salon holidays
        holiday = BlockedTime.query.filter(
            BlockedTime.stylist_id == stylist_id,
            BlockedTime.is_holiday == True,
            BlockedTime.start_time <= datetime.combine(selected_date, time(23, 59)),
            BlockedTime.end_time >= datetime.combine(selected_date, time(0, 0))
        ).first()
        
        if holiday:
            return render_template('client/partials/available_times.html', 
                                 error_message=f"Salon closed: {holiday.reason}")
        
        # Get all blocked times for this stylist on this date
        blocked_times = BlockedTime.query.filter(
            BlockedTime.stylist_id == stylist_id,
            BlockedTime.start_time <= datetime.combine(selected_date, time(23, 59)),
            BlockedTime.end_time >= datetime.combine(selected_date, time(0, 0))
        ).all()
        
        # Get all existing appointments for this stylist on this date
        existing_appointments = Appointment.query.filter(
            Appointment.stylist_id == stylist_id,
            Appointment.start_time >= datetime.combine(selected_date, time(0, 0)),
            Appointment.start_time <= datetime.combine(selected_date, time(23, 59)),
            Appointment.status == 'scheduled'
        ).all()
        
        # Generate available time slots
        open_time = business_hours.open_time
        close_time = business_hours.close_time
        
        interval = 30  # Minutes between time slots
        service_duration = service.duration_minutes
        
        # Start from either opening time or current time if booking for today
        if selected_date == datetime.now().date():
            # Round up to the nearest interval
            now = datetime.now().time()
            minutes = (now.hour * 60) + now.minute
            next_slot_minutes = ((minutes // interval) + 1) * interval
            start_hour = next_slot_minutes // 60
            start_minute = next_slot_minutes % 60
            
            # Add buffer time of 1 hour
            buffer_minutes = 60
            start_minutes_with_buffer = next_slot_minutes + buffer_minutes
            start_hour = start_minutes_with_buffer // 60
            start_minute = start_minutes_with_buffer % 60
            
            current_time = time(start_hour, start_minute)
            if current_time > open_time:
                start_time = current_time
            else:
                start_time = open_time
        else:
            start_time = open_time
        
        # Calculate all possible time slots
        available_times = []
        current_datetime = datetime.combine(selected_date, start_time)
        end_datetime = datetime.combine(selected_date, close_time) - timedelta(minutes=service_duration)
        
        while current_datetime <= end_datetime:
            slot_end_time = current_datetime + timedelta(minutes=service_duration)
            is_available = True
            
            # Check if slot overlaps with any existing appointments
            for appointment in existing_appointments:
                # If the proposed slot overlaps with an existing appointment
                if (current_datetime < appointment.end_time and
                    slot_end_time > appointment.start_time):
                    is_available = False
                    break
            
            # Check if slot overlaps with any blocked times
            for blocked in blocked_times:
                # If the proposed slot overlaps with a blocked time
                if (current_datetime < blocked.end_time and
                    slot_end_time > blocked.start_time):
                    is_available = False
                    break
            
            if is_available:
                # Fixed format string to be Windows-compatible (removed the dash in %-I)
                available_times.append({
                    'datetime': current_datetime.strftime('%Y-%m-%d %H:%M'),
                    'formatted_time': current_datetime.strftime('%I:%M %p').lstrip('0')
                })
            
            # Move to next slot
            current_datetime += timedelta(minutes=interval)
        
        return render_template('client/partials/available_times.html', 
                             available_times=available_times)
    
    except Exception as e:
        print(f"Error generating available times: {str(e)}")
        return render_template('client/partials/available_times.html', 
                             error_message="An error occurred. Please try again.")


def check_appointment_slot_available(stylist_id, start_time, end_time):
    """Check if a specific appointment slot is available"""
    
    # Check if the time falls within business hours
    day_of_week = start_time.date().weekday()
    business_hours = BusinessHours.query.filter_by(day_of_week=day_of_week).first()
    
    if not business_hours or business_hours.is_closed:
        return False
    
    # Create datetime objects with the selected date but business hours times
    open_datetime = datetime.combine(start_time.date(), business_hours.open_time)
    close_datetime = datetime.combine(start_time.date(), business_hours.close_time)
    
    # Check if appointment start and end times fall within business hours
    if start_time < open_datetime or end_time > close_datetime:
        return False
    
    # Check for blocked times
    blocked_time = BlockedTime.query.filter(
        BlockedTime.stylist_id == stylist_id,
        BlockedTime.start_time < end_time,
        BlockedTime.end_time > start_time
    ).first()
    
    if blocked_time:
        return False
    
    # Check for existing appointments
    existing_appointment = Appointment.query.filter(
        Appointment.stylist_id == stylist_id,
        Appointment.status == 'scheduled',
        Appointment.start_time < end_time,
        Appointment.end_time > start_time
    ).first()
    
    if existing_appointment:
        return False
    
    return True