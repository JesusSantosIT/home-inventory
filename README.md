# Home Inventory Management System

A self-hosted Django-based home inventory management system with hierarchical location structure, multi-user support, barcode generation, and insurance export capabilities.

## Features

- **Hierarchical Location Management**: Organize items in a tree structure (House → Room → Room Location → Box → Item)
- **Item Tracking**: Track items with images, serial numbers, purchase information, and current value
- **Barcode & QR Code Generation**: Automatic Code 128 barcodes and QR codes for items and locations
- **Multi-User Support**: User authentication, profiles, and household management
- **Lending Tracking**: Track items borrowed between household members with due dates and overdue alerts
- **Warranty Management**: Track warranty information with expiration alerts
- **Document Storage**: Upload receipts, manuals, and other documents
- **Insurance Export**: Export inventory to CSV or PDF for insurance purposes
- **Search & Filter**: Advanced search and filtering by location, category, condition, and more
- **Responsive Design**: Bootstrap 5-based UI that works on desktop and mobile

## Tech Stack

- **Backend**: Django 5.x (Python 3.11+)
- **Database**: PostgreSQL (SQLite for local development)
- **Frontend**: Django templates + Bootstrap 5
- **Deployment**: Docker Compose
- **File Storage**: Local filesystem (configurable for S3)
- **Barcode Libraries**: python-barcode, qrcode
- **PDF Export**: WeasyPrint
- **Image Processing**: Pillow
- **Hierarchical Data**: django-treebeard (Materialized Path Tree)

## Installation

### Prerequisites

- Python 3.11 or higher
- PostgreSQL 15 (for production) or SQLite (for development)
- Docker and Docker Compose (recommended for deployment)

### Local Development Setup

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd home_inventory
   ```

2. **Create a virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your settings
   ```

5. **Run migrations**
   ```bash
   python manage.py migrate
   ```

6. **Create a superuser**
   ```bash
   python manage.py createsuperuser
   ```

7. **Run the development server**
   ```bash
   python manage.py runserver
   ```

8. **Access the application**
   - Open http://localhost:8000 in your browser
   - Log in with the superuser account you created

### Docker Setup

1. **Build and start containers**
   ```bash
   docker-compose up --build
   ```

2. **Run migrations in the container**
   ```bash
   docker-compose exec web python manage.py migrate
   ```

3. **Create a superuser**
   ```bash
   docker-compose exec web python manage.py createsuperuser
   ```

4. **Access the application**
   - Open http://localhost:8000 in your browser

## Configuration

### Environment Variables

Edit the `.env` file to configure the application:

```env
# Database
DB_PASSWORD=your_secure_password_here
DATABASE_URL=postgres://inventory:your_secure_password_here@db:5432/inventory

# Django - Development (default)
SECRET_KEY=your-secret-key-here-generate-with-python
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Django - Production Settings
# Set these when deploying to production:
# DEBUG=False
# SECRET_KEY=<generate-with-python>
# ALLOWED_HOSTS=your-domain.com,your-domain.com
# SECURE_SSL_REDIRECT=True
# SESSION_COOKIE_SECURE=True
# CSRF_COOKIE_SECURE=True
# SECURE_HSTS_SECONDS=31536000
# SECURE_HSTS_INCLUDE_SUBDOMAINS=True
# SECURE_HSTS_PRELOAD=True

# CSRF Trusted Origins (for development/browser preview)
CSRF_TRUSTED_ORIGINS=http://127.0.0.1:*,http://localhost:*
```

Generate a secret key with:
```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

**Important:** Copy `.env.example` to `.env` and customize for your environment.

### Database Configuration

For local development, SQLite is configured by default. To use PostgreSQL:

1. Uncomment the PostgreSQL configuration in `home_inventory/settings.py`
2. Set your database credentials in the `.env` file
3. Run migrations

### Static Files

For production, collect static files:
```bash
python manage.py collectstatic
```

## Usage

### Creating Locations

1. Navigate to the **Locations** page
2. Click **Create Location**
3. Enter location details:
   - **Name**: e.g., "Main House", "Garage"
   - **Type**: House Name, Room, Room Location, Box, or Other
   - **Description**: Optional description
4. Save the location
5. Create child locations by selecting a parent location

### Adding Items

1. Navigate to the **Items** page
2. Click **Add Item**
3. Fill in item details:
   - **Name**: Item name
   - **Description**: Optional description
   - **Location**: Select from hierarchical location list
   - **Categories**: Select relevant categories
   - **Serial Number**: Optional serial number
   - **Brand/Model**: Optional brand and model
   - **Purchase Information**: Date, price, current value
   - **Condition**: New, Excellent, Good, Fair, or Poor
4. Upload images (optional)
5. Save the item

Barcode and QR codes are automatically generated when the item is saved.

### Tracking Lending

1. Navigate to the **Lending** page
2. Click **Lend Item**
3. Select the item and borrower
4. Set the due date
5. Add notes (optional)
6. Save

View lending status on the dashboard, including overdue items.

### Managing Warranties

1. Navigate to the **Warranties** page
2. Click **Add Warranty**
3. Select the item
4. Enter warranty details:
   - **Provider**: Warranty provider name
   - **Policy Number**: Optional policy number
   - **Expiration Date**: When the warranty expires
   - **Coverage Details**: Optional coverage information
5. Save

Expiring warranties are displayed on the dashboard.

### Uploading Documents

1. Navigate to an item's detail page
2. Click **Documents** section
3. Click **Upload Document**
4. Select document type (Receipt, Warranty, Manual, Insurance, Other)
5. Enter title and upload file
6. Save

### Exporting for Insurance

1. Navigate to the **Items** page
2. Apply filters if needed (location, category, condition)
3. Click **Export CSV** or **Export PDF**
4. The file will be downloaded automatically

## Project Structure

```
home_inventory/
├── apps/
│   ├── locations/          # Hierarchical location management
│   ├── items/              # Item tracking and management
│   ├── users/              # User authentication and profiles
│   ├── lending/            # Lending/borrowing tracking
│   ├── warranties/        # Warranty management
│   └── documents/         # Document storage
├── templates/             # HTML templates
├── static/               # Static files (CSS, JS)
├── media/                # User-uploaded files
├── home_inventory/       # Django project settings
├── docker-compose.yml     # Docker configuration
├── Dockerfile            # Docker image definition
├── requirements.txt      # Python dependencies
└── manage.py            # Django management script
```

## Development

### Running Tests

```bash
python manage.py test
```

### Creating Migrations

After making model changes:

```bash
python manage.py makemigrations
python manage.py migrate
```

### Django Admin

Access the Django admin panel at http://localhost:8000/admin/ for advanced management.

## Security Considerations

- **Secret Key**: Use a strong, randomly generated secret key in production
- **Database Password**: Use a strong password for PostgreSQL
- **HTTPS**: Enable HTTPS in production (configured in settings.py when DEBUG=False)
- **File Uploads**: File types are validated (images and PDFs only)
- **CSRF Protection**: Enabled by default in Django
- **Rate Limiting**: Implemented using django-ratelimit (5 attempts per minute for login)
- **Account Lockout**: Accounts locked for 30 minutes after 5 failed login attempts
- **Secure Cookies**: SESSION_COOKIE_SECURE and CSRF_COOKIE_SECURE enabled in production
- **HSTS**: HTTP Strict Transport Security enabled in production
- **Security Headers**: X-Frame-Options, X-Content-Type-Options, X-XSS-Protection enabled
- **Role-Based Access Control**: Admin, Editor, Viewer, and Lender roles
- **API Security**: API key authentication for external household connections
- **Environment Variables**: All sensitive configuration loaded from .env file

## Deployment

### Production Checklist

- [ ] Set `DEBUG=False` in `.env`
- [ ] Set a strong `SECRET_KEY` (generate with `python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"`)
- [ ] Configure PostgreSQL database
- [ ] Set `ALLOWED_HOSTS` to your domain
- [ ] Set `SECURE_SSL_REDIRECT=True` if using HTTPS
- [ ] Enable HTTPS with SSL certificate
- [ ] Set `SESSION_COOKIE_SECURE=True`
- [ ] Set `CSRF_COOKIE_SECURE=True`
- [ ] Set `SECURE_HSTS_SECONDS=31536000` (1 year)
- [ ] Set `SECURE_HSTS_INCLUDE_SUBDOMAINS=True`
- [ ] Set `SECURE_HSTS_PRELOAD=True`
- [ ] Configure static file serving (nginx)
- [ ] Set up regular database backups
- [ ] Configure media file backups
- [ ] Review security headers in settings.py
- [ ] Configure rate limiting (already implemented)
- [ ] Test login rate limiting and account lockout

### Using Nginx

Example nginx configuration:

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location /static/ {
        alias /app/staticfiles/;
    }

    location /media/ {
        alias /app/media/;
    }

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## Troubleshooting

### Database Connection Issues

If you see database connection errors:
- Ensure PostgreSQL is running
- Check database credentials in `.env`
- Verify the database exists

### Static Files Not Loading

- Run `python manage.py collectstatic`
- Check `STATIC_ROOT` and `STATIC_URL` in settings.py
- Ensure nginx is configured to serve static files

### Barcode Generation Issues

If barcodes don't generate:
- Ensure `python-barcode` and `qrcode` are installed
- Check that Pillow is installed for image processing

## Contributing

Contributions are welcome! Please follow these steps:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Write tests for new functionality
5. Submit a pull request

## License

This project is licensed under the MIT License.

## Support

For issues, questions, or suggestions, please open an issue on the repository.

## Roadmap

Future enhancements:
- [ ] Mobile app for barcode scanning
- [ ] REST API for mobile integration
- [ ] Email notifications for warranty expiration
- [ ] Advanced reporting and analytics
- [ ] Multi-household support
- [ ] Cloud storage integration (S3, Google Cloud Storage)
- [ ] Bulk import/export
- [ ] Item depreciation tracking
