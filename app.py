import os
import secrets
import imaplib
import email
from email.header import decode_header
import base64
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import re

app = Flask(__name__)
app.config['SECRET_KEY'] = secrets.token_hex(16)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///events.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'static/uploads'

# Ensure upload directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Gmail credentials
GMAIL_USER = os.environ.get('GMAIL_USER', 'eikonsym@gmail.com')
GMAIL_PASSWORD = os.environ.get('GMAIL_APP_PASSWORD', '')
GMAIL_PREFIX = 'eikonsym+'
GMAIL_DOMAIN = 'gmail.com'

db = SQLAlchemy(app)

class Event(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    key = db.Column(db.String(16), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    images = db.relationship('Image', backref='event', lazy=True)

    @property
    def email(self):
        return f"{GMAIL_PREFIX}{self.key}@{GMAIL_DOMAIN}"

class Image(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    original_filename = db.Column(db.String(255))
    sender = db.Column(db.String(255))
    received_at = db.Column(db.DateTime, default=datetime.utcnow)
    event_id = db.Column(db.Integer, db.ForeignKey('event.id'), nullable=False)

with app.app_context():
    db.create_all()

def generate_event_key():
    """Generate a unique event key"""
    while True:
        key = secrets.token_urlsafe(8)
        # Make sure it's alphanumeric and doesn't contain special characters
        key = re.sub(r'[^a-zA-Z0-9]', '', key)[:12]
        if not Event.query.filter_by(key=key).first():
            return key

def check_emails_for_event(event_key):
    """Check emails for a specific event and download images"""
    if not GMAIL_PASSWORD:
        flash("Gmail app password not configured", "error")
        return False
    
    try:
        # Connect to Gmail
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(GMAIL_USER, GMAIL_PASSWORD)
        mail.select("inbox")
        
        # Search for emails sent to the event email
        event_email = f"{GMAIL_PREFIX}{event_key}@{GMAIL_DOMAIN}"
        search_criteria = f'TO "{event_email}"'
        status, messages = mail.search(None, search_criteria)
        
        if status != 'OK':
            flash("Failed to search emails", "error")
            return False
        
        message_ids = messages[0].split()
        if not message_ids:
            return True  # No new emails
        
        event = Event.query.filter_by(key=event_key).first()
        if not event:
            return False
        
        for msg_id in message_ids:
            status, msg_data = mail.fetch(msg_id, '(RFC822)')
            if status != 'OK':
                continue
                
            raw_email = msg_data[0][1]
            msg = email.message_from_bytes(raw_email)
            
            # Get sender
            sender = msg.get("From", "Unknown")
            
            # Process attachments
            for part in msg.walk():
                if part.get_content_maintype() == 'multipart':
                    continue
                
                if part.get('Content-Disposition') is None:
                    continue
                
                filename = part.get_filename()
                if not filename:
                    continue
                
                # Check if it's an image
                if not any(filename.lower().endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.gif']):
                    continue
                
                # Decode filename if needed
                if decode_header(filename)[0][1] is not None:
                    filename = decode_header(filename)[0][0].decode(decode_header(filename)[0][1])
                
                # Save the image
                data = part.get_payload(decode=True)
                if data:
                    # Create a unique filename
                    unique_filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{secrets.token_hex(4)}_{filename}"
                    file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
                    
                    with open(file_path, 'wb') as f:
                        f.write(data)
                    
                    # Save to database
                    new_image = Image(
                        filename=unique_filename,
                        original_filename=filename,
                        sender=sender,
                        event_id=event.id
                    )
                    db.session.add(new_image)
        
        db.session.commit()
        return True
    
    except Exception as e:
        flash(f"Error checking emails: {str(e)}", "error")
        return False
    finally:
        try:
            mail.close()
            mail.logout()
        except:
            pass

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/create_event', methods=['GET', 'POST'])
def create_event():
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        
        if not name:
            flash('Event name is required', 'error')
            return redirect(url_for('create_event'))
        
        event_key = generate_event_key()
        new_event = Event(name=name, description=description, key=event_key)
        
        db.session.add(new_event)
        db.session.commit()
        
        flash(f'Event created! Share this email address: {new_event.email}', 'success')
        return redirect(url_for('view_event', event_key=event_key))
    
    return render_template('create_event.html')

@app.route('/event/<event_key>')
def view_event(event_key):
    event = Event.query.filter_by(key=event_key).first_or_404()
    
    # Check for new emails
    check_emails_for_event(event_key)
    
    # Get all images for this event
    images = Image.query.filter_by(event_id=event.id).order_by(Image.received_at.desc()).all()
    
    return render_template('view_event.html', event=event, images=images)

@app.route('/find_event', methods=['GET', 'POST'])
def find_event():
    if request.method == 'POST':
        email = request.form.get('email')
        
        if not email:
            flash('Email is required', 'error')
            return redirect(url_for('find_event'))
        
        # Extract event key from email
        match = re.search(f'{GMAIL_PREFIX}([a-zA-Z0-9]+)@{GMAIL_DOMAIN}', email)
        if not match:
            flash('Invalid event email format', 'error')
            return redirect(url_for('find_event'))
        
        event_key = match.group(1)
        event = Event.query.filter_by(key=event_key).first()
        
        if not event:
            flash('Event not found', 'error')
            return redirect(url_for('find_event'))
        
        return redirect(url_for('view_event', event_key=event_key))
    
    return render_template('find_event.html')

if __name__ == '__main__':
    app.run(debug=True)
