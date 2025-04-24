from flask import request, current_app
from flask_login import current_user
from app.models.audit import AuditLog
from app import db
import json
from functools import wraps
from decimal import Decimal

def log_audit(action, entity_type, entity_id=None, details=None):
    """
    Log an audit entry
    
    Parameters:
    - action: The action performed (e.g., 'create', 'update', 'delete')
    - entity_type: The type of entity affected (e.g., 'user', 'appointment')
    - entity_id: ID of the affected entity (optional)
    - details: Additional details about the action (optional)
    """
    try:
        # Get user ID if logged in
        user_id = current_user.id if current_user and current_user.is_authenticated else None
        
        # Get IP address
        ip_address = request.remote_addr
        
        # Create audit log entry
        audit_entry = AuditLog(
            user_id=user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            details=details,
            ip_address=ip_address
        )
        
        db.session.add(audit_entry)
        db.session.commit()
        
        return True
    except Exception as e:
        current_app.logger.error(f"Failed to log audit entry: {e}")
        return False

def audit_log_decorator(action, entity_type, get_entity_id=None, get_details=None):
    """
    Decorator for automatically logging audit entries

    Parameters:
    - action: The action performed (e.g., 'create', 'update', 'delete')
    - entity_type: The type of entity affected (e.g., 'user', 'appointment')
    - get_entity_id: Function to extract entity_id from function args/kwargs/return value
                    Should accept (result, *args, **kwargs) parameters
    - get_details: Function to extract details from function args/kwargs/return value
                  Should accept (result, *args, **kwargs) parameters
    
    Example usage:
    
    @audit_log_decorator(
        action='create', 
        entity_type='appointment',
        get_entity_id=lambda result, *args, **kwargs: result.id,
        get_details=lambda result, *args, **kwargs: {'client_id': kwargs.get('client_id')}
    )
    def create_appointment(client_id, ...):
        # Function implementation
        return new_appointment
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                # Execute the original function
                result = func(*args, **kwargs)
                
                # Extract entity_id if provided
                entity_id = None
                if get_entity_id:
                    try:
                        entity_id = get_entity_id(result, *args, **kwargs)
                    except Exception as e:
                        current_app.logger.error(f"Error extracting entity_id for audit log: {e}")
                
                # Extract details if provided
                details = None
                if get_details:
                    try:
                        details = get_details(result, *args, **kwargs)
                    except Exception as e:
                        current_app.logger.error(f"Error extracting details for audit log: {e}")
                
                # Log the audit entry
                log_audit(action, entity_type, entity_id, details)
                
                return result
            except Exception as e:
                # Still try to log the failure
                log_audit(
                    action=f"{action}_failed",
                    entity_type=entity_type,
                    details={"error": str(e)}
                )
                # Re-raise the exception
                raise
        return wrapper
    return decorator