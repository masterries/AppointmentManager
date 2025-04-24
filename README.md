# Hair Salon Booking System

A full-featured web application for managing a hair salon business, built with Flask, SQLAlchemy, and Tailwind CSS.

## Overview

This application provides a comprehensive solution for hair salons to manage appointments, staff, clients, and services. It features role-based access control (admin, stylist, client) with different dashboards and functionalities for each role.

## Features

- **User Authentication**
  - Registration and login system
  - Role-based authorization (admin, stylist, client)
  - Password reset functionality
  - Profile management

- **Client Features**
  - Book appointments with preferred stylists
  - View and manage upcoming appointments
  - Browse stylist profiles and services

- **Stylist Features**
  - Manage availability and working hours
  - View upcoming appointments
  - Track client information and appointment history
  - Add client notes

- **Admin Features**
  - User management
  - Service management
  - Business hours configuration
  - Analytics dashboard
  - Audit logs for security and compliance

- **Technical Features**
  - Responsive design with Tailwind CSS
  - Database-backed with SQLAlchemy ORM
  - HTMX for enhanced interactivity
  - Security features and audit logging

## Installation & Setup

1. Clone the repository
```
git clone https://github.com/yourusername/hair-salon-booking.git
cd hair-salon-booking
```

2. Create and activate a virtual environment
```
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

3. Install dependencies
```
pip install -r requirements.txt
```

4. Set environment variables
```
export FLASK_APP=run.py
export FLASK_ENV=development
```

5. Initialize the database
```
flask db init
flask db migrate
flask db upgrade
```

6. Run the application
```
flask run
```

## Technologies Used

- Flask (Python web framework)
- SQLAlchemy (ORM)
- Tailwind CSS (Utility-first CSS framework)
- HTMX (Dynamic HTML without JavaScript)
- Alpine.js (Minimal JS framework)
- SQLite (Development database)

## License

MIT License

