from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from app import db
from app.models.user import User, ROLE_CLIENT
from app.auth.forms import LoginForm, RegistrationForm, PasswordResetForm, UpdateProfileForm
from app.utils.audit import log_audit, audit_log_decorator

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    
    form = RegistrationForm()
    
    if form.validate_on_submit():
        user = User(
            email=form.email.data,
            first_name=form.first_name.data,
            last_name=form.last_name.data,
            password=form.password.data,
            role=ROLE_CLIENT,
            phone=form.phone.data
        )
        
        db.session.add(user)
        db.session.commit()
        
        # Log the registration in audit trail
        audit_details = {
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'role': user.role,
            'phone': user.phone,
            'ip_address': request.remote_addr
        }
        log_audit('create', 'user', user.id, audit_details)
        
        flash('Registration successful! You can now login with your credentials.', 'success')
        return redirect(url_for('auth.login'))
    
    return render_template('auth/register.html', form=form)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    
    form = LoginForm()
    
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        
        if user and user.check_password(form.password.data):
            if not user.is_active:
                # Log failed login due to inactive account
                audit_details = {
                    'email': form.email.data,
                    'reason': 'account_inactive',
                    'ip_address': request.remote_addr
                }
                log_audit('attempt', 'login', user.id, audit_details, success=False)
                
                flash('Your account is currently deactivated. Please contact support.', 'danger')
                return redirect(url_for('auth.login'))
                
            login_user(user, remember=form.remember_me.data)
            
            # Log successful login
            audit_details = {
                'email': user.email,
                'ip_address': request.remote_addr,
                'user_agent': request.user_agent.string,
                'remember_me': form.remember_me.data
            }
            log_audit('perform', 'login', user.id, audit_details)
            
            next_page = request.args.get('next')
            if not next_page or not next_page.startswith('/'):
                if user.is_admin():
                    next_page = url_for('admin.dashboard')
                elif user.is_stylist():
                    next_page = url_for('stylist.dashboard')
                else:
                    next_page = url_for('client.dashboard')
            
            flash('Login successful!', 'success')
            return redirect(next_page)
        else:
            # Log failed login attempt
            audit_details = {
                'email': form.email.data,
                'reason': 'invalid_credentials',
                'ip_address': request.remote_addr
            }
            user_id = user.id if user else None
            log_audit('attempt', 'login', user_id, audit_details, success=False)
            
            flash('Invalid email or password.', 'danger')
    
    return render_template('auth/login.html', form=form)

@auth_bp.route('/logout')
@login_required
def logout():
    # Log the logout action
    audit_details = {
        'email': current_user.email,
        'ip_address': request.remote_addr
    }
    user_id = current_user.id
    log_audit('perform', 'logout', user_id, audit_details)
    
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('main.index'))

@auth_bp.route('/reset-password', methods=['GET', 'POST'])
def reset_password():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    
    form = PasswordResetForm()
    
    if form.validate_on_submit():
        # Simple password reset for development - in production this would be more secure
        user = User.query.filter_by(email=form.email.data).first()
        if user:
            user.set_password(form.password.data)
            db.session.commit()
            
            # Log the password reset
            audit_details = {
                'email': user.email,
                'ip_address': request.remote_addr,
                'reset_method': 'form_reset'  # In production, this might be 'email_link' or other methods
            }
            log_audit('update', 'password_reset', user.id, audit_details)
            
            flash('Your password has been reset. Please login with your new password.', 'success')
            return redirect(url_for('auth.login'))
        else:
            # Log failed password reset attempt
            audit_details = {
                'email': form.email.data,
                'ip_address': request.remote_addr,
                'reason': 'email_not_found'
            }
            log_audit('attempt', 'password_reset', None, audit_details, success=False)
            
            flash('Email address not found in our system.', 'danger')
    
    return render_template('auth/reset_password.html', form=form)

@auth_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    form = UpdateProfileForm(obj=current_user)
    
    if form.validate_on_submit():
        # Track old values for audit log
        old_values = {
            'first_name': current_user.first_name,
            'last_name': current_user.last_name,
            'phone': current_user.phone
        }
        
        # Update user data
        current_user.first_name = form.first_name.data
        current_user.last_name = form.last_name.data
        current_user.phone = form.phone.data
        
        db.session.commit()
        
        # Log the profile update
        audit_details = {
            'email': current_user.email,
            'changes': {
                'first_name': {'old': old_values['first_name'], 'new': current_user.first_name},
                'last_name': {'old': old_values['last_name'], 'new': current_user.last_name},
                'phone': {'old': old_values['phone'], 'new': current_user.phone}
            },
            'ip_address': request.remote_addr
        }
        log_audit('update', 'user_profile', current_user.id, audit_details)
        
        flash('Your profile has been updated.', 'success')
        return redirect(url_for('auth.profile'))
        
    return render_template('auth/profile.html', form=form)

@auth_bp.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    form = PasswordResetForm()
    form.email.data = current_user.email  # Pre-fill the email field
    
    if form.validate_on_submit():
        current_user.set_password(form.password.data)
        db.session.commit()
        
        # Log the password change
        audit_details = {
            'email': current_user.email,
            'ip_address': request.remote_addr,
            'change_method': 'user_initiated'
        }
        log_audit('update', 'password_change', current_user.id, audit_details)
        
        flash('Your password has been updated.', 'success')
        return redirect(url_for('auth.profile'))
        
    return render_template('auth/reset_password.html', form=form)