![Eikonsym Logo](eikonsym_icon-512.png)

# Eikonsym

A Flask application for sharing photos from events via email. Eikonsym makes it easy to collect and display photos from your events in one central location.

## Features

- Create events with unique email addresses
- Share the event email with friends and family
- Automatically collect photos sent to the event email
- View all photos in one place with a clean gallery interface
- Full-size image viewing with a simple click
- Admin dashboard for managing events and images
- Configurable auto-refresh for the admin dashboard

## Setup

1. Clone the repository
2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
3. Set up credentials:
   - Copy `.env.example` to `.env`
   - Update with your Gmail account and app password
   - Set an admin password for creating events
   - Set a master admin password for the admin dashboard
   - Note: You need to create an app password in your Google account

4. Run the application:
   ```
   flask run
   ```

## Gmail Setup

To use this application, you need to:

1. Have a Gmail account
2. Enable 2-factor authentication in your Google account
3. Create an app password for this application:
   - Go to your Google Account > Security > App passwords
   - Select "Mail" as the app and give it a name (e.g., "Eikonsym")
   - Copy the generated password
4. Set the app password in the `.env` file

## How It Works

1. When you create an event, a unique key is generated
2. A special email address is created: `eikonsym+EVENTKEY@gmail.com`
3. Share this email with your friends and family
4. When they send photos to this email, the app retrieves them automatically
5. All photos are displayed on the event page in a gallery view
6. Emails with images are automatically deleted after processing to avoid duplicates

## Admin Features

- Secure admin dashboard with master password protection
- View and manage all events
- Delete events and individual images
- Configurable auto-refresh settings
- Collapsible image view for efficient management

## Security Notes

- Keep your app password and admin passwords secure
- The application checks emails sent specifically to event addresses
- Images are stored in the `static/uploads` directory
- Use environment variables for sensitive information in production

## Requirements

- Python 3.6+
- Flask
- Internet connection for email retrieval
- Gmail account with app password
