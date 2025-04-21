# Eikonsym

A Flask application for sharing photos from events via email.

## Features

- Create events with unique email addresses
- Share the event email with friends and family
- Collect photos sent to the event email
- View all photos in one place

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
   - Note: You need to create an app password in your Google account

4. Run the application:
   ```
   flask run
   ```

## Gmail Setup

To use this application, you need to:

1. Have a Gmail account
2. Enable 2-factor authentication
3. Create an app password for this application
4. Set the app password in the `.env` file

## How It Works

1. When you create an event, a unique key is generated
2. A special email address is created: `eikonsym+EVENTKEY@gmail.com`
3. Share this email with your friends
4. When they send photos to this email, the app retrieves them
5. All photos are displayed on the event page

## Security Notes

- Keep your app password secure
- The application checks emails sent specifically to event addresses
- Images are stored in the `static/uploads` directory
