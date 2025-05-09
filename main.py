import os
import sys
import poplib
import smtplib
import email
from email.parser import BytesParser
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import decode_header, make_header
import logging
from typing import List, Dict, Any, Optional

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


load_dotenv()


def get_str_env_var(name: str, default: Optional[str] = None) -> Optional[str]:
    value = os.getenv(name)
    return value if value is not None else default

def get_int_env_var(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is not None and value.isdigit():
        return int(value)
    return default

def get_bool_env_var(name: str, default: bool = False) -> bool:
    value = os.getenv(name, str(default)).lower()
    return value in ('true', '1', 'yes', 'y', 'on')


EMAIL_USER = get_str_env_var("EMAIL_USER")
EMAIL_PASS = get_str_env_var("EMAIL_PASS")
POP3_SERVER = get_str_env_var("POP3_SERVER")
POP3_PORT = get_int_env_var("POP3_PORT", 995)
SMTP_SERVER = get_str_env_var("SMTP_SERVER")
SMTP_USE_SSL = get_bool_env_var("SMTP_USE_SSL", False)
SMTP_PORT_DEFAULT = 465 if SMTP_USE_SSL else 587
SMTP_PORT = get_int_env_var("SMTP_PORT", SMTP_PORT_DEFAULT)


if not all([EMAIL_USER, EMAIL_PASS, POP3_SERVER, SMTP_SERVER]):
    error_msg = "CRITICAL: Missing required environment variables (EMAIL_USER, EMAIL_PASS, POP3_SERVER, SMTP_SERVER). Server cannot start."
    logging.error(error_msg)
    sys.exit(error_msg)


def connect_pop3() -> poplib.POP3_SSL:
    try:
        logging.info(f"Connecting to POP3 server: {POP3_SERVER}:{POP3_PORT}")
        mailbox = poplib.POP3_SSL(POP3_SERVER, POP3_PORT)
        mailbox.user(EMAIL_USER)
        mailbox.pass_(EMAIL_PASS)
        logging.info("POP3 connection successful.")
        return mailbox
    except Exception as e:
        logging.error(f"POP3 connection failed: {e}")
        raise ConnectionError(f"Failed to connect to POP3 server: {e}")

def connect_smtp() -> smtplib.SMTP:
    try:
        if SMTP_USE_SSL:
            logging.info(f"Connecting to SMTP server using SMTP_SSL: {SMTP_SERVER}:{SMTP_PORT}")
            server = smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT)
            server.login(EMAIL_USER, EMAIL_PASS)
            logging.info("SMTP_SSL connection successful.")
        else:
            logging.info(f"Connecting to SMTP server using STARTTLS: {SMTP_SERVER}:{SMTP_PORT}")
            server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(EMAIL_USER, EMAIL_PASS)
            logging.info("STARTTLS connection successful.")
        return server
    except Exception as e:
        logging.error(f"SMTP connection failed (SSL={SMTP_USE_SSL}): {e}")
        raise ConnectionError(f"Failed to connect to SMTP server (SSL={SMTP_USE_SSL}): {e}")

def decode_email_header(header_value: Optional[str]) -> str:
    if header_value is None:
        return ""
    try:
        decoded_parts = decode_header(header_value)
        header_str = ""
        for part, encoding in decoded_parts:
            if isinstance(part, bytes):
                try:
                    header_str += part.decode(encoding or 'utf-8', errors='replace')
                except LookupError:
                    header_str += part.decode('utf-8', errors='replace')
            else:
                header_str += part
        return header_str
    except Exception as e:
        logging.warning(f"Could not decode header '{header_value}': {e}")
        return str(header_value)


def parse_email_message(raw_email_bytes: List[bytes]) -> Dict[str, Any]:
    parser = BytesParser()
    msg = parser.parsebytes(b'\r\n'.join(raw_email_bytes))

    headers = {
        "Subject": decode_email_header(msg.get("Subject")),
        "From": decode_email_header(msg.get("From")),
        "To": decode_email_header(msg.get("To")),
        "Cc": decode_email_header(msg.get("Cc")),
        "Date": msg.get("Date"),
        "Content-Type": msg.get("Content-Type"),
        "Message-ID": msg.get("Message-ID"),
    }

    body = ""
    html_body = None
    plain_body = None

    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get("Content-Disposition"))

            if "attachment" in content_disposition.lower():
                continue

            if part.get_payload(decode=True):
                charset = part.get_content_charset() or 'utf-8'
                try:
                    part_payload = part.get_payload(decode=True).decode(charset, errors='replace')
                except LookupError:
                    part_payload = part.get_payload(decode=True).decode('utf-8', errors='replace')

                if content_type == "text/html":
                    html_body = part_payload
                elif content_type == "text/plain":
                    plain_body = part_payload

    else:
        if msg.get_payload(decode=True):
            charset = msg.get_content_charset() or 'utf-8'
            try:
                plain_body = msg.get_payload(decode=True).decode(charset, errors='replace')
            except LookupError:
                plain_body = msg.get_payload(decode=True).decode('utf-8', errors='replace')

    body = html_body if html_body is not None else plain_body if plain_body is not None else ""

    return {"headers": headers, "body": body}


mcp = FastMCP("email-mcp-server")


@mcp.tool(description="Polls the email server for a list of all email headers, providing a summary of each email.")
def pollEmails() -> List[Dict[str, Any]]:
    """
    Retrieves a list of email headers from the POP3 server.

    This tool connects to the configured POP3 server, lists all available emails,
    and for each email, fetches basic header information such as Subject, From,
    Date, and Message-ID. It does not download the entire email body, making it
    a quick way to get an overview of the inbox.

    Returns:
        List[Dict[str, Any]]: A list of dictionaries, where each dictionary
        represents an email and contains:
            - "id" (int): The email's ID on the server.
            - "Subject" (str): The decoded subject of the email.
            - "From" (str): The decoded sender of the email.
            - "Date" (str): The date of the email.
            - "Message-ID" (str): The unique message ID of the email.
            - "error" (str, optional): If an error occurred processing this specific email.
    Raises:
        ConnectionError: If connection to the POP3 server fails.
        Exception: For other errors during the polling process.
    """
    results = []
    mailbox = None
    try:
        mailbox = connect_pop3()
        num_messages = len(mailbox.list()[1])
        logging.info(f"Found {num_messages} emails to poll.")
        for i in range(1, num_messages + 1):
            try:
                raw_header_lines = mailbox.top(i, 0)[1]
                parser = BytesParser()
                msg = parser.parsebytes(b'\r\n'.join(raw_header_lines))
                results.append({
                    "id": i,
                    "Subject": decode_email_header(msg.get("Subject")),
                    "From": decode_email_header(msg.get("From")),
                    "Date": msg.get("Date"),
                    "Message-ID": msg.get("Message-ID"),
                })
            except Exception as e:
                 logging.warning(f"Could not process header for email ID {i}: {e}")
                 results.append({
                    "id": i,
                    "error": f"Failed to parse headers for email {i}: {str(e)}"
                 })
        return results
    except Exception as e:
        logging.error(f"pollEmails tool failed: {e}")
        raise Exception(f"Failed to poll emails: {e}") from e
    finally:
        if mailbox:
            try:
                mailbox.quit()
                logging.info("POP3 connection closed after pollEmails.")
            except Exception as e:
                logging.warning(f"Error closing POP3 connection after pollEmails: {e}")


@mcp.tool(description="Retrieves the full content (headers and body) of specified emails by their server IDs.")
def getEmailsById(ids: List[int]) -> List[Dict[str, Any]]:
    """
    Fetches complete email messages (headers and body) for a given list of email IDs.

    Connects to the POP3 server and retrieves the full raw content for each valid ID
    provided in the input list. The raw email content is then parsed to extract
    headers and the body (preferring HTML over plain text if available).

    Args:
        ids (List[int]): A list of integer IDs corresponding to the emails to be fetched.
                         IDs should be 1-based and within the range of available emails
                         on the server.

    Returns:
        List[Dict[str, Any]]: A list of dictionaries, where each dictionary
        represents a fetched email or an error for a specific ID:
            - "id" (int): The requested email ID.
            - "headers" (Dict[str, str], optional): A dictionary of decoded email headers
              (e.g., "Subject", "From", "To", "Date"). Present if successful.
            - "body" (str, optional): The decoded email body (HTML if available,
              otherwise plain text). Present if successful.
            - "error" (str, optional): An error message if fetching or parsing
              the email for this ID failed, or if the ID was invalid/out of range.
    Raises:
        ValueError: If the input 'ids' is not a list.
        ConnectionError: If connection to the POP3 server fails.
        Exception: For other errors during the email retrieval process.
    """
    results = []
    mailbox = None
    if not isinstance(ids, list):
        raise ValueError("Input 'ids' must be a list of integers.")

    try:
        mailbox = connect_pop3()
        num_messages = len(mailbox.list()[1])
        processed_ids = set()

        for requested_id in ids:
            if requested_id in processed_ids: continue

            if not isinstance(requested_id, int) or not (1 <= requested_id <= num_messages):
                logging.warning(f"Invalid or out-of-range email ID requested: {requested_id}")
                results.append({"id": requested_id, "error": f"Invalid or out-of-range ID ({requested_id}). Max ID: {num_messages}"})
                processed_ids.add(requested_id)
                continue

            try:
                logging.info(f"Fetching email ID: {requested_id}")
                raw_email_lines = mailbox.retr(requested_id)[1]
                parsed_email = parse_email_message(raw_email_lines)
                results.append({
                    "id": requested_id,
                    "headers": parsed_email["headers"],
                    "body": parsed_email["body"]
                })
            except Exception as e:
                logging.warning(f"Could not retrieve or parse email ID {requested_id}: {e}")
                results.append({
                    "id": requested_id,
                    "error": f"Failed to retrieve or parse email {requested_id}: {str(e)}"
                })
            processed_ids.add(requested_id)

        return results
    except Exception as e:
        logging.error(f"getEmailsById tool failed: {e}")
        raise Exception(f"Failed to get emails by ID: {e}") from e
    finally:
        if mailbox:
            try:
                mailbox.quit()
                logging.info("POP3 connection closed after getEmailsById.")
            except Exception as e:
                logging.warning(f"Error closing POP3 connection after getEmailsById: {e}")


@mcp.tool(description="Deletes specified emails from the server by their IDs. This action is permanent after the connection is closed.")
def deleteEmailsById(ids: List[int]) -> Dict[str, Any]:
    """
    Marks specified emails for deletion from the POP3 server.

    Connects to the POP3 server and issues a DELE command for each valid email ID
    provided in the input list. The actual deletion occurs when the connection
    to the server is closed (quit command).

    Args:
        ids (List[int]): A list of integer IDs corresponding to the emails to be deleted.
                         IDs should be 1-based and within the range of available emails
                         on the server.

    Returns:
        Dict[str, Any]: A dictionary containing two lists:
            - "deleted" (List[int]): A list of IDs that were successfully marked for deletion.
            - "failed" (Dict[str, str]): A dictionary where keys are string representations
              of IDs that failed to be marked for deletion, and values are error messages.
              This includes invalid/out-of-range IDs.
    Raises:
        ValueError: If the input 'ids' is not a list.
        ConnectionError: If connection to the POP3 server fails.
        Exception: For other errors during the deletion process.
    """
    mailbox = None
    deleted_ids = []
    failed_ids = {}
    if not isinstance(ids, list):
        raise ValueError("Input 'ids' must be a list of integers.")

    try:
        mailbox = connect_pop3()
        num_messages = len(mailbox.list()[1])
        processed_ids = set()

        for requested_id in ids:
             if requested_id in processed_ids: continue

             if not isinstance(requested_id, int) or not (1 <= requested_id <= num_messages):
                 logging.warning(f"Invalid or out-of-range email ID requested for deletion: {requested_id}")
                 failed_ids[str(requested_id)] = f"Invalid or out-of-range ID ({requested_id}). Max ID: {num_messages}"
                 processed_ids.add(requested_id)
                 continue

             try:
                 logging.info(f"Marking email ID {requested_id} for deletion.")
                 mailbox.dele(requested_id)
                 deleted_ids.append(requested_id)
             except Exception as e:
                 logging.warning(f"Failed to mark email ID {requested_id} for deletion: {e}")
                 failed_ids[str(requested_id)] = str(e)
             processed_ids.add(requested_id)

        return {"deleted": deleted_ids, "failed": failed_ids}
    except Exception as e:
        logging.error(f"deleteEmailsById tool failed: {e}")
        raise Exception(f"Failed to delete emails by ID: {e}") from e
    finally:
        if mailbox:
            try:
                mailbox.quit()
                logging.info("POP3 connection closed, deletions committed.")
            except Exception as e:
                logging.warning(f"Error closing POP3 connection (deletion might be incomplete): {e}")


@mcp.tool(description="Sends a plain text email using the configured SMTP server.")
def sendTextEmail(fromAddress: str, toAddresses: List[str], subject: str, body: str) -> Dict[str, str]:
    """
    Sends a plain text email.

    Connects to the configured SMTP server and sends an email with the provided
    details. The email is sent as 'text/plain'.

    Args:
        fromAddress (str): The email address of the sender.
                           Note: Some SMTP servers may require this to match the authenticated user.
        toAddresses (List[str]): A list of recipient email addresses.
        subject (str): The subject line of the email.
        body (str): The plain text content of the email body.

    Returns:
        Dict[str, str]: A dictionary indicating the status of the send operation.
            - "status" (str): "success" if the email was sent without raising an
              immediate error from the SMTP library.
    Raises:
        ValueError: If 'toAddresses' is not a non-empty list.
        ConnectionError: If connection to the SMTP server fails.
        Exception: For other errors during the email sending process (e.g., SMTP errors).
    """
    if not isinstance(toAddresses, list) or not toAddresses:
        raise ValueError("Input 'toAddresses' must be a non-empty list.")
    if fromAddress != EMAIL_USER:
         logging.warning(f"fromAddress '{fromAddress}' may differ from authenticated user '{EMAIL_USER}'. Sending may fail depending on SMTP server policy.")

    server = None
    try:
        msg = MIMEText(body, 'plain', 'utf-8')
        msg['Subject'] = make_header(decode_header(subject))
        msg['From'] = fromAddress
        msg['To'] = ', '.join(toAddresses)

        server = connect_smtp()
        server.sendmail(fromAddress, toAddresses, msg.as_string())
        logging.info(f"Text email sent successfully to {', '.join(toAddresses)}")
        return {"status": "success"}
    except Exception as e:
        logging.error(f"sendTextEmail tool failed: {e}")
        raise Exception(f"Failed to send text email: {e}") from e
    finally:
        if server:
            try:
                server.quit()
                logging.info("SMTP connection closed after sendTextEmail.")
            except Exception as e:
                 logging.warning(f"Error closing SMTP connection after sendTextEmail: {e}")


@mcp.tool(description="Sends an HTML email using the configured SMTP server.")
def sendHtmlEmail(fromAddress: str, toAddresses: List[str], subject: str, body: str) -> Dict[str, str]:
    """
    Sends an HTML email.

    Connects to the configured SMTP server and sends an email with the provided
    details. The email is sent as 'text/html' within a multipart/alternative
    MIME structure.

    Args:
        fromAddress (str): The email address of the sender.
                           Note: Some SMTP servers may require this to match the authenticated user.
        toAddresses (List[str]): A list of recipient email addresses.
        subject (str): The subject line of the email.
        body (str): The HTML content of the email body.

    Returns:
        Dict[str, str]: A dictionary indicating the status of the send operation.
            - "status" (str): "success" if the email was sent without raising an
              immediate error from the SMTP library.
    Raises:
        ValueError: If 'toAddresses' is not a non-empty list.
        ConnectionError: If connection to the SMTP server fails.
        Exception: For other errors during the email sending process (e.g., SMTP errors).
    """
    if not isinstance(toAddresses, list) or not toAddresses:
        raise ValueError("Input 'toAddresses' must be a non-empty list.")
    if fromAddress != EMAIL_USER:
         logging.warning(f"fromAddress '{fromAddress}' may differ from authenticated user '{EMAIL_USER}'. Sending may fail depending on SMTP server policy.")

    server = None
    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = make_header(decode_header(subject))
        msg['From'] = fromAddress
        msg['To'] = ', '.join(toAddresses)

        html_part = MIMEText(body, 'html', 'utf-8')
        msg.attach(html_part)


        server = connect_smtp()
        server.sendmail(fromAddress, toAddresses, msg.as_string())
        logging.info(f"HTML email sent successfully to {', '.join(toAddresses)}")
        return {"status": "success"}
    except Exception as e:
        logging.error(f"sendHtmlEmail tool failed: {e}")
        raise Exception(f"Failed to send HTML email: {e}") from e
    finally:
        if server:
            try:
                server.quit()
                logging.info("SMTP connection closed after sendHtmlEmail.")
            except Exception as e:
                 logging.warning(f"Error closing SMTP connection after sendHtmlEmail: {e}")


if __name__ == "__main__":
    logging.info(f"Starting MCP Email Server (FastMCP) '{mcp.name}'...")
    mcp.run(transport='stdio')
    logging.info("MCP Email Server stopped.")
