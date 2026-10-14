# WeRhere PyQt6 Desktop App

This project is a desktop CRM prototype for managing VIT IT-training applicants. It is built in PyQt6 and stores a local snapshot of the shared Google Drive workbooks in SQLite.

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

On first launch, the app needs an internet connection and read access to the
shared Google Drive workbooks. It imports `Applications.xlsx`, `Interviews.xlsx`,
`Mentor.xlsx`, and `Users.xlsx` into `wehere.db` once. Later launches use that
local database and do not download or synchronize workbook changes.

The workspace has Applications, Mentor interviews, Mentors, and Interviews screens.
Applications can be searched and filtered by mentor assignment, duplicate
name-and-email records, and unique names. The full application source row is
available when a candidate is selected. Candidates can be added or edited, and
an email draft can be opened for a selected candidate in the computer's default
email application. This creates a draft only; it does not send email
automatically. Mentor interviews show the candidate, mentor, date, scores,
recommendations, and notes, with a recommendation filter. New mentor
appointments can be scheduled or edited with a date, time, candidate, and
assigned interviewer. The Mentors screen lists the distinct mentors found in
recorded or scheduled interviews; the appointment form also offers those
mentors in its interviewer dropdown and allows entering another name.
Interviews show project-sent and project-received dates with corresponding
filters. The source workbook rows are retained locally so the screens reflect
the original data instead of deriving residents or accommodation records from
application statuses.

The available Drive folder contains VIT3 applications, but no VIT1/VIT2
workbooks; previous-VIT comparison is therefore unavailable. Google Calendar
event capture and email sending are also not configured in this desktop build.
The source `Password` cells are excluded from the local source-record archive;
imported account passwords are stored as salted PBKDF2 hashes. Workbook users
with the `user` role keep that role in the application.

Each computer has its own local database. The workbooks include personal
information, so keep `wehere.db` private and do not share or commit it. If the
shared workbooks cannot be downloaded or validated, startup displays an error
instead of silently substituting sample data. Ask the coordinator for workbook
access or account credentials.

The app opens on a welcome screen. Select **Sign in to your account** to reach
the username and password form. Password visibility can be toggled; password
reset and new account creation are not available in this local build, so users
should contact their coordinator for account help.

Use the language selector on the welcome or sign-in screen to switch between
English, Turkish, and Dutch. The selected language is saved locally and used
throughout the workspace.

The virtual environment is machine-specific, so it is recreated from
`requirements.txt` rather than copied from another computer. VS Code settings
are optional editor preferences and are not needed to run the app.

To install without a virtual environment instead:

1. Install the listed dependency:
   ```bash
   pip install -r requirements.txt
   ```
2. Run the app:
   ```bash
   python -m app.main
   ```

## Sign-in

Sign in with an account from `Users.xlsx`; contact the coordinator if you need
the workbook credentials or account help. Password reset and new account
creation are not available in this local build.

## Structure

- `app/backend.py` — SQLite-backed data layer, role-aware authentication, and preserved workbook source rows
- `app/drive_import.py` — one-time download and validation of the shared Google Drive workbooks
- `app/real_ui.py` — branded login flow and the full polished desktop interface
- `app/localization.py` — English, Turkish, and Dutch interface text
- `app/styles.qss` — light theme and shared component styling
- `app/assets/brand-logo.svg` — product logo used in the UI
- `app/assets/chevron-down.svg` — shared dropdown indicator

## Notes

The application stores data locally in `wehere.db`. It does not connect to an
external email provider, Google Calendar, or a hosted multi-user service.
