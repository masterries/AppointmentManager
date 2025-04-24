from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app import db
from app.models.user import User, ROLE_CLIENT, ROLE_STYLIST, ROLE_ADMIN
from app.models.service import Service
from app.models.availability import BusinessHours, BlockedTime, MONDAY, TUESDAY, WEDNESDAY, THURSDAY, FRIDAY, SATURDAY, SUNDAY
from app.models.appointment import Appointment, STATUS_SCHEDULED, STATUS_COMPLETED, STATUS_CANCELLED, STATUS_NO_SHOW
from app.models.audit import AuditLog
from app.admin.forms import ServiceForm, BusinessHoursForm, UserCreateForm, UserUpdateForm, HolidayForm
from datetime import datetime, time, timedelta
from functools import wraps
from sqlalchemy import func, extract, case, and_, or_
from collections import defaultdict
from app.utils.audit import log_audit, audit_log_decorator

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

# Custom decorator to ensure only admins can access these routes
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin():
            flash('Access denied. This area is for administrators only.', 'danger')
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated_function

@admin_bp.route('/dashboard')
@login_required
@admin_required
def dashboard():
    """Admin dashboard with overview of system statistics"""
    # Count users by role
    total_clients = User.query.filter_by(role=ROLE_CLIENT).count()
    total_stylists = User.query.filter_by(role=ROLE_STYLIST).count()
    total_admins = User.query.filter_by(role=ROLE_ADMIN).count()
    
    # Count appointments
    total_appointments = Appointment.query.count()
    upcoming_appointments = Appointment.query.filter(
        Appointment.start_time > datetime.utcnow(),
        Appointment.status == 'scheduled'
    ).count()
    
    # Count services
    total_services = Service.query.count()
    active_services = Service.query.filter_by(is_active=True).count()
    
    return render_template(
        'admin/dashboard.html',
        total_clients=total_clients,
        total_stylists=total_stylists,
        total_admins=total_admins,
        total_appointments=total_appointments,
        upcoming_appointments=upcoming_appointments,
        total_services=total_services,
        active_services=active_services
    )

@admin_bp.route('/analytics')
@login_required
@admin_required
def analytics():
    """Advanced analytics and reports for appointments and revenue"""
    # Get date range from request parameters or use defaults
    try:
        date_from = datetime.strptime(request.args.get('date_from', ''), '%Y-%m-%d')
    except (ValueError, TypeError):
        date_from = datetime.now() - timedelta(days=30)  # Default to last 30 days
    
    try:
        date_to = datetime.strptime(request.args.get('date_to', ''), '%Y-%m-%d')
        # Set time to end of day
        date_to = date_to.replace(hour=23, minute=59, second=59)
    except (ValueError, TypeError):
        date_to = datetime.now()
    
    # Base query with date filter
    base_query = Appointment.query.filter(
        Appointment.start_time >= date_from,
        Appointment.start_time <= date_to
    )
    
    # Calculate basic statistics
    total_appointments = base_query.count()
    
    # Status counts and percentages
    status_counts = []
    if total_appointments > 0:
        for status in [STATUS_SCHEDULED, STATUS_COMPLETED, STATUS_CANCELLED, STATUS_NO_SHOW]:
            count = base_query.filter(Appointment.status == status).count()
            status_counts.append({
                'name': status,
                'count': count,
                'percentage': (count / total_appointments) * 100 if total_appointments > 0 else 0
            })
    
    # Calculate revenue from completed appointments
    revenue_query = db.session.query(
        func.sum(Service.price)
    ).join(
        Appointment, Service.id == Appointment.service_id
    ).filter(
        Appointment.status == STATUS_COMPLETED,
        Appointment.start_time >= date_from,
        Appointment.start_time <= date_to
    )
    
    # Ensure total_revenue is a native Python float rather than a SQLAlchemy Decimal or other type
    revenue_value = revenue_query.scalar()
    total_revenue = float(revenue_value) if revenue_value is not None else 0.0
    
    # Calculate completion rate
    total_scheduled_completed = base_query.filter(
        or_(Appointment.status == STATUS_SCHEDULED, 
            Appointment.status == STATUS_COMPLETED)
    ).count()
    
    completed_count = base_query.filter(Appointment.status == STATUS_COMPLETED).count()
    
    completion_rate = 0
    if total_scheduled_completed > 0:
        completion_rate = (completed_count / total_scheduled_completed) * 100
    
    # Count new clients (first-time appointments) within the period
    new_clients_subquery = db.session.query(
        Appointment.client_id,
        func.min(Appointment.start_time).label('first_appointment')
    ).group_by(Appointment.client_id).subquery()
    
    new_clients = db.session.query(func.count(new_clients_subquery.c.client_id)).filter(
        new_clients_subquery.c.first_appointment >= date_from,
        new_clients_subquery.c.first_appointment <= date_to
    ).scalar() or 0
    
    # Services breakdown
    service_data = {
        'labels': [],
        'values': []
    }
    
    services_breakdown = db.session.query(
        Service.name,
        func.count(Appointment.id)
    ).join(
        Appointment, Service.id == Appointment.service_id
    ).filter(
        Appointment.start_time >= date_from,
        Appointment.start_time <= date_to
    ).group_by(Service.name).all()
    
    for service_name, count in services_breakdown:
        service_data['labels'].append(service_name)
        service_data['values'].append(count)
    
    # Stylists breakdown
    stylist_data = {
        'labels': [],
        'values': []
    }
    
    stylists_breakdown = db.session.query(
        User.first_name,
        User.last_name,
        func.count(Appointment.id)
    ).join(
        Appointment, User.id == Appointment.stylist_id
    ).filter(
        Appointment.start_time >= date_from,
        Appointment.start_time <= date_to
    ).group_by(User.id).all()
    
    for first_name, last_name, count in stylists_breakdown:
        stylist_data['labels'].append(f"{first_name} {last_name}")
        stylist_data['values'].append(count)
    
    # Appointments by day of week
    weekday_counts = [0] * 7  # 0 for Monday through 6 for Sunday
    
    weekday_breakdown = db.session.query(
        extract('dow', Appointment.start_time),  # 0 is Sunday in SQL
        func.count(Appointment.id)
    ).filter(
        Appointment.start_time >= date_from,
        Appointment.start_time <= date_to
    ).group_by(extract('dow', Appointment.start_time)).all()
    
    for dow, count in weekday_breakdown:
        # Convert SQL's Sunday=0 to Python's Monday=0 indexing
        adjusted_dow = (dow - 1) % 7
        weekday_counts[adjusted_dow] = count
    
    # Combine all stats into one object
    stats = {
        'total_appointments': total_appointments,
        'status_counts': status_counts,
        'total_revenue': total_revenue,  # Now properly converted to float
        'completion_rate': completion_rate,
        'new_clients': new_clients,
        'service_data': service_data,
        'stylist_data': stylist_data,
        'weekday_data': weekday_counts
    }
    
    return render_template(
        'admin/analytics.html',
        stats=stats,
        date_from=date_from,
        date_to=date_to
    )

@admin_bp.route('/users')
@login_required
@admin_required
def users():
    """List all users with role filtering"""
    role_filter = request.args.get('role', 'all')
    
    if role_filter == 'all':
        users_list = User.query.all()
    else:
        users_list = User.query.filter_by(role=role_filter).all()
    
    return render_template(
        'admin/users.html',
        users=users_list,
        role_filter=role_filter
    )

@admin_bp.route('/users/create', methods=['GET', 'POST'])
@login_required
@admin_required
def create_user():
    """Create a new user (client, stylist, or admin)"""
    form = UserCreateForm()
    
    if form.validate_on_submit():
        user = User(
            email=form.email.data,
            first_name=form.first_name.data,
            last_name=form.last_name.data,
            password=form.password.data,
            role=form.role.data,
            phone=form.phone.data
        )
        
        db.session.add(user)
        db.session.commit()
        
        # Log user creation action
        role_name_map = {
            ROLE_CLIENT: 'Client',
            ROLE_STYLIST: 'Stylist',
            ROLE_ADMIN: 'Administrator'
        }
        
        audit_details = {
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'role': user.role,
            'role_name': role_name_map.get(user.role, 'Unknown'),
            'phone': user.phone
        }
        
        log_audit('create', 'user', entity_id=user.id, details=audit_details)
        
        flash(f'User {user.email} created successfully.', 'success')
        return redirect(url_for('admin.users'))
    
    return render_template('admin/create_user.html', form=form)

@admin_bp.route('/users/update/<int:user_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def update_user(user_id):
    """Update an existing user"""
    user = User.query.get_or_404(user_id)
    form = UserUpdateForm(obj=user)
    
    if form.validate_on_submit():
        # Store old values for audit log
        old_values = {
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'phone': user.phone,
            'role': user.role,
            'is_active': user.is_active
        }
        
        # Update user data
        user.email = form.email.data
        user.first_name = form.first_name.data
        user.last_name = form.last_name.data
        user.phone = form.phone.data
        user.role = form.role.data
        user.is_active = form.is_active.data
        
        # Track password change
        password_changed = False
        if form.password.data:
            user.set_password(form.password.data)
            password_changed = True
        
        # Role name mapping for readability
        role_name_map = {
            ROLE_CLIENT: 'Client',
            ROLE_STYLIST: 'Stylist',
            ROLE_ADMIN: 'Administrator'
        }
        
        # Prepare audit details
        audit_details = {
            'old_values': old_values,
            'new_values': {
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'phone': user.phone,
                'role': user.role,
                'role_name': role_name_map.get(user.role, 'Unknown'),
                'is_active': user.is_active
            },
            'password_changed': password_changed
        }
        
        db.session.commit()
        
        # Log the user update
        log_audit('update', 'user', entity_id=user.id, details=audit_details)
        
        flash(f'User {user.email} updated successfully.', 'success')
        return redirect(url_for('admin.users'))
    
    return render_template('admin/update_user.html', form=form, user=user)

@admin_bp.route('/services')
@login_required
@admin_required
def services():
    """List all salon services"""
    services_list = Service.query.all()
    return render_template('admin/services.html', services=services_list)

@admin_bp.route('/services/create', methods=['GET', 'POST'])
@login_required
@admin_required
def create_service():
    """Create a new salon service"""
    form = ServiceForm()
    
    if form.validate_on_submit():
        service = Service(
            name=form.name.data,
            description=form.description.data,
            price=form.price.data,
            duration_minutes=form.duration_minutes.data,
            is_active=form.is_active.data
        )
        
        db.session.add(service)
        db.session.commit()
        
        # Log service creation
        audit_details = {
            'name': service.name,
            'description': service.description,
            'price': float(service.price),
            'duration_minutes': service.duration_minutes,
            'is_active': service.is_active
        }
        
        log_audit('create', 'service', entity_id=service.id, details=audit_details)
        
        flash(f'Service {service.name} created successfully.', 'success')
        return redirect(url_for('admin.services'))
    
    return render_template('admin/create_service.html', form=form)

@admin_bp.route('/services/update/<int:service_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def update_service(service_id):
    """Update an existing service"""
    service = Service.query.get_or_404(service_id)
    form = ServiceForm(obj=service)
    
    if form.validate_on_submit():
        # Store old values for audit log
        old_values = {
            'name': service.name,
            'description': service.description,
            'price': float(service.price),
            'duration_minutes': service.duration_minutes,
            'is_active': service.is_active
        }
        
        # Update service data
        service.name = form.name.data
        service.description = form.description.data
        service.price = form.price.data
        service.duration_minutes = form.duration_minutes.data
        service.is_active = form.is_active.data
        
        # Prepare audit details
        audit_details = {
            'old_values': old_values,
            'new_values': {
                'name': service.name,
                'description': service.description,
                'price': float(service.price),
                'duration_minutes': service.duration_minutes,
                'is_active': service.is_active
            }
        }
        
        db.session.commit()
        
        # Log the service update
        log_audit('update', 'service', entity_id=service.id, details=audit_details)
        
        flash(f'Service {service.name} updated successfully.', 'success')
        return redirect(url_for('admin.services'))
    
    return render_template('admin/update_service.html', form=form, service=service)

@admin_bp.route('/business-hours', methods=['GET', 'POST'])
@login_required
@admin_required
def business_hours():
    """Manage salon business hours"""
    # Create default business hours if they don't exist
    days = [MONDAY, TUESDAY, WEDNESDAY, THURSDAY, FRIDAY, SATURDAY, SUNDAY]
    existing_days = [hour.day_of_week for hour in BusinessHours.query.all()]
    
    for day in days:
        if day not in existing_days:
            default_hours = BusinessHours(
                day_of_week=day,
                open_time=time(9, 0),  # 9:00 AM
                close_time=time(17, 0),  # 5:00 PM
                is_closed=(day in [SATURDAY, SUNDAY])  # Closed on weekends by default
            )
            db.session.add(default_hours)
    
    db.session.commit()
    
    # Handle form submission for updating hours
    if request.method == 'POST':
        # Store old values for audit log
        day_names = {
            MONDAY: 'Monday',
            TUESDAY: 'Tuesday',
            WEDNESDAY: 'Wednesday',
            THURSDAY: 'Thursday',
            FRIDAY: 'Friday',
            SATURDAY: 'Saturday',
            SUNDAY: 'Sunday'
        }
        
        old_hours = {}
        for day in days:
            hour = BusinessHours.query.filter_by(day_of_week=day).first()
            old_hours[day] = {
                'day_name': day_names[day],
                'is_closed': hour.is_closed,
                'open_time': hour.open_time.strftime('%H:%M') if hour.open_time else None,
                'close_time': hour.close_time.strftime('%H:%M') if hour.close_time else None
            }
        
        # Update hours
        changes_made = False
        new_hours = {}
        
        for day in days:
            hour = BusinessHours.query.filter_by(day_of_week=day).first()
            is_closed = request.form.get(f'is_closed_{day}') == 'on'
            
            # Track if this day's hours changed
            day_changed = hour.is_closed != is_closed
            
            if is_closed:
                hour.is_closed = True
            else:
                hour.is_closed = False
                open_time_str = request.form.get(f'open_time_{day}')
                close_time_str = request.form.get(f'close_time_{day}')
                
                try:
                    new_open_time = datetime.strptime(open_time_str, '%H:%M').time()
                    new_close_time = datetime.strptime(close_time_str, '%H:%M').time()
                    
                    # Check if times have changed
                    if hour.open_time != new_open_time or hour.close_time != new_close_time:
                        day_changed = True
                    
                    hour.open_time = new_open_time
                    hour.close_time = new_close_time
                except ValueError:
                    flash('Invalid time format. Use HH:MM.', 'danger')
                    return redirect(url_for('admin.business_hours'))
            
            # Record if any changes were made
            if day_changed:
                changes_made = True
            
            # Store new values for audit log
            new_hours[day] = {
                'day_name': day_names[day],
                'is_closed': hour.is_closed,
                'open_time': hour.open_time.strftime('%H:%M') if hour.open_time else None,
                'close_time': hour.close_time.strftime('%H:%M') if hour.close_time else None
            }
        
        db.session.commit()
        
        # Log the business hours update if changes were made
        if changes_made:
            audit_details = {
                'old_hours': old_hours,
                'new_hours': new_hours
            }
            log_audit('update', 'business_hours', entity_id=None, details=audit_details)
        
        flash('Business hours updated successfully.', 'success')
        return redirect(url_for('admin.business_hours'))
    
    # Get all business hours for display
    hours = BusinessHours.query.order_by(BusinessHours.day_of_week).all()
    
    # Map day numbers to names for display
    day_names = {
        MONDAY: 'Monday',
        TUESDAY: 'Tuesday',
        WEDNESDAY: 'Wednesday',
        THURSDAY: 'Thursday',
        FRIDAY: 'Friday',
        SATURDAY: 'Saturday',
        SUNDAY: 'Sunday'
    }
    
    return render_template('admin/business_hours.html', hours=hours, day_names=day_names)

@admin_bp.route('/holidays', methods=['GET', 'POST'])
@login_required
@admin_required
def holidays():
    """Manage salon holidays"""
    form = HolidayForm()
    
    if form.validate_on_submit():
        # Create a blocked time entry for all stylists
        stylists = User.query.filter_by(role=ROLE_STYLIST).all()
        
        # Prepare audit details
        holiday_date = form.date.data
        holiday_description = form.description.data
        
        audit_details = {
            'date': holiday_date.strftime('%Y-%m-%d'),
            'description': holiday_description,
            'affected_stylists': []
        }
        
        for stylist in stylists:
            holiday = BlockedTime(
                stylist_id=stylist.id,
                start_time=datetime.combine(form.date.data, time(0, 0)),
                end_time=datetime.combine(form.date.data, time(23, 59)),
                reason=form.description.data,
                is_holiday=True
            )
            db.session.add(holiday)
            
            # Record affected stylists for audit log
            audit_details['affected_stylists'].append({
                'id': stylist.id,
                'name': f"{stylist.first_name} {stylist.last_name}",
                'email': stylist.email
            })
        
        db.session.commit()
        
        # Log the holiday creation
        log_audit('create', 'holiday', entity_id=None, details=audit_details)
        
        flash('Holiday added successfully.', 'success')
        return redirect(url_for('admin.holidays'))
    
    # Get all holidays for display
    holidays_list = BlockedTime.query.filter_by(is_holiday=True).distinct(BlockedTime.start_time, BlockedTime.reason).all()
    
    return render_template('admin/holidays.html', form=form, holidays=holidays_list)

@admin_bp.route('/appointments')
@login_required
@admin_required
def appointments():
    """View all salon appointments"""
    status_filter = request.args.get('status', 'all')
    date_from = request.args.get('date_from', datetime.utcnow().strftime('%Y-%m-%d'))
    
    # Convert date string to datetime
    try:
        date_from = datetime.strptime(date_from, '%Y-%m-%d')
    except ValueError:
        date_from = datetime.utcnow()
    
    # Start with base query
    query = Appointment.query
    
    # Apply filters
    if status_filter != 'all':
        query = query.filter_by(status=status_filter)
    
    query = query.filter(Appointment.start_time >= date_from)
    
    # Get final results ordered by date
    appointments_list = query.order_by(Appointment.start_time).all()
    
    return render_template(
        'admin/appointments.html',
        appointments=appointments_list,
        status_filter=status_filter,
        date_from=date_from.strftime('%Y-%m-%d')
    )

@admin_bp.route('/audit-logs')
@login_required
@admin_required
def audit_logs():
    """View system audit logs with filtering options"""
    # Get filter parameters
    action_filter = request.args.get('action', '')
    entity_type_filter = request.args.get('entity_type', '')
    user_id_filter = request.args.get('user_id', '')
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    
    # Base query
    query = AuditLog.query
    
    # Apply filters
    if action_filter:
        query = query.filter(AuditLog.action == action_filter)
    
    if entity_type_filter:
        query = query.filter(AuditLog.entity_type == entity_type_filter)
    
    if user_id_filter and user_id_filter.isdigit():
        query = query.filter(AuditLog.user_id == int(user_id_filter))
    
    if date_from:
        try:
            date_from_obj = datetime.strptime(date_from, '%Y-%m-%d')
            query = query.filter(AuditLog.timestamp >= date_from_obj)
        except ValueError:
            flash('Invalid from date format. Use YYYY-MM-DD.', 'warning')
    
    if date_to:
        try:
            date_to_obj = datetime.strptime(date_to, '%Y-%m-%d')
            # Add one day to include the entire end date
            date_to_obj = date_to_obj + timedelta(days=1)
            query = query.filter(AuditLog.timestamp < date_to_obj)
        except ValueError:
            flash('Invalid to date format. Use YYYY-MM-DD.', 'warning')
    
    # Order by timestamp (newest first)
    query = query.order_by(AuditLog.timestamp.desc())
    
    # Pagination
    page = request.args.get('page', 1, type=int)
    per_page = 50  # Number of logs per page
    audit_logs_pagination = query.paginate(page=page, per_page=per_page)
    
    # Get distinct actions and entity types for filter dropdowns
    actions = db.session.query(AuditLog.action).distinct().all()
    entity_types = db.session.query(AuditLog.entity_type).distinct().all()
    
    # Get all admin users for the user filter dropdown
    users = User.query.all()
    
    return render_template(
        'admin/audit_logs.html',
        audit_logs=audit_logs_pagination.items,
        pagination=audit_logs_pagination,
        actions=[action[0] for action in actions],
        entity_types=[entity_type[0] for entity_type in entity_types],
        users=users,
        filters={
            'action': action_filter,
            'entity_type': entity_type_filter,
            'user_id': user_id_filter,
            'date_from': date_from,
            'date_to': date_to
        }
    )