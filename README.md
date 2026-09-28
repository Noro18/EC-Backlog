# EC Backlog Management

## Project Description

EC Backlog Management is a Django-based web application designed to manage and track engineering change (EC) backlogs efficiently. It provides a structured workflow for submitting, reviewing, approving, and tracking engineering change requests across teams and projects.

## Tech Stack

- **Language**: Python 3.12+
- **Framework**: Django 6.1+
- **Database**: SQLite (development) / PostgreSQL (production)
- **Task Queue**: Django-Q2 (background task processing)
- **Filtering**: Django-Filter (API query filtering)
- **Tables**: Django-Tables2 (tabular data rendering)
- **Audit Logging**: Django-Auditlog (model change tracking)
- **Configuration**: Django-Environ (environment-based settings)

## Project Management with uv

This project uses **[uv](https://docs.astral.sh/uv/)** as the Python package and project manager. All dependencies are managed through `pyproject.toml` and locked in `uv.lock`.

### Prerequisites

- Python 3.12+ (managed by uv)
- uv installed ([installation guide](https://docs.astral.sh/uv/getting-started/installation/))

### Setup

```bash
# Clone the repository
git clone <repository-url>
cd EC-Backlog-Management

# Create and sync the virtual environment with all dependencies
uv sync

# The virtual environment will be created at .venv/
# All packages from pyproject.toml will be installed
```

### Common Development Commands

```bash
# Run Django management commands
uv run python manage.py <command>

# Run the development server
uv run python manage.py runserver

# Create and run migrations
uv run python manage.py makemigrations
uv run python manage.py migrate

# Create a superuser
uv run python manage.py createsuperuser

# Run tests
uv run python manage.py test

# Add a new dependency
uv add <package-name>

# Add a development dependency
uv add --dev <package-name>

# Update dependencies
uv lock --upgrade
uv sync
```

### Why uv?

- **Fast**: Written in Rust, significantly faster than pip/venv
- **Reproducible**: Lockfile (`uv.lock`) ensures identical environments across machines
- **Integrated**: Manages Python versions, virtual environments, and packages in one tool
- **Modern**: Supports `pyproject.toml` standards (PEP 621)

## Architecture

See [ARCHITECTURE.md](ARCHITECTURE.md) for system architecture, database schema, and component design (to be created).

## License

[Add license information here]