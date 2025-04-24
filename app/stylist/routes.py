from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app import db
from app.models.user import User
from app.models.appointment import Appointment, STATUS_SCHEDULED, STATUS_COMPLETED, STATUS_CANCELLED, STATUS_NO_SHOW
from app.models.service import Service
from app.models.client_notes import ClientNote
from app.models.availability import BlockedTime
from app.stylist.forms import BlockTimeForm, ClientNoteForm, AppointmentStatusForm, ProfileUpdateForm
from datetime import datetime, timedelta
from functools import wraps
from app.utils.audit import log_audit, audit_log_decorator
from werkzeug.utils import secure_filename

stylist_bp = Blueprint('stylist', __name__, url_prefix='/stylist')

# Custom decorator to ensure only stylists can access these routes
def stylist_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_stylist():
            flash('Access denied. This area is for stylists only.', 'danger')
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated_function

@stylist_bp.route('/dashboard')
@login_required
@stylist_required
def dashboard():
    """Stylist dashboard showing today's and upcoming appointments"""
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow = today + timedelta(days=1)
    
    # Get today's appointments
    today_appointments = Appointment.query.filter_by(
        stylist_id=current_user.id, 
        status=STATUS_SCHEDULED
    ).filter(
        Appointment.start_time >= today,
        Appointment.start_time < tomorrow
    ).order_by(Appointment.start_time).all()
    
    # Get upcoming appointments
    upcoming_appointments = Appointment.query.filter_by(
        stylist_id=current_user.id,
        status=STATUS_SCHEDULED
    ).filter(
        Appointment.start_time >= tomorrow
    ).order_by(Appointment.start_time).limit(10).all()
    
    return render_template(
        'stylist/dashboard.html',
        today_appointments=today_appointments,
        upcoming_appointments=upcoming_appointments
    )

@stylist_bp.route('/appointments')
@login_required
@stylist_required
def appointments():
    """View all stylist appointments with filtering options"""
    status_filter = request.args.get('status', 'scheduled')
    date_from = request.args.get('date_from', datetime.utcnow().strftime('%Y-%m-%d'))
    
    # Convert date string to datetime
    try:
        date_from = datetime.strptime(date_from, '%Y-%m-%d')
    except ValueError:
        date_from = datetime.utcnow()
    
    # Start with base query
    query = Appointment.query.filter_by(stylist_id=current_user.id)
    
    # Apply filters
    if status_filter != 'all':
        query = query.filter_by(status=status_filter)
    
    query = query.filter(Appointment.start_time >= date_from)
    
    # Get final results ordered by date
    appointments = query.order_by(Appointment.start_time).all()
    
    return render_template(
        'stylist/appointments.html',
        appointments=appointments,
        status_filter=status_filter,
        date_from=date_from.strftime('%Y-%m-%d')
    )

@stylist_bp.route('/update-appointment-status/<int:appointment_id>', methods=['GET', 'POST'])
@login_required
@stylist_required
def update_appointment_status(appointment_id):
    """Update the status of an appointment"""
    appointment = Appointment.query.get_or_404(appointment_id)
    
    # Ensure the appointment belongs to this stylist
    if appointment.stylist_id != current_user.id:
        flash('Access denied. You can only update your own appointments.', 'danger')
        return redirect(url_for('stylist.appointments'))
    
    form = AppointmentStatusForm()
    form.status.choices = [
        (STATUS_SCHEDULED, 'Scheduled'),
        (STATUS_COMPLETED, 'Completed'),
        (STATUS_CANCELLED, 'Cancelled'),
        (STATUS_NO_SHOW, 'No Show')
    ]
    
    if request.method == 'GET':
        form.status.default = appointment.status
        form.process()
    
    if form.validate_on_submit():
        # Store old status for audit log
        old_status = appointment.status
        
        # Update status
        appointment.status = form.status.data
        db.session.commit()
        
        # Log the status change
        service = Service.query.get(appointment.service_id)
        client = User.query.get(appointment.client_id)
        
        audit_details = {
            'old_status': old_status,
            'new_status': form.status.data,
            'client_id': client.id,
            'client_name': client.get_full_name(),
            'service_id': service.id,
            'service_name': service.name,
            'appointment_time': appointment.start_time.strftime('%Y-%m-%d %H:%M')
        }
        
        log_audit('update', 'appointment_status', entity_id=appointment.id, details=audit_details)
        
        flash('Appointment status updated successfully.', 'success')
        return redirect(url_for('stylist.appointments'))
    
    return render_template(
        'stylist/update_appointment_status.html',
        form=form,
        appointment=appointment
    )

@stylist_bp.route('/availability', methods=['GET', 'POST'])
@login_required
@stylist_required
def availability():
    """View and manage stylist availability"""
    form = BlockTimeForm()
    
    if form.validate_on_submit():
        blocked_time = BlockedTime(
            stylist_id=current_user.id,
            start_time=form.start_time.data,
            end_time=form.end_time.data,
            reason=form.reason.data
        )
        
        db.session.add(blocked_time)
        db.session.commit()
        
        # Log the blocked time creation
        audit_details = {
            'start_time': form.start_time.data.strftime('%Y-%m-%d %H:%M'),
            'end_time': form.end_time.data.strftime('%Y-%m-%d %H:%M'),
            'reason': form.reason.data,
            'is_holiday': False
        }
        log_audit('create', 'blocked_time', entity_id=blocked_time.id, details=audit_details)
        
        flash('Time block added successfully.', 'success')
        return redirect(url_for('stylist.availability'))
    
    # Get existing blocked times
    blocked_times = BlockedTime.query.filter_by(
        stylist_id=current_user.id
    ).filter(
        BlockedTime.end_time >= datetime.utcnow()
    ).order_by(BlockedTime.start_time).all()
    
    return render_template(
        'stylist/availability.html',
        form=form,
        blocked_times=blocked_times
    )

@stylist_bp.route('/remove-blocked-time/<int:blocked_time_id>', methods=['POST'])
@login_required
@stylist_required
def remove_blocked_time(blocked_time_id):
    """Remove a blocked time period"""
    blocked_time = BlockedTime.query.get_or_404(blocked_time_id)
    
    # Ensure the blocked time belongs to this stylist
    if blocked_time.stylist_id != current_user.id:
        flash('Access denied. You can only remove your own blocked times.', 'danger')
        return redirect(url_for('stylist.availability'))
    
    # Gather details for audit log before deletion
    audit_details = {
        'start_time': blocked_time.start_time.strftime('%Y-%m-%d %H:%M'),
        'end_time': blocked_time.end_time.strftime('%Y-%m-%d %H:%M'),
        'reason': blocked_time.reason,
        'is_holiday': blocked_time.is_holiday if hasattr(blocked_time, 'is_holiday') else False
    }
    
    # Store the ID before deletion
    blocked_time_id = blocked_time.id
    
    db.session.delete(blocked_time)
    db.session.commit()
    
    # Log the removal action
    log_audit('delete', 'blocked_time', entity_id=blocked_time_id, details=audit_details)
    
    flash('Blocked time removed successfully.', 'success')
    return redirect(url_for('stylist.availability'))

@stylist_bp.route('/client-notes/<int:client_id>', methods=['GET', 'POST'])
@login_required
@stylist_required
def client_notes(client_id):
    """View and add notes for a specific client"""
    client = User.query.get_or_404(client_id)
    
    # Ensure this is actually a client
    if not client.is_client():
        flash('Invalid client selected.', 'danger')
        return redirect(url_for('stylist.dashboard'))
    
    form = ClientNoteForm()
    
    if form.validate_on_submit():
        note = ClientNote(
            client_id=client_id,
            stylist_id=current_user.id,
            note=form.note.data
        )
        
        db.session.add(note)
        db.session.commit()
        
        # Log the client note creation
        audit_details = {
            'client_id': client_id,
            'client_name': client.get_full_name(),
            'note_summary': form.note.data[:50] + ('...' if len(form.note.data) > 50 else '')
        }
        log_audit('create', 'client_note', entity_id=note.id, details=audit_details)
        
        flash('Client note added successfully.', 'success')
        return redirect(url_for('stylist.client_notes', client_id=client_id))
    
    # Get existing notes for this client by this stylist
    notes = ClientNote.query.filter_by(
        client_id=client_id,
        stylist_id=current_user.id
    ).order_by(ClientNote.created_at.desc()).all()
    
    # Get appointments history for context
    appointments = Appointment.query.filter_by(
        client_id=client_id,
        stylist_id=current_user.id
    ).order_by(Appointment.start_time.desc()).all()
    
    return render_template(
        'stylist/client_notes.html',
        client=client,
        form=form,
        notes=notes,
        appointments=appointments
    )

@stylist_bp.route('/clients')
@login_required
@stylist_required
def clients():
    """View all clients who have had appointments with this stylist"""
    # Find all unique clients who have had appointments with this stylist
    client_ids = db.session.query(Appointment.client_id).filter_by(
        stylist_id=current_user.id
    ).distinct().all()
    
    # Extract the IDs and get the client objects
    client_ids = [id[0] for id in client_ids]
    clients = User.query.filter(User.id.in_(client_ids)).all()
    
    return render_template('stylist/clients.html', clients=clients)

@stylist_bp.route('/profile', methods=['GET', 'POST'])
@login_required
@stylist_required
def profile():
    """Update stylist profile information"""
    form = ProfileUpdateForm(obj=current_user)
    
    if form.validate_on_submit():
        # Capture old values for audit log
        old_values = {
            'first_name': current_user.first_name,
            'last_name': current_user.last_name,
            'phone': current_user.phone,
            'bio': current_user.bio,
            'specialties': current_user.specialties,
            'profile_image': current_user.profile_image
        }
        
        # Update user data
        current_user.first_name = form.first_name.data
        current_user.last_name = form.last_name.data
        current_user.phone = form.phone.data
        current_user.bio = form.bio.data
        current_user.specialties = form.specialties.data
        
        # Handle profile image upload
        profile_image_changed = False
        if form.profile_image.data:
            # Save profile image
            filename = secure_filename(form.profile_image.data.filename)
            # Code to save image would go here
            current_user.profile_image = filename
            profile_image_changed = True
        
        # Prepare audit details
        audit_details = {
            'old_values': old_values,
            'new_values': {
                'first_name': form.first_name.data,
                'last_name': form.last_name.data,
                'phone': form.phone.data,
                'bio': form.bio.data,
                'specialties': form.specialties.data,
                'profile_image': current_user.profile_image
            },
            'profile_image_changed': profile_image_changed
        }
        
        db.session.commit()
        
        # Log the profile update
        log_audit('update', 'stylist_profile', entity_id=current_user.id, details=audit_details)
        
        flash('Your profile has been updated.', 'success')
        return redirect(url_for('stylist.profile'))
    
    return render_template('stylist/profile.html', form=form)