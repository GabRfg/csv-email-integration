# CSV-by-Email → SQL Server Integration

Python scripts that turn an email inbox into a data intake channel: they read unread messages, pick up CSV attachments sent by partners or other systems, clean the data and load it into SQL Server tables.

**Stack:** Python · imaplib · pandas · pyodbc · SQL Server

---

## The problem

Some sources can only deliver data as a CSV attached to an email — no API, no shared database. Someone had to download each file and import it manually. These scripts automate that path end to end.

## How it works

```
Inbox (IMAP, unread only)
   │  filter attachments by file-name prefix
   ▼
Save CSV locally ──► Clean with pandas ──► INSERT into SQL Server
   │                                              │
   └──── mark email as read                       └── move file to /old with timestamp
```

1. Connects via IMAP over SSL and searches the configured folder for `UNSEEN` messages
2. Saves only attachments matching the expected name and `.csv` extension
3. Normalizes the data: `NULL` strings and empty cells become `0`, dates are parsed from `dd/mm/yyyy`, numeric columns are coerced
4. Adds a `timestamp` column and inserts each row with **parameterized queries** (`?` placeholders)
5. Marks the email as read and archives the processed file in `old/`, so nothing is imported twice

## Scripts

| Script | Data | Load strategy |
| --- | --- | --- |
| `integratingClients_with_email_and_csvfiles.py` | Customers (`CLIENTES*.csv`) | Incremental insert |
| `integratingData_with_email_and_csvfile.py` | Billing / sales | Incremental insert |
| `integratingStockData_with_email_and_csvfile.py` | Stock (`ESTOQUE*.csv`) | **Full refresh** — truncates the table first, since stock is a snapshot of the current position, not a history |

## Setup

**Requirements:** Python 3.9+, [ODBC Driver 17 for SQL Server](https://learn.microsoft.com/sql/connect/odbc/download-odbc-driver-for-sql-server), and an email account with IMAP enabled.

```bash
pip install pandas pyodbc
```

In each script, fill in the configuration block at the top:

```python
IMAP_SERVER = 'imap.example.com'
EMAIL_ACCOUNT = 'integration@example.com'
EMAIL_PASSWORD = '...'

SQL_SERVER = '10.0.0.10'
SQL_DATABASE = 'ERP'
SQL_USERNAME = '...'
SQL_PASSWORD = '...'
```

Also set the inbox folder name, the expected file-name prefix and the target table. The CSV columns must match the table columns, separated by `;`.

```bash
python integratingClients_with_email_and_csvfiles.py
```

Designed to run on a schedule (Windows Task Scheduler or cron).

## Possible improvements

- [ ] Move credentials to environment variables / `.env`
- [ ] Merge the three scripts into one module with a config file per source
- [ ] Batch inserts (`fast_executemany`) and a single transaction per file
- [ ] Structured logging and an alert email on failure
- [ ] `requirements.txt`
