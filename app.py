import os
import secrets
import imaplib
import email
import sqlite3
from email.header import decode_header
import base64
from flask import Flask, render_template, request, redirect, url_for, flash, session, g
from datetime import datetime
import re

app = Flask(__name__)
app.config['SECRET_KEY'] = secrets.token_hex(16)
app.config['DATABASE'] = 'events.db'
app.config['UPLOAD_FOLDER'] = 'static/uploads'

# Ensure upload directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Gmail credentials
GMAIL_USER = os.environ.get('GMAIL_USER', 'eikonsym@gmail.com')
GMAIL_PASSWORD = os.environ.get('GMAIL_APP_PASSWORD', '')
GMAIL_PREFIX = 'eikonsym+'
GMAIL_DOMAIN = 'gmail.com'

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
    def create(filename, original_filename, sender, event_id):
        db = get_db()
        db.execute(
            'INSERT INTO images (filename, original_filename, sender, event_id) VALUES (?, ?, ?, ?)',
            (filename, original_filename, sender, event_id)
        )
        db.commit()

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
                    Image.create(
                        filename=unique_filename,
                        original_filename=filename,
                        sender=sender,
                        event_id=event['id']
                    )
        
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
        
        # Extract event key from email
        match = re.search(f'{GMAIL_PREFIX}([a-zA-Z0-9]+)@{GMAIL_DOMAIN}', email)
        if not match:
            flash('Invalid event email format', 'error')
            return redirect(url_for('find_event'))
        
        event_key = match.group(1)
        event = Event.get_by_key(event_key)
        
        if not event:
            flash('Event not found', 'error')
            return redirect(url_for('find_event'))
        
        return redirect(url_for('view_event', event_key=event_key))
    
    return render_template('find_event.html')

if __name__ == '__main__':
    app.run(debug=True)
