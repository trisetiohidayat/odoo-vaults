# Timesheets/Attendances Reporting (hr_timesheet_attendance)

## Overview
- **Category:** Human Resources/Attendances
- **Depends:** `hr_timesheet`, `hr_attendance`
- **Auto-install:** True
- **License:** LGPL-3

Reports that compare timesheet entries with attendance records. Provides a reporting view to reconcile timesheet hours against attendance hours per employee.

## Models
No custom models — this module provides a `hr.timesheet.attendance.report` SQL view (defined in `report/hr_timesheet_attendance_report_view.xml`) and security rules.

## Key Features

### Reporting View
`hr_timesheet_attendance_report` — a read-only SQL reporting view that joins timesheet lines with attendance records to show discrepancies between recorded timesheet hours and attendance hours.

### Security
- `report/hr_timesheet_attendance_report_view.xml` — form/tree views for the report
- `security/hr_timesheet_attendance_report_security.xml` — record rules restricting access

## Related
- [Modules/hr_timesheet](modules/hr_timesheet.md) — Timesheets
- [Modules/hr_attendance](modules/hr_attendance.md) — Attendance tracking
