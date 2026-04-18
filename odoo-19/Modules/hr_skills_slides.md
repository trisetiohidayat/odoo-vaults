---
title: "Hr Skills Slides"
module: hr_skills_slides
type: module
generated: 2026-04-17
generator: orchestrator.py
---

# Hr Skills Slides

## Overview

Module `hr_skills_slides` — auto-generated from source code.

**Source:** `addons/hr_skills_slides/`
**Models:** 5
**Fields:** 9
**Methods:** 2

## Models

### hr.employee (`hr.employee`)

—

**File:** `hr_employee.py` | Class: `HrEmployee`

#### Fields (3)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| `subscribed_courses` | `Many2many` | Y | — | Y | — | — |
| `has_subscribed_courses` | `Boolean` | Y | — | — | — | — |
| `courses_completion_text` | `Char` | Y | — | — | — | — |


#### Methods (1)

| Method | Description |
|--------|-------------|
| `action_open_courses` | |


### hr.employee.public (`hr.employee.public`)

—

**File:** `hr_employee_public.py` | Class: `HrEmployeePublic`

#### Fields (2)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| `has_subscribed_courses` | `Boolean` | — | — | Y | — | — |
| `courses_completion_text` | `Char` | — | — | Y | — | — |


#### Methods (1)

| Method | Description |
|--------|-------------|
| `action_open_courses` | |


### hr.resume.line (`hr.resume.line`)

—

**File:** `hr_resume_line.py` | Class: `HrResumeLine`

#### Fields (4)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| `channel_id` | `Many2one` | Y | — | Y | Y | — |
| `course_url` | `Char` | Y | — | Y | Y | — |
| `duration` | `Integer` | Y | — | — | Y | — |
| `course_type` | `Selection` | Y | — | — | — | — |


#### Methods (0)

| Method | Description |
|--------|-------------|
| — | — |


### slide.channel.partner (`slide.channel.partner`)

—

**File:** `slide_channel.py` | Class: `SlideChannelPartner`

#### Fields (0)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| — | — | — | — | — | — | — |


#### Methods (0)

| Method | Description |
|--------|-------------|
| — | — |


### slide.channel (`slide.channel`)

—

**File:** `slide_channel.py` | Class: `SlideChannel`

#### Fields (0)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| — | — | — | — | — | — | — |


#### Methods (0)

| Method | Description |
|--------|-------------|
| — | — |




## Related

- [Modules/Base](base.md)
- [Modules/HR](HR.md)
