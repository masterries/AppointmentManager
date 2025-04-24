from flask import Blueprint, render_template, redirect, url_for
from app.models.user import User
from app.models.service import Service
from flask_login import current_user

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    """Landing page for the salon website"""
    # Get a few stylists to display on the homepage
    stylists = User.query.filter_by(role='stylist').limit(4).all()
    # Get all active services
    services = Service.query.filter_by(is_active=True).all()
    return render_template('main/index.html', 
                           stylists=stylists, 
                           services=services)

@main_bp.route('/services')
def services():
    """Page displaying all salon services"""
    services = Service.query.filter_by(is_active=True).all()
    return render_template('main/services.html', services=services)

@main_bp.route('/stylists')
def stylists():
    """Page displaying all salon stylists"""
    stylists = User.query.filter_by(role='stylist').all()
    return render_template('main/stylists.html', stylists=stylists)

@main_bp.route('/about')
def about():
    """About the salon page"""
    return render_template('main/about.html')

@main_bp.route('/contact')
def contact():
    """Contact information page"""
    return render_template('main/contact.html')

@main_bp.route('/dashboard')
def dashboard():
    """Redirect to appropriate dashboard based on user role"""
    if not current_user.is_authenticated:
        return redirect(url_for('auth.login'))
    
    if current_user.is_admin():
        return redirect(url_for('admin.dashboard'))
    elif current_user.is_stylist():
        return redirect(url_for('stylist.dashboard'))
    else:
        return redirect(url_for('client.dashboard'))