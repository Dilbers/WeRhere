# WeRhere PyQt6 Desktop App

This project is a desktop CRM for managing VIT IT-training applicants. It is built in PyQt6, reads its source workbooks from Google Sheets, and keeps a local SQLite cache.

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

## Google Sheets setup

The app connects to four Google Sheets copies configured in
`app/drive_import.py`. Keep the required worksheet names and column headers
unchanged. The Google account used to authorize the app must have access to all
four copies.

1. In Google Cloud Console, create a project and enable the Google Sheets API.
2. Configure an OAuth consent screen and create an OAuth client with application
   type **Desktop app**.
3. Download its JSON file and save it as
   `credentials/google_oauth_client.json` in this project.
4. Install requirements and launch the app. On first launch, a browser opens so
   you can authorize access to your Sheets. The local OAuth token is saved under
   `credentials/` and is excluded from Git.

At startup, the app reads the four Sheets into its local SQLite cache. Adding
or editing an applicant writes the change to the online Applications sheet and
then updates the local cache. Other workspace data, such as messages and
scheduled appointments, remains local. Google Calendar event capture and email
sending are not configured.

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

Each computer has its own local database and Google OAuth token. The workbooks
include personal information, so keep `wehere.db` and the `credentials/`
directory private and do not share or commit them. If the Sheets cannot be read
or validated, startup displays an error instead of silently substituting sample
data.

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
- `app/drive_import.py` — authenticated Google Sheets read/write and workbook validation
- `app/real_ui.py` — branded login flow and the full polished desktop interface
- `app/localization.py` — English, Turkish, and Dutch interface text
- `app/styles.qss` — light theme and shared component styling
- `app/assets/brand-logo.svg` — product logo used in the UI
- `app/assets/chevron-down.svg` — shared dropdown indicator

## Notes

The application caches source records locally in `wehere.db`; source workbook
changes and applicant additions/edits synchronize with the configured Google
Sheets. Messages and scheduled appointments remain local to each computer.
