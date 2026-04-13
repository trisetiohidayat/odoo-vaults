---
type: module
module: fetchmail
tags: [odoo, odoo19, email, imap, pop, mail, incoming-mail, cron]
created: 2026-04-11
updated: 2026-04-11
depth: L4
---

# Fetchmail Module (Incoming Mail Server)

> **IMPORTANT:** In Odoo 19, the `fetchmail` functionality has been integrated into the `mail` module. The model `fetchmail.server` is now located at `mail/models/fetchmail.py` instead of being a separate module. The standalone `fetchmail` module no longer exists in Odoo 19.

## Overview

| Property | Value |
|----------|-------|
| **Technical Name** | `fetchmail.server` (model) |
| **Module** | `mail` (integrated) |
| **Description** | Incoming POP/IMAP mail server configuration |
| **Location** | `odoo/addons/mail/models/fetchmail.py` |

## What is Fetchmail?

The fetchmail functionality enables Odoo to **fetch emails from external IMAP/POP3 mail servers** and process them into Odoo's mail system. This allows:

- Creating records from incoming emails based on email aliases
- Processing support tickets from email
- Creating leads from incoming emails
- Syncing email conversations with Odoo records

---

## fetchmail.server Model

**File:** `mail/models/fetchmail.py`

### Model Definition

```python
class FetchmailServer(models.Model):
    """Incoming POP/IMAP mail server account"""
    _name = 'fetchmail.server'
    _description = 'Incoming Mail Server'
    _order = 'priority'
    _email_field = 'user'
```

### Server States

| State | Description |
|-------|-------------|
| `draft` | Not Confirmed - Server configuration not tested |
| `done` | Confirmed - Server is active and tested |

### Server Types

| Type | Description |
|------|-------------|
| `imap` | IMAP Server (recommended for multi-device sync) |
| `pop` | POP Server (downloads and deletes from server) |
| `local` | Local Server (uses odoo-mailgate.py script) |

### L1 Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Server name (required) |
| `active` | Boolean | Active status (default: True) |
| `state` | Selection | Status: draft/done (readonly) |
| `server` | Char | Hostname or IP of mail server |
| `port` | Integer | Server port number |
| `server_type` | Selection | Type: imap/pop/local (required) |
| `server_type_info` | Text | Info about local script (computed) |
| `is_ssl` | Boolean | SSL/TLS encryption enabled |
| `attach` | Boolean | Keep attachments (default: True) |
| `original` | Boolean | Keep original email (default: False) |
| `date` | Datetime | Last successful fetch (readonly) |
| `error_date` | Datetime | Last error date (readonly) |
| `error_message` | Text | Last error message (readonly) |
| `user` | Char | Username for authentication |
| `password` | Char | Password (stored securely) |
| `object_id` | Many2one | Target model for alias (mail.alias) |
| `priority` | Integer | Server priority (lower = higher priority) |
| `message_ids` | One2many | Linked mail.mail records (readonly) |
| `configuration` | Text | Mailgate script configuration (readonly) |
| `script` | Char | Script path (readonly, default: /mail/static/scripts/odoo-mailgate.py) |

### Port Defaults

| Server Type | Non-SSL Port | SSL Port |
|-------------|--------------|----------|
| IMAP | 143 | 993 |
| POP | 110 | 995 |

### L2 Server State and Connection Testing

#### Onchange Auto-Configuration

```python
@api.onchange('server_type', 'is_ssl', 'object_id')
def onchange_server_type(self):
    self.port = 0
    if self.server_type == 'pop':
        self.port = self.is_ssl and 995 or 110
    elif self.server_type == 'imap':
        self.port = self.is_ssl and 993 or 143

    # Generate mailgate configuration text
    self.configuration = """Use the below script with:
odoo-mailgate.py --host=HOSTNAME --port=PORT -u %(uid)d -p PASSWORD -d %(dbname)s"""
```

#### button_confirm_login

Tests the server connection by attempting to connect and login. Sets `state` to `done` on success.

```python
def button_confirm_login(self):
    for server in self:
        connection = None
        try:
            connection = server._connect__(allow_archived=True)
            server.write({'state': 'done'})
        except UnicodeError as e:
            raise UserError(_("Invalid server name!\n %s", tools.exception_to_unicode(e)))
        except (gaierror, timeout, IMAP4.abort) as e:
            raise UserError(_("No response received. Check server information.\n %s", ...))
        except (IMAP4.error, poplib.error_proto) as err:
            raise UserError(_("Server replied with following exception:\n %s", ...))
        except SSLError as e:
            raise UserError(_("An SSL exception occurred. Check SSL/TLS configuration.\n %s", ...))
        except (OSError, Exception) as err:
            _logger.info("Failed to connect to %s server %s.", server.server_type, server.name, exc_info=True)
            raise UserError(_("Connection test failed: %s", ...))
        finally:
            if connection:
                connection.disconnect()
```

---

## L3: Cron Job, Mail Processing, and SSL/TLS

### Cron Job Triggering

The mail gateway cron (`mail.ir_cron_mail_gateway_action`) runs periodically to check all configured servers. The cron is automatically enabled/disabled based on the number of active servers.

```python
MAIL_SERVER_DOMAIN = Domain('state', '=', 'done') & Domain('server_type', '!=', 'local')

@api.model
def _fetch_mails(self, **kw):
    """Method called by cron to fetch mails from servers."""
    assert self.env.context.get('cron_id') == self.env.ref('mail.ir_cron_mail_gateway_action').id
    self.search(MAIL_SERVER_DOMAIN)._fetch_mail(**kw)
    if not self.search_count(MAIL_SERVER_DOMAIN):
        self.env['ir.cron']._commit_progress(deactivate=True)
```

**Key behavior:** If no active servers exist, the cron deactivates itself via `_commit_progress(deactivate=True)`.

### Full Email Fetching Flow

```python
def _fetch_mail(self, batch_limit=50) -> Exception | None:
    """Fetch e-mails from multiple servers. Commit after each message."""
    result_exception = None
    servers = self.with_context(fetchmail_cron_running=True)
    total_remaining = len(servers)

    self.env['ir.cron']._commit_progress(remaining=total_remaining)

    for server in servers:
        total_remaining -= 1  # the server is checked
        # Lock server record to prevent concurrent fetching
        if not server.try_lock_for_update(allow_referencing=True).filtered_domain(MAIL_SERVER_DOMAIN):
            _logger.info('Skip checking for new mails on mail server id %d (unavailable)', server.id)
            continue

        server_connection = None
        message_cr = None
        try:
            server_connection = server._connect__()
            # Separate cursor for message processing (keeps lock on server)
            message_cr = self.env.registry.cursor()
            MailThread = server.env['mail.thread'].with_env(
                self.env(cr=message_cr)
            ).with_context(default_fetchmail_server_id=server.id)

            thread_process_message = functools.partial(
                MailThread.message_process,
                model=server.object_id.model,
                save_original=server.original,
                strip_attachments=(not server.attach),
            )

            unread_message_count = server_connection.check_unread_messages()
            total_remaining += unread_message_count

            for message_num, message in server_connection.retrieve_unread_messages():
                count += 1
                total_remaining -= 1
                try:
                    thread_process_message(message=message)
                    remaining_time = MailThread.env['ir.cron']._commit_progress(1)
                except Exception:
                    MailThread.env.cr.rollback()
                    failed += 1
                    _logger.info('Failed to process mail...', exc_info=True)
                    remaining_time = MailThread.env['ir.cron']._commit_progress()
                server_connection.handled_message(message_num)
                if count >= batch_limit or not remaining_time:
                    break

            server.error_date = False
            server.error_message = False

        except Exception as e:
            result_exception = e
            _logger.info("General failure when trying to fetch mail...", exc_info=True)
            if not server.error_date:
                server.error_date = fields.Datetime.now()
                server.error_message = exception_to_unicode(e)
            elif server.error_date < fields.Datetime.now() - MAIL_SERVER_DEACTIVATE_TIME:
                server.set_draft()
                server.env['ir.cron']._notify_admin(message)

        finally:
            if message_cr is not None:
                message_cr.close()
            if server_connection:
                server_connection.disconnect()

        server.write({'date': fields.Datetime.now()})
        self.env.cr.commit()
        if not self.env['ir.cron']._commit_progress(remaining=total_remaining):
            break
    return result_exception
```

### Connection Classes

#### IMAP Connection

```python
class OdooIMAP4(IMAP4):
    def check_unread_messages(self):
        self.select()
        result, data = self.search(None, '(UNSEEN)')
        self._unread_messages = data[0].split() if data and data[0] else []
        self._unread_messages.reverse()
        return len(self._unread_messages)

    def retrieve_unread_messages(self):
        assert self._unread_messages is not None
        while self._unread_messages:
            num = self._unread_messages.pop()
            result, data = self.fetch(num, '(RFC822)')
            self.store(num, '-FLAGS', '\\Seen')  # Mark as read
            yield num, data[0][1]

    def handled_message(self, num):
        self.store(num, '+FLAGS', '\\Seen')

    def disconnect(self):
        if self._unread_messages is not None:
            self.close()
        self.logout()

class OdooIMAP4_SSL(OdooIMAP4, IMAP4_SSL):
    pass
```

#### POP Connection

```python
class OdooPOP3(POP3):
    def check_unread_messages(self):
        (num_messages, _total_size) = self.stat()
        self.list()
        self._unread_messages = list(range(num_messages, 0, -1))
        return num_messages

    def retrieve_unread_messages(self):
        while self._unread_messages:
            num = self._unread_messages.pop()
            (_header, messages, _octets) = self.retr(num)
            message = (b'\n').join(messages)
            yield num, message

    def handled_message(self, num):
        self.dele(num)  # Delete from server

    def disconnect(self):
        self.quit()

class OdooPOP3_SSL(OdooPOP3, POP3_SSL):
    pass
```

### SSL/TLS Configuration

```python
def _connect__(self, allow_archived=False):
    self.ensure_one()
    if not allow_archived and not self.active:
        raise UserError(_('The server "%s" cannot be used because it is archived.', self.display_name))

    if self._get_connection_type() == 'imap':
        server, port, is_ssl = self.server, int(self.port), self.is_ssl
        connection = OdooIMAP4_SSL(server, port, timeout=MAIL_TIMEOUT) if is_ssl else OdooIMAP4(server, port, timeout=MAIL_TIMEOUT)
        self._imap_login__(connection)
    elif self._get_connection_type() == 'pop':
        server, port, is_ssl = self.server, int(self.port), self.is_ssl
        connection = OdooPOP3_SSL(server, port, timeout=MAIL_TIMEOUT) if is_ssl else OdooPOP3(server, port, timeout=MAIL_TIMEOUT)
        connection.user(self.user)
        connection.pass_(self.password)
    return connection
```

The `_imap_login__` method can be overridden by submodules (e.g., Gmail) for custom authentication methods.

### Cron Auto-Enabling

```python
@api.model
def _update_cron(self):
    if self.env.context.get('fetchmail_cron_running'):
        return
    try:
        cron = self.env.ref('mail.ir_cron_mail_gateway_action')
        cron.toggle(model=self._name, domain=MAIL_SERVER_DOMAIN)
    except ValueError:
        pass
```

The `_update_cron` method is called on create/write/unlink of any fetchmail server, ensuring the cron is active only when needed.

---

## L4: Error Handling, Security, and Odoo 18→19 Changes

### L4.1 Error Handling

#### Automatic Server Deactivation

Servers experiencing persistent failures are automatically deactivated after 5 days:

```python
MAIL_SERVER_DEACTIVATE_TIME = datetime.timedelta(days=5)
MAIL_TIMEOUT = 60

# In _fetch_mail:
if server.error_date < fields.Datetime.now() - MAIL_SERVER_DEACTIVATE_TIME:
    message = "Deactivating fetchmail %s server %s (too many failures)"
    server.set_draft()  # Reset to draft state
    server.env['ir.cron']._notify_admin(message)
```

**Root cause:** This prevents repeated failed connection attempts from consuming resources and generating errors indefinitely. When a server is set back to draft, the cron domain `state = 'done'` excludes it from processing.

#### Error Tracking Fields

| Field | Description | Reset Condition |
|-------|-------------|----------------|
| `error_date` | Date of last failure | Reset on successful fetch |
| `error_message` | Full error message | Reset on successful fetch |

#### Connection Exception Hierarchy

```python
# Hierarchy of exceptions caught during connection testing:
UnicodeError          # Invalid server name encoding
(gaierror, timeout, IMAP4.abort)  # Network unreachable / timeout
(IMAP4.error, poplib.error_proto)  # Server rejected credentials
SSLError              # SSL/TLS handshake failure
(OSError, Exception)  # Catch-all for unexpected errors
```

Each exception type maps to a specific user-facing error message.

### L4.2 Security Considerations

#### Password Storage

- Passwords are stored as plain Char in the database. For production, ensure:
  - Database-level encryption at rest
  - Network-level security (SSL/TLS connections mandatory)
  - Restricted database user permissions
  - Consider using `ir.config_parameter` with encryption for higher security

#### SSL/TLS Requirements

- **Always enable `is_ssl=True`** for production mail servers
- Non-SSL connections transmit credentials in plain text
- Default ports: IMAPS=993, POP3S=995
- SSL certificate verification is handled by Python's `ssl` module

#### Message Processing Security

- Messages are processed through `mail.thread.message_process()`, which:
  - Sanitizes HTML content
  - Validates email headers
  - Extracts attachments safely
- Original email storage (`original=True`) doubles database size

### L4.3 Odoo 18→19 Changes

#### Changes from Odoo 18 to 19

| Aspect | Odoo 18 | Odoo 19 |
|--------|---------|---------|
| Module location | `mail` (integrated) | `mail` (integrated) |
| Connection timeout | Not explicitly set | `MAIL_TIMEOUT = 60` |
| Message processing | Single cursor | Per-message cursor with rollback |
| `_get_connection_type()` | Not present | Extensible hook added |
| `_imap_login__()` override | Not present | Extension point for Gmail/etc. |
| `_update_cron()` | Simple toggle | Uses `cron.toggle()` with domain |

#### Key New Extension Points in Odoo 19

**1. `_get_connection_type()`** — Override to support custom server types:

```python
def _get_connection_type(self):
    """Return which connection must be used for this mail server.
    Can be overridden in sub-module to define which connection to use
    for a specific 'server_type' (e.g. Gmail server).
    """
    self.ensure_one()
    return self.server_type
```

**2. `_imap_login__()`** — Override for custom IMAP authentication:

```python
def _imap_login__(self, connection):
    """Authenticate the IMAP connection.
    Can be overridden in other module for different authentication methods."""
    self.ensure_one()
    connection.login(self.user, self.password)
```

### L4.4 Batch Processing Architecture

The `_fetch_mail` method uses a sophisticated batch processing pattern:

1. **Server locking**: `try_lock_for_update()` prevents concurrent fetching from the same server
2. **Per-message cursor**: A separate database cursor isolates each message processing, allowing rollback without affecting the fetch state
3. **Progress tracking**: `ir.cron._commit_progress()` reports remaining messages and respects cron timeout
4. **Batch limits**: `batch_limit=50` prevents infinite loops; combined with cron timeout, ensures cron jobs complete

---

## Attachment Handling

| Field | Behavior |
|-------|----------|
| `attach = True` (default) | Attachments are downloaded and stored |
| `attach = False` | Attachments are stripped before processing |
| `original = True` | Full original email attached to message |
| `original = False` (default) | Only parsed content stored |

---

## Local Server (odoo-mailgate.py)

For servers that cannot be accessed directly (e.g., localhost-only MTA), use the `local` server type:

```python
script = fields.Char(default='/mail/static/scripts/odoo-mailgate.py')
```

### Configuration Example

```bash
# /etc/aliases:
odoo_mailgate: "|/path/to/odoo-mailgate.py --host=localhost -u USER_ID -p PASSWORD -d DATABASE"
```

### Mailgate Script

Located at: `odoo/addons/mail/static/scripts/odoo-mailgate.py`

Usage:
```bash
odoo-mailgate.py --host=HOSTNAME --port=PORT -u UID -p PASSWORD -d DBNAME
```

---

## Related Models

| Model | Relationship | Purpose |
|-------|--------------|---------|
| `mail.mail` | One2many (`fetchmail_server_id`) | Stored fetched emails |
| `mail.alias` | Many2one (`object_id`) | Target model for alias |
| `ir.model` | Many2one (`object_id`) | Model selection for alias |
| `mail.thread` | (extends) | Message processing via `message_process()` |

---

## Views

### List View (`fetchmail.server.list`)

Displays all configured mail servers with:
- Server name
- Server type (IMAP/POP)
- Username
- Last fetch date
- State badge

### Form View (`fetchmail.server.form`)

Two main pages:

**Server & Login Tab:**
- Server configuration
- Login credentials
- Alias/model mapping
- Local script configuration

**Advanced Tab (group: base.group_no_one):**
- Priority
- Attachment handling options
- Error information

---

## Related

- [Modules/mail](Modules/mail.md) - Mail module documentation
- [Modules/fetchmail](Modules/fetchmail.md) - Email alias configuration
