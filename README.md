# WeRhere PyQt6 Desktop App

This project is a functional desktop prototype for the WeRhere resident operations dashboard. It is built in PyQt6, uses SQLite persistence, and follows the product story and visual direction provided in the concept materials.

## Quick start

Clone the project and enter its folder:

```powershell
git clone https://github.com/Dilbers/WeRhere.git
Set-Location WeRhere
```

Create a virtual environment and install the dependencies:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Then launch the app:

```powershell
.\.venv\Scripts\python.exe -m app.main
```

On first launch, the app creates `wehere.db` in the project folder, initializes
its tables, and adds local starter accounts and sample records. Each person gets
their own local database; this desktop app does not synchronize data between
computers.

The virtual environment is machine-specific, so it is recreated from
`requirements.txt` rather than copied from another computer. VS Code settings
are optional editor preferences and are not needed to run the app.

The starter sign-in accounts are created in each new local database:

| Account | Username | Password |
|---|---|---|
| Administrator | `admin` | `admin123` |
| Resident | `resident` | `resident123` |

These are shared starter credentials, not private user accounts. Change them
before using the application with real data.

To install without a virtual environment instead:

1. Install the listed dependency:
   ```bash
   pip install -r requirements.txt
   ```
2. Run the app:
   ```bash
   python -m app.main
   ```

## Default login

| Account | Username | Password | What it can see |
|---|---|---|---|
| Administrator | `admin` | `admin123` | Applications, mentor sessions, residents, operational overview, and messages |
| Resident | `resident` | `resident123` | Own application, shared schedule, support guidance, and messages |

The resident account is linked to the application for Ava Martin. Residents can view their own information and message the administrator; record management remains in the administrator area.

## Structure

- `app/backend.py` — SQLite-backed data layer, role-aware authentication, application/session records, in-app messages, and dashboard metrics
- `app/real_ui.py` — branded login flow and the full polished desktop interface
- `app/styles.qss` — light theme and shared component styling
- `app/assets/brand-logo.svg` — product logo used in the UI

## Notes

The application stores data locally in `wehere.db`; in-app messages are available to accounts using this local database. This desktop build does not connect to an external email provider or hosted multi-user service. Change the starter account passwords and review deployment/security requirements before using it with real resident data.
