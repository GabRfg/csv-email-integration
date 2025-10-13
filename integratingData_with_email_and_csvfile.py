import imaplib
import email
import pandas as pd
import pyodbc
import os
from datetime import datetime

#Estrutura para realizar integração de dados via e-mail com arquivos .csv, integra dados de faturamento 

# Email server connection details
IMAP_SERVER = 'porta do seu e-mail'
EMAIL_ACCOUNT = 'conta do seu e-mail'
EMAIL_PASSWORD = 'senha do seu e-mail'

# Conexão ao banco de dados, caso seja necessario alterar: 
# SQL Server connection details
SQL_SERVER = 'Porta IP que seu banco de dados comunica'
SQL_DATABASE = 'Nome do BD'
SQL_USERNAME = 'Username do BD'
SQL_PASSWORD = 'Senha do BD'

CURRENT_RANGE = datetime.today().replace(day=1).strftime('%Y-%m-%d')

# Directory to store attachments temporarily
caminhoAbs = os.path.abspath(__file__)
ATTACHMENTS_DIR = os.path.dirname(caminhoAbs)
os.chdir(ATTACHMENTS_DIR)
print(ATTACHMENTS_DIR)

def get_attachments_from_unread_emails():
    # Connect to the email server
    mail = imaplib.IMAP4_SSL(IMAP_SERVER)
    mail.login(EMAIL_ACCOUNT, EMAIL_PASSWORD)
    mail.select('Sua caixa de entrada alvo')

    # Search for all unread emails in the folder
    status, data = mail.search(None, 'UNSEEN')
    email_ids = data[0].split()

    attachments = []

    for email_id in email_ids:
        # Fetch the email
        status, data = mail.fetch(email_id, '(RFC822)')
        raw_email = data[0][1]

        # Parse the email
        msg = email.message_from_bytes(raw_email)

        # Iterate over email parts to find attachments
        for part in msg.walk():
            if part.get_content_disposition() == 'attachment':
                filename = part.get_filename()
                print(f"Arquivo encontrado: {filename}")

                if filename and filename.endswith('.csv') and filename.startswith('Nome do seu arquivo'):
                    unique_filename = f"{os.path.splitext(filename)[0]}_{email_id.decode()}.csv"
                    filepath = os.path.join(ATTACHMENTS_DIR, unique_filename)
                    print(f"Salvando arquivo: {filepath}")
                    with open(filepath, 'wb') as f:
                        f.write(part.get_payload(decode=True))
                    attachments.append(filepath)

        # Mark the email as read
        #Caso for integrar mais de um arquvio nas tabelas do banco, e automatizar, checar se a essa regra precisa estar comentada para não acarretar em erros 
        mail.store(email_id, '+FLAGS', '\\SEEN')

    mail.logout()
    return attachments

def process_attachment(filepath):
    # Check if the file exists before processing
    if not os.path.exists(filepath) or os.stat(filepath).st_size == 0:
        print(f"Arquivo {filepath} não encontrado ou vazio. Ignorando.")
        return pd.DataFrame()

    df = pd.read_csv(filepath, delimiter=';', encoding='utf-8')
    df = df.replace(to_replace=r"^\s*NULL\s*$", value=0, regex=True)
    df = df.fillna(0)

    if 'DATA' in df.columns:
        df['DATA'] = pd.to_datetime(df['DATA'], format='%d/%m/%Y', errors='coerce')
        df = df.dropna(subset=['DATA'])

    print(df)
    return df

def insert_into_sql(df, table_name):
    if df.empty:
        print("DataFrame está vazio. Nenhum dado será inserido.")
        return

    #Conection string feita para conectar ao SQL Server, se for outro BD, adaptar para realizar a conexão do cursor
    conn_str = f"DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={SQL_SERVER};DATABASE={SQL_DATABASE};UID={SQL_USERNAME};PWD={SQL_PASSWORD}"
    conn = pyodbc.connect(conn_str)
    cursor = conn.cursor()
    conn.commit()

    df['timestamp'] = pd.Timestamp("now")

    for index, row in df.iterrows():
        columns = ', '.join(df.columns)
        placeholders = ', '.join(['?' for _ in df.columns])
        sql = f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders})"
        cursor.execute(sql, tuple(row))
        print('Linha inserida com sucesso')

    conn.commit()
    cursor.close()
    conn.close()

if __name__ == '__main__':
    attachment_paths = get_attachments_from_unread_emails()
    print(attachment_paths)

    for filepath in attachment_paths:
        if filepath.endswith('.csv'):
            df = process_attachment(filepath)
            insert_into_sql(df, 'Sua tabela que será gravado os dados')
            timestamp = pd.Timestamp("now").strftime('%Y%m%d_%H%M%S')
            new_filename = os.path.join(ATTACHMENTS_DIR, f'old\\{os.path.basename(filepath).replace(".csv", f"_{timestamp}.csv")}')
            os.makedirs(os.path.dirname(new_filename), exist_ok=True)
            os.rename(filepath, new_filename)

    print("Data from all attachments successfully inserted into the SQL database.")