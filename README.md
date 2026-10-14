# WeRhere PyQt6 Desktop App

This project is a functional desktop prototype for the WeRhere resident operations dashboard. It is built in PyQt6, uses SQLite persistence, and follows the product story and visual direction provided in the concept materials.

## Quick start

1. Create and activate a virtual environment if desired.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Run the app:
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
