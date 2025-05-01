# MCP Email Server

This Python script implements an MCP (Model Context Protocol) server using the `mcp` library (`FastMCP`) that allows an LLM (like Claude) to interact with an email account using POP3 (for reading/deleting emails) and SMTP (for sending emails), both secured with TLS encryption. It uses `python-dotenv` to load configuration from a `.env` file.

## Features

*   **Poll Emails:** Polls the inbox for email headers (`pollEmails`).
*   **Fetch Full Emails:** Retrieves specific emails (headers and body) by ID (`getEmailsById`).
*   **Delete Emails:** Deletes specific emails by ID (`deleteEmailsById`).
*   **Send Emails:** Sends plain text (`sendTextEmail`) or HTML formatted (`sendHtmlEmail`) emails.
*   **Secure Connections:** Uses POP3 over SSL (default port 995). For SMTP, supports both STARTTLS (explicit TLS, default port 587) and direct SSL/TLS (implicit TLS, default port 465), configurable via environment variable.
*   **Configuration:** Loads credentials and server details from environment variables or a `.env` file.

## Tools Provided

The server exposes the following tools (defined using `@mcp.tool()`) to the connected LLM:

1.  **`pollEmails()`**
    *   **Description:** Returns the message ID and key headers (Subject, From, Date, Message-ID) of all emails currently in the selected mailbox.
    *   **Inputs:** None.
    *   **Returns:** `list[dict]` - A list of dictionaries, each containing `id` and headers. Example: `[{"id": 1, "Subject": "Hello", "From": "...", "Date": "...", "Message-ID": "..."}]`

2.  **`getEmailsById(ids: list)`**
    *   **Description:** Returns the full details (ID, headers, parsed body) of the specified emails. It attempts to parse the body, preferring HTML over plain text if available.
    *   **Inputs:**
        *   `ids` (`list[int]`): A list of email IDs to retrieve (IDs correspond to the order returned by `pollEmails` *at the time of polling*).
    *   **Returns:** `list[dict]` - A list of dictionaries, each containing `id`, `headers` (dict), and `body` (str). If an ID is invalid or fetching fails, an `error` key will be present. Example: `[{"id": 1, "headers": {"Subject": "..."}, "body": "..."}]`

3.  **`deleteEmailsById(ids: list)`**
    *   **Description:** Marks specified emails for deletion based on their ID. **Important:** Deleting emails invalidates the current ID sequence. It's recommended to perform deletions *after* all necessary read operations in a given session. The actual deletion occurs when the POP3 connection is closed after the command.
    *   **Inputs:**
        *   `ids` (`list[int]`): A list of email IDs to delete.
    *   **Returns:** `dict` - A dictionary indicating which IDs were marked for deletion and which failed. Example: `{"deleted": [1, 3], "failed": {2: "Error message"}}`

4.  **`sendTextEmail(fromAddress: str, toAddresses: list, subject: str, body: str)`**
    *   **Description:** Sends a plain text email via SMTP.
    *   **Inputs:**
        *   `fromAddress` (`str`): The email address to send from. *Note: Sending may fail if this doesn't match the authenticated user, depending on SMTP server policy.*
        *   `toAddresses` (`list[str]`): A list of recipient email addresses.
        *   `subject` (`str`): The email subject line.
        *   `body` (`str`): The plain text content of the email body.
    *   **Returns:** `dict` - Status indication. Example: `{"status": "success"}` or `{"error": "..."}`

5.  **`sendHtmlEmail(fromAddress: str, toAddresses: list, subject: str, body: str)`**
    *   **Description:** Sends an HTML formatted email via SMTP.
    *   **Inputs:**
        *   `fromAddress` (`str`): The email address to send from. *Note: Sending may fail if this doesn't match the authenticated user, depending on SMTP server policy.*
        *   `toAddresses` (`list[str]`): A list of recipient email addresses.
        *   `subject` (`str`): The email subject line.
        *   `body` (`str`): The HTML content of the email body.
    *   **Returns:** `dict` - Status indication. Example: `{"status": "success"}` or `{"error": "..."}`

## Setup and Installation

1.  **Prerequisites:**
    *   Python 3.12+ installed (check `pyproject.toml` for specific version, e.g., >=3.12).
    *   [uv](https://github.com/astral-sh/uv) installed (recommended for environment management and running).

2.  **Environment Setup & Dependencies:**
    *   Navigate to the `mcp_email_server` directory in your terminal.
    *   Create and activate a virtual environment using `uv`:
        ```bash
        uv venv
        source .venv/bin/activate  # Linux/macOS
        # .venv\Scripts\activate  # Windows
        ```
    *   Install dependencies using `uv` (it reads `pyproject.toml` and installs `mcp` and `python-dotenv`):
        ```bash
        uv pip install -e .
        # or 'uv pip sync' if uv.lock exists
        ```
        *(This installs the package in editable mode, which is good practice for development).*

3.  **Configuration (`.env` file):**
    *   Create a file named `.env` in the `mcp_email_server` directory.
    *   Add your email credentials and server details to this file:
        ```dotenv
        EMAIL_USER=YourEmailUsername@example.com
        EMAIL_PASS=YourEmailAppPasswordOrRegularPassword
        POP3_SERVER=pop.example.com
        POP3_PORT=995 # Optional, defaults to 995

        # SMTP Configuration (Choose ONE method: STARTTLS or SSL)
        SMTP_SERVER=smtp.example.com
        # For STARTTLS (usually port 587, default method):
        SMTP_PORT=587 # Optional, defaults to 587 if SMTP_USE_SSL is false/unset
        # SMTP_USE_SSL=false # Optional, defaults to false

        # OR For direct SSL (usually port 465):
        # SMTP_PORT=465 # Optional, defaults to 465 if SMTP_USE_SSL is true
        # SMTP_USE_SSL=true
        ```
    *   **Security:** Ensure the `.env` file is kept secure and **never** committed to version control (add `.env` to your `.gitignore` file).

4.  **Configuration (Claude Desktop):**
    *   Add this server to your Claude Desktop developer configuration file (`developer_config.json`).
    *   Replace `/path/to/mcp_email_server` with the **full, absolute path** to the `mcp_email_server` directory on your system.
    *   Note: The `env` section in the JSON is now less critical if you use a `.env` file, but it can still be used to override `.env` variables if needed.

    ```json
    {
        "mcpServers": {
            "mcp_email": {
                "command": "uv",
                "args": [
                    "--directory",
                    "/path/to/mcp_email_server",
                    "run",
                    "main.py"
                ],
                "env": {
                    # These can override .env file settings if needed
                    # "EMAIL_USER": "...",
                    # "EMAIL_PASS": "...",
                    # "POP3_SERVER": "...",
                    # "POP3_PORT": "...",
                    # "SMTP_SERVER": "...",
                    # "SMTP_PORT": "...",
                    # "SMTP_USE_SSL": "false" # or "true"
                }
            }
        }
    }
    ```

5.  **Restart Claude Desktop:** After modifying the configuration, restart Claude Desktop for the changes to take effect. The server should connect automatically.

## Important Notes

*   **.env File:** Using a `.env` file is the recommended way to manage credentials for this server.
*   **App Passwords:** If your email provider uses Two-Factor Authentication (2FA), you will likely need to generate an "App Password" specifically for this server instead of using your regular account password. Use this App Password in your `.env` file for `EMAIL_PASS`. Consult your email provider's documentation (e.g., Gmail, Outlook).
*   **Security:** Ensure the `.env` file and potentially the `developer_config.json` file are kept secure. Add `.env` to your `.gitignore`.
*   **Error Handling:** The server uses the `mcp` library's error handling. Connection errors or tool execution failures should result in appropriate MCP error responses.
*   **Email IDs:** POP3 email IDs are typically sequential numbers assigned by the server for the current session. They are only valid for the duration of that session and *will change* if emails are deleted. Use `pollEmails` to get current IDs before using `getEmailsById` or `deleteEmailsById`.
