# MCP Email Server

A Model Context Protocol (MCP) server for email operations (POP3/SMTP with TLS). Allows an LLM like Claude to read, send, and manage emails.

## Quick Start (uvx)

The fastest way to use the Email MCP Server — no clone, no install:

```bash
uvx https://github.com/ptbsare/email-mcp-server
```

That's it. The server starts immediately. On first run, uvx caches the package; subsequent launches are instant.

### Environment Variables

The server reads configuration from environment variables or a `.env` file:

```dotenv
EMAIL_USER=YourEmailUsername@example.com
EMAIL_PASS=YourEmailAppPasswordOrRegularPassword
POP3_SERVER=pop.example.com
POP3_PORT=995
SMTP_SERVER=smtp.example.com
SMTP_PORT=587
SMTP_USE_SSL=false
```

## Using with Claude Desktop

Add the following to your Claude Desktop config file:

**macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
**Windows:** `%APPDATA%/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "email-mcp-server": {
      "command": "uvx",
      "args": [
        "https://github.com/ptbsare/email-mcp-server"
      ],
      "env": {
        "EMAIL_USER": "your-email@example.com",
        "EMAIL_PASS": "your-app-password",
        "POP3_SERVER": "pop.example.com",
        "SMTP_SERVER": "smtp.example.com"
      }
    }
  }
}
```

> **Tip:** You can put credentials in a `.env` file in the working directory instead of the `env` section. The `env` section overrides `.env` values if both are present.

## Features

- **Poll Emails:** List inbox email headers (`pollEmails`)
- **Fetch Full Emails:** Get complete email content by ID (`getEmailsById`)
- **Delete Emails:** Remove emails by ID (`deleteEmailsById`)
- **Send Emails:** Send plain text (`sendTextEmail`) or HTML (`sendHtmlEmail`) emails
- **Secure Connections:** POP3 over SSL (port 995), SMTP with STARTTLS (port 587) or direct SSL (port 465)

## Tools

### `pollEmails()`

Returns headers for all emails in the inbox.

**Inputs:** None
**Returns:** `list[dict]` — Each dict contains `id`, `Subject`, `From`, `Date`, `Message-ID`

### `getEmailsById(ids: list[int])`

Fetches full email content (headers + body) for given IDs.

**Inputs:** `ids` — List of email IDs from `pollEmails()`
**Returns:** `list[dict]` — Each dict contains `id`, `headers`, `body`

### `deleteEmailsById(ids: list[int])`

Marks emails for deletion. Deletion is committed when the POP3 connection closes.

**Inputs:** `ids` — List of email IDs to delete
**Returns:** `{"deleted": [int], "failed": {id: error_msg}}`

### `sendTextEmail(fromAddress, toAddresses, subject, body)`

Sends a plain text email.

**Inputs:** sender, recipients list, subject, plain text body
**Returns:** `{"status": "success"}`

### `sendHtmlEmail(fromAddress, toAddresses, subject, body)`

Sends an HTML email.

**Inputs:** sender, recipients list, subject, HTML body
**Returns:** `{"status": "success"}`

## Development Setup

### Prerequisites
- Python 3.12+
- [uv](https://github.com/astral-sh/uv)

### Steps

1. **Clone the repository:**
   ```bash
   git clone https://github.com/ptbsare/email-mcp-server
   cd email-mcp-server
   ```

2. **Install dependencies:**
   ```bash
   uv pip install -e .
   ```

3. **Create `.env` file:**
   ```dotenv
   EMAIL_USER=your-email@example.com
   EMAIL_PASS=your-app-password
   POP3_SERVER=pop.example.com
   SMTP_SERVER=smtp.example.com
   ```

4. **Run the server:**
   ```bash
   uv run main.py
   ```

## Important Notes

- **App Passwords:** If your email provider uses 2FA, generate an App Password for `EMAIL_PASS`
- **Email IDs:** POP3 IDs are session-specific. Call `pollEmails()` before `getEmailsById()` or `deleteEmailsById()`
- **Security:** Never commit your `.env` file — it's already in `.gitignore`

## Project Structure

```
email-mcp-server/
├── main.py           # MCP server entry point
├── pyproject.toml    # Package config & dependencies
├── .env              # Credentials (create your own)
├── .gitignore
└── README.md
```

## License

MIT
