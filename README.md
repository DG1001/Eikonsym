![Eikonsym Logo](static/eikonsym_icon-512.png)

# Eikonsym [![Docker Image CI](https://github.com/DG1001/Eikonsym/actions/workflows/docker-publish.yml/badge.svg)](https://github.com/DG1001/Eikonsym/actions/workflows/docker-publish.yml)

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

## Deployment with Docker

This project includes a `Dockerfile` and `docker-compose.yml` for easy containerization and deployment. A GitHub Actions workflow (`.github/workflows/docker-publish.yml`) is also configured to automatically build and push the Docker image to a container registry (Docker Hub or GitHub Container Registry) on pushes to the `main` branch.

### Prerequisites

- Docker installed on your server/local machine.
- Docker Compose installed on your server/local machine.

### Building the Image

The Docker image is automatically built and pushed by the GitHub Actions workflow. You need to:

1.  **Choose a Registry:** In `.github/workflows/docker-publish.yml`, uncomment either the Docker Hub or GitHub Container Registry (GHCR) section.
2.  **Configure Secrets (if needed):**
    *   **Docker Hub:** Add `DOCKERHUB_USERNAME` and `DOCKERHUB_TOKEN` secrets to your GitHub repository settings.
    *   **GHCR:** No secrets are needed by default if pushing to your own repository's package registry.
3.  **Push to `main`:** Pushing changes to the `main` branch will trigger the workflow, build the image, and push it to your chosen registry (e.g., `ghcr.io/your-username/eikonsym:latest`).

### Running on a Server

1.  **SSH into your server.**
2.  **Install Docker and Docker Compose.**
3.  **Create a directory for the application:**
    ```bash
    mkdir eikonsym-app && cd eikonsym-app
    ```
4.  **Copy `docker-compose.yml` to this directory.**
5.  **Create a `.env` file** in this directory with your production credentials (copy from `.env.example` and fill in):
    ```dotenv
    # .env file contents
    GMAIL_USER=your_email@gmail.com
    GMAIL_APP_PASSWORD=your_gmail_app_password
    ADMIN_PASSWORD=your_event_creation_password
    ADMIN_MASTER_PASSWORD=your_master_admin_password
    # Optional: Set Flask secret key if you want it fixed
    # SECRET_KEY=a_very_strong_random_secret_key
    ```
    *Ensure this file is **not** committed to Git.*
6.  **Create placeholder files/directories for volumes** (Docker usually handles this, but doing it manually ensures correct permissions initially):
    ```bash
    touch events.db
    mkdir -p static/uploads
    ```
7.  **Pull the latest image** from your registry:
    *   *GHCR Example:* `docker pull ghcr.io/your-github-username/eikonsym:latest`
    *   *Docker Hub Example:* `docker pull your-dockerhub-username/eikonsym:latest`
    *(You might need to `docker login ghcr.io` or `docker login` first).*
8.  **Start the application:**
    ```bash
    docker compose up -d
    ```
    The application will be accessible on port 80 (or the host port specified in `docker-compose.yml`). The database (`events.db`) and uploads (`static/uploads/`) will persist on the host machine within the `eikonsym-app` directory.

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

## Security Considerations

- **SECRET_KEY:** For production deployments, ensure you set a strong, unique `SECRET_KEY` as an environment variable. The default randomly generated key is not suitable for production, especially when running multiple server processes (like with Gunicorn), as it will lead to session invalidation.
- **CSRF Protection:** This application currently lacks Cross-Site Request Forgery (CSRF) protection. It is highly recommended to add CSRF protection (e.g., using the `Flask-WTF` extension) to all forms that perform state-changing actions (creating events, logging in, deleting items) to prevent malicious websites from forcing users to perform unwanted actions. This requires adding the library and modifying the HTML templates to include CSRF tokens.
- **Dependencies:** Regularly check `requirements.txt` for known vulnerabilities using tools like `pip-audit` or GitHub's Dependabot feature.
- **File Uploads:** Filenames are sanitized using `werkzeug.utils.secure_filename`. Ensure the upload folder (`static/uploads`) has appropriate permissions on your server. Consider adding file size limits or more robust file type checking if necessary for your environment.
- **Input Validation:** Basic input validation is performed, but review and enhance it based on your specific security requirements.

## Requirements

- Python 3.6+
- Flask
- Internet connection for email retrieval
- Gmail account with app password
