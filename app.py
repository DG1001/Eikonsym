import os
import secrets
import imaplib
import email
import sqlite3
from email.header import decode_header
import base64
from werkzeug.utils import secure_filename # Import secure_filename
from flask import Flask, render_template, request, redirect, url_for, flash, session, g
from datetime import datetime
import re
import warnings # Import warnings

app = Flask(__name__)

# Load secret key from environment or generate a default (warn if default is used outside debug)
SECRET_KEY = os.environ.get('SECRET_KEY')
if not SECRET_KEY:
    SECRET_KEY = secrets.token_hex(16)
    if os.environ.get('FLASK_ENV') == 'production' or not os.environ.get('FLASK_DEBUG'):
         warnings.warn("WARNING: SECRET_KEY not set in environment. Using temporary key. Set a strong SECRET_KEY environment variable for production.", UserWarning)

app.config['SECRET_KEY'] = SECRET_KEY
app.config['DATABASE'] = 'events.db'
app.config['UPLOAD_FOLDER'] = 'static/uploads'

# Ensure upload directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Gmail credentials
GMAIL_USER = os.environ.get('GMAIL_USER', 'eikonsym@gmail.com')
GMAIL_PASSWORD = os.environ.get('GMAIL_APP_PASSWORD', '')
GMAIL_PREFIX = 'eikonsym+'
GMAIL_DOMAIN = 'gmail.com'

# Admin passwords
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'eikonsym')
ADMIN_MASTER_PASSWORD = os.environ.get('ADMIN_MASTER_PASSWORD', 'eikonsym_master')

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(app.config['DATABASE'])
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def init_db():
    with app.app_context():
        db = get_db()
        with app.open_resource('schema.sql', mode='r') as f:
            db.cursor().executescript(f.read())
        db.commit()

# Create tables if they don't exist
def create_tables():
    conn = sqlite3.connect(app.config['DATABASE'])
    conn.execute('''
    CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        description TEXT,
        key TEXT UNIQUE NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    conn.execute('''
    CREATE TABLE IF NOT EXISTS images (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        filename TEXT NOT NULL,
        original_filename TEXT,
        sender TEXT,
        received_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        event_id INTEGER,
        FOREIGN KEY (event_id) REFERENCES events (id)
    )
    ''')
    conn.commit()
    conn.close()

# Create tables on startup
with app.app_context():
    create_tables()

class Event:
    @staticmethod
    def get_by_key(key):
        db = get_db()
        event = db.execute('SELECT * FROM events WHERE key = ?', (key,)).fetchone()
        return event
    
    @staticmethod
    def get_by_id(id):
        db = get_db()
        event = db.execute('SELECT * FROM events WHERE id = ?', (id,)).fetchone()
        return event
    
    @staticmethod
    def get_all():
        db = get_db()
        events = db.execute('SELECT * FROM events ORDER BY created_at DESC').fetchall()
        return events
    
    @staticmethod
    def create(name, description, key):
        db = get_db()
        db.execute(
            'INSERT INTO events (name, description, key) VALUES (?, ?, ?)',
            (name, description, key)
        )
        db.commit()
        return Event.get_by_key(key)
    
    @staticmethod
    def delete(event_id):
        db = get_db()
        # First delete all images associated with this event
        images = Image.get_by_event_id(event_id)
        for image in images:
            Image.delete(image['id'])
        
        # Then delete the event
        db.execute('DELETE FROM events WHERE id = ?', (event_id,))
        db.commit()
        return True
    
    @staticmethod
    def get_email(key):
        return f"{GMAIL_PREFIX}{key}@{GMAIL_DOMAIN}"

class Image:
    @staticmethod
    def get_by_event_id(event_id):
        db = get_db()
        images = db.execute(
            'SELECT * FROM images WHERE event_id = ? ORDER BY received_at DESC',
            (event_id,)
        ).fetchall()
        return images
    
    @staticmethod
    def get_by_id(id):
        db = get_db()
        image = db.execute('SELECT * FROM images WHERE id = ?', (id,)).fetchone()
        return image
    
    @staticmethod
    def create(filename, original_filename, sender, event_id):
        db = get_db()
        db.execute(
            'INSERT INTO images (filename, original_filename, sender, event_id) VALUES (?, ?, ?, ?)',
            (filename, original_filename, sender, event_id)
        )
        db.commit()
    
    @staticmethod
    def delete(image_id):
        db = get_db()
        # Get the image filename first
        image = Image.get_by_id(image_id)
        if image:
            # Delete the file from disk
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], image['filename'])
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
            except Exception as e:
                print(f"Error deleting file: {e}")
            
            # Delete from database
            db.execute('DELETE FROM images WHERE id = ?', (image_id,))
            db.commit()
            return True
        return False

def generate_event_key():
    """Generate a unique event key"""
    while True:
        key = secrets.token_urlsafe(8)
        # Make sure it's alphanumeric and doesn't contain special characters
        key = re.sub(r'[^a-zA-Z0-9]', '', key)[:12]
        db = get_db()
        existing = db.execute('SELECT id FROM events WHERE key = ?', (key,)).fetchone()
        if not existing:
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
        
        event = Event.get_by_key(event_key)
        if not event:
            return False
        
        processed_emails = 0
        for msg_id in message_ids:
            status, msg_data = mail.fetch(msg_id, '(RFC822)')
            if status != 'OK':
                continue
                
            raw_email = msg_data[0][1]
            msg = email.message_from_bytes(raw_email)
            
            # Get sender
            sender = msg.get("From", "Unknown")
            
            # Track if this email had any images
            had_images = False
            
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
                    # Sanitize the original filename before using it
                    safe_original_filename = secure_filename(filename)
                    if not safe_original_filename: # Handle empty filename after sanitization
                        safe_original_filename = "unnamed_upload"

                    # Create a unique filename based on the sanitized original
                    unique_filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{secrets.token_hex(4)}_{safe_original_filename}"
                    file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)

                    with open(file_path, 'wb') as f:
                        f.write(data)
                    
                    # Save to database
                    Image.create(
                        filename=unique_filename,
                        original_filename=filename,
                        sender=sender,
                        event_id=event['id']
                    )
                    
                    had_images = True
            
            # Mark the email for deletion if it had images
            if had_images:
                mail.store(msg_id, '+FLAGS', '\\Deleted')
                processed_emails += 1
        
        # Permanently remove emails marked for deletion
        if processed_emails > 0:
            mail.expunge()
            flash(f"Successfully processed and deleted {processed_emails} emails", "success")
        
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
        password = request.form.get('password')
        
        if not name:
            flash('Event name is required', 'error')
            return redirect(url_for('create_event'))
        
        if not password or password != ADMIN_PASSWORD:
            flash('Invalid admin password', 'error')
            return redirect(url_for('create_event'))
        
        event_key = generate_event_key()
        Event.create(name=name, description=description, key=event_key)
        
        flash(f'Event created! Share this email address: {Event.get_email(event_key)}', 'success')
        return redirect(url_for('view_event', event_key=event_key))
    
    return render_template('create_event.html')

@app.route('/event/<event_key>')
def view_event(event_key):
    event = Event.get_by_key(event_key)
    if not event:
        flash('Event not found', 'error')
        return redirect(url_for('index'))
    
    # Check for new emails
    check_emails_for_event(event_key)
    
    # Get all images for this event
    images = Image.get_by_event_id(event['id'])
    
    # Add email property to event dictionary
    event_with_email = dict(event)
    event_with_email['email'] = Event.get_email(event_key)
    
    return render_template('view_event.html', event=event_with_email, images=images)

@app.route('/find_event', methods=['GET', 'POST'])
def find_event():
    if request.method == 'POST':
        email = request.form.get('email')
        
        if not email:
            flash('Email is required', 'error')
            return redirect(url_for('find_event'))

        # Debug info - Commented out to avoid potential info disclosure
        # flash(f'Searching for event with email: {email}', 'info')

        # Extract event key from email
        match = re.search(rf'{GMAIL_PREFIX}([a-zA-Z0-9]+)@{GMAIL_DOMAIN}', email)
        if not match:
            # Try a more lenient pattern as fallback
            match = re.search(r'eikonsym\+([a-zA-Z0-9]+)@gmail\.com', email)
            if not match:
                flash('Invalid event email format. Please enter the complete email address (e.g., eikonsym+abc123@gmail.com)', 'error')
                return redirect(url_for('find_event'))
        
        event_key = match.group(1)
        event = Event.get_by_key(event_key)
        
        if not event:
            flash(f'Event not found for key: {event_key}', 'error')
            return redirect(url_for('find_event'))
        
        return redirect(url_for('view_event', event_key=event_key))
    
    return render_template('find_event.html')

@app.route('/admin', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        password = request.form.get('password')
        
        if not password or password != ADMIN_MASTER_PASSWORD:
            flash('Invalid admin password', 'error')
            return redirect(url_for('admin_login'))
        
        session['admin_authenticated'] = True
        return redirect(url_for('admin_dashboard'))
    
    return render_template('admin_login.html')

@app.route('/admin/dashboard', methods=['GET', 'POST'])
def admin_dashboard():
    if not session.get('admin_authenticated'):
        flash('Please login as admin first', 'error')
        return redirect(url_for('admin_login'))
    
    events = Event.get_all()
    return render_template('admin_dashboard.html', events=events)

@app.route('/admin/refresh_emails', methods=['POST'])
def admin_refresh_emails():
    if not session.get('admin_authenticated'):
        flash('Please login as admin first', 'error')
        return redirect(url_for('admin_login'))
    events = Event.get_all()
    refreshed = 0
    for event in events:
        if check_emails_for_event(event['key']):
            refreshed += 1
    flash(f"Checked emails for {len(events)} events.", "success")
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/event/refresh/<int:event_id>', methods=['POST'])
def admin_refresh_single_event(event_id):
    if not session.get('admin_authenticated'):
        flash('Please login as admin first', 'error')
        return redirect(url_for('admin_login'))
    event = Event.get_by_id(event_id)
    if not event:
        flash('Event not found', 'error')
        return redirect(url_for('admin_dashboard'))
    if check_emails_for_event(event['key']):
        flash(f"Checked emails for event '{event['name']}'.", "success")
    else:
        flash(f"Failed to check emails for event '{event['name']}'.", "error")
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/event/<int:event_id>')
def admin_view_event(event_id):
    if not session.get('admin_authenticated'):
        flash('Please login as admin first', 'error')
        return redirect(url_for('admin_login'))
    
    event = Event.get_by_id(event_id)
    if not event:
        flash('Event not found', 'error')
        return redirect(url_for('admin_dashboard'))
    
    images = Image.get_by_event_id(event_id)
    
    # Add email property to event dictionary
    event_with_email = dict(event)
    event_with_email['email'] = Event.get_email(event['key'])
    
    return render_template('admin_view_event.html', event=event_with_email, images=images)

@app.route('/admin/event/delete/<int:event_id>', methods=['POST'])
def admin_delete_event(event_id):
    if not session.get('admin_authenticated'):
        flash('Please login as admin first', 'error')
        return redirect(url_for('admin_login'))
    
    event = Event.get_by_id(event_id)
    if not event:
        flash('Event not found', 'error')
        return redirect(url_for('admin_dashboard'))
    
    Event.delete(event_id)
    flash(f'Event "{event["name"]}" has been deleted', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/image/delete/<int:image_id>', methods=['POST'])
def admin_delete_image(image_id):
    if not session.get('admin_authenticated'):
        flash('Please login as admin first', 'error')
        return redirect(url_for('admin_login'))
    
    image = Image.get_by_id(image_id)
    if not image:
        flash('Image not found', 'error')
        return redirect(url_for('admin_dashboard'))
    
    event_id = image['event_id']
    Image.delete(image_id)
    flash('Image has been deleted', 'success')
    return redirect(url_for('admin_view_event', event_id=event_id))

if __name__ == '__main__':
    # Bind to 0.0.0.0 to be accessible externally, e.g., within a container
    # Use debug=False in production environments or when running with Gunicorn
    app.run(host='0.0.0.0', debug=True)
