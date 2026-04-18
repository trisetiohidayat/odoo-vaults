---
title: "Crm Livechat"
module: crm_livechat
type: module
generated: 2026-04-17
generator: orchestrator.py
---

# Crm Livechat

## Overview

Module `crm_livechat` — auto-generated from source code.

**Source:** `addons/crm_livechat/`
**Models:** 5
**Fields:** 10
**Methods:** 5

## Models

### chatbot.script (`chatbot.script`)

—

**File:** `chatbot_script.py` | Class: `ChatbotScript`

#### Fields (1)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| `lead_count` | `Integer` | Y | — | — | — | — |


#### Methods (1)

| Method | Description |
|--------|-------------|
| `action_view_leads` | |


### chatbot.script.step (`chatbot.script.step`)

When reaching a 'create_lead' step, we extract the relevant information: visitor's
        email, phone and conversation history to create a crm.lead.

        We use the email and phone to update the

**File:** `chatbot_script_step.py` | Class: `ChatbotScriptStep`

#### Fields (2)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| `step_type` | `Selection` | — | — | — | — | — |
| `crm_team_id` | `Many2one` | — | — | — | — | — |


#### Methods (0)

| Method | Description |
|--------|-------------|
| — | — |


### crm.lead (`crm.lead`)

—

**File:** `crm_lead.py` | Class: `CrmLead`

#### Fields (1)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| `origin_channel_id` | `Many2one` | — | — | — | — | — |


#### Methods (3)

| Method | Description |
|--------|-------------|
| `create` | |
| `write` | |
| `action_open_livechat` | |


### discuss.channel (`discuss.channel`)

Create a lead from channel /lead command
        :param partner: internal user partner (operator) that created the lead;
        :param key: operator input in chat ('/lead Lead about Product')

**File:** `discuss_channel.py` | Class: `DiscussChannel`

#### Fields (6)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| `lead_ids` | `One2many` | Y | — | — | — | — |
| `has_crm_lead` | `Boolean` | Y | — | — | Y | — |
| `pre_start` | `Markup` | — | — | — | — | — |
| `pre_end` | `Markup` | — | — | — | — | — |
| `i_start` | `Markup` | — | — | — | — | — |
| `i_end` | `Markup` | — | — | — | — | — |


#### Methods (1)

| Method | Description |
|--------|-------------|
| `execute_command_lead` | |


### res.users (`res.users`)

—

**File:** `res_users.py` | Class: `ResUsers`

#### Fields (0)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| — | — | — | — | — | — | — |


#### Methods (0)

| Method | Description |
|--------|-------------|
| — | — |




## Related

- [[Modules/Base]]
- [[Modules/CRM]]
