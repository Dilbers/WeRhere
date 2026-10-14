# VIT Applicant CRM - User Story & Product Requirements

## Product overview

The application supports the process for refugee candidates who want to work in
IT. Staff currently manage applications, mentor conversations, project work, and
interview stages across Google Drive workbooks. The CRM brings those records
together in a searchable desktop workspace.

The system is for administrators and regular users. After signing in, both roles
can open Applications, Mentor interviews, and Interviews. Administrators also
have an Admin area.

## Core user story

As a programme team member, I want one place to review candidate applications,
mentor conversations, and project interview progress so that I can find records,
see the next step, and reduce manual follow-up across separate workbooks.

## Functional requirements

### Login and role-based navigation

- Authenticate users using the accounts in `Users.xlsx`.
- Direct administrators to the administrator navigation and regular users to
  the regular-user navigation.
- Both roles can open Applications, Mentor interviews, and Interviews.
- Only administrators can open the Admin area.

### Applications

- Read all application records from `Applications.xlsx`.
- Search candidates by name or other record text.
- Filter candidates whose `Mentor Meeting` field is assigned or not assigned.
- Identify duplicate registrations by matching both full name and email; do not
  merge records silently.
- Offer a de-duplicated view that keeps one application for each name.
- Show the source application fields so staff can inspect the original record.
- Compare candidates with VIT1 and VIT2 records when those source workbooks are
  available. Do not infer previous participation from unrelated fields.

### Mentor interviews

- Read all mentor conversations from the `Mentor` sheet in `Mentor.xlsx`.
- Search candidates, mentors, and conversation details.
- Show the date, VIT group, scores, recommendations, alternative
  recommendations, and notes.
- Filter conversations by the recommendation options supplied in the workbook.

### Interviews and project progress

- Read interview records from `Interviews.xlsx`.
- Search candidates by name or other record text.
- Filter candidates with a project sent and candidates with a project received.
- Show the project sent and received dates together.

### Admin

- The intended admin workflow captures Google Calendar events and displays them
  in a table.
- Administrators can send email to the addresses associated with captured
  events.

## Source workbooks and limitations

The current shared Drive folder provides `Applications.xlsx`, `Mentor.xlsx`,
`Interviews.xlsx`, and `Users.xlsx`. These are imported once into a local
database; changes made later in Drive are not synchronized automatically.

The available application workbook contains VIT3 records. VIT1 and VIT2
workbooks were not present in the shared folder when this workspace was checked,
so the previous-VIT and cross-VIT comparison requirements cannot yet be
completed from the available data.

No Google Calendar event source, OAuth configuration, or email provider is
configured in this desktop build. Calendar capture and event email therefore
remain unimplemented and must not be represented as working features until
access and credentials are provided.

## Acceptance criteria

1. Signing in with an administrator account exposes Applications, Mentor
   interviews, Interviews, and Admin; a regular user sees the three data pages.
2. Applications shows records from the workbook, supports search and mentor
   assignment filters, and displays duplicate name-and-email registrations for
   staff review.
3. The de-duplicated application view keeps one record per candidate name
   without deleting or modifying source records.
4. Mentor interviews displays the conversation details and supports filtering
   by recommendation.
5. Interviews displays project sent and received dates and supports each
   corresponding filter.
6. Missing VIT1/VIT2 workbooks and unavailable Calendar/email integrations are
   clearly identified rather than replaced with fabricated data.
7. Workbook passwords are not retained in the source-record archive; account
   passwords are stored as salted hashes.

## Non-functional requirements

- Use a clear, modern interface that is easy to navigate on desktop.
- Keep imported source records faithful to their workbook values.
- Keep candidate records separate from accommodation or resident concepts.
- Preserve personal workbook data in the local database and do not expose it
  through an external service.
