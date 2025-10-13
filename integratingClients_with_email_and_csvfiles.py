import imaplib
import email
import pandas as pd
import pyodbc
import os
from datetime import datetime

# Estrutura que realiza integração de clientes, via e-mail com arquivos .csv 

# Email server connection details
IMAP_SERVER = 'Imap do seu e-mail que será usado'
EMAIL_ACCOUNT = 'Login do e-mail que será usado'
EMAIL_PASSWORD = 'Senha do e-mail'

# SQL Server connection details
SQL_SERVER = 'Ip que o BD se comunica'
SQL_DATABASE = 'Nome do BD'
SQL_USERNAME = 'Username do BD'
SQL_PASSWORD = 'Senha do BD'

# Diretório de trabalho
caminhoAbs = os.path.abspath(__file__)
ATTACHMENTS_DIR = os.path.dirname(caminhoAbs)
os.chdir(ATTACHMENTS_DIR)
print("Diretório de trabalho:", ATTACHMENTS_DIR)

def get_attachments_from_unread_emails():
    mail = imaplib.IMAP4_SSL(IMAP_SERVER)
    mail.login(EMAIL_ACCOUNT, EMAIL_PASSWORD)
    mail.select('Inbox que será usada na integração')

    status, data = mail.search(None, 'UNSEEN')
    email_ids = data[0].split()
    attachments = []

    for email_id in email_ids:
        status, data = mail.fetch(email_id, '(RFC822)')
        raw_email = data[0][1]
        msg = email.message_from_bytes(raw_email)

        for part in msg.walk():
            if part.get_content_disposition() == 'attachment':
                filename = part.get_filename()
                if filename and filename.startswith('CLIENTES') and filename.endswith('.csv'):
                    unique_filename = f"{os.path.splitext(filename)[0]}_{email_id.decode()}.csv"
                    filepath = os.path.join(ATTACHMENTS_DIR, unique_filename)
                    with open(filepath, 'wb') as f:
                        f.write(part.get_payload(decode=True))
                    attachments.append(filepath)
                    print(f"Arquivo salvo: {filepath}")

        mail.store(email_id, '+FLAGS', '\\SEEN')

    mail.logout()
    return attachments

def process_attachment(filepath):
    if not os.path.exists(filepath) or os.stat(filepath).st_size == 0:
        print(f"Arquivo {filepath} não encontrado ou vazio. Ignorando.")
        return pd.DataFrame()

    df = pd.read_csv(filepath, delimiter=';', encoding='utf-8')
    df = df.replace(to_replace=r"^\s*NULL\s*$", value=0, regex=True)
    df = df.fillna(0)

    #Tratamento personalizado, caso a planilha enviada, tenha alguma coluna que precise ser tratada por erro de preenchimento
    if 'DATA' in df.columns:
        df['DATA'] = pd.to_datetime(df['DATA'], format='%d/%m/%Y', errors='coerce')
        df = df.dropna(subset=['DATA'])

    if 'NUM_ESTOQUE' in df.columns:
        df['NUM_ESTOQUE'] = pd.to_numeric(df['NUM_ESTOQUE'], errors='coerce')
        df['NUM_ESTOQUE'] = df['NUM_ESTOQUE'].fillna(0)

    return df

def insert_into_sql(df, table_name):
    if df.empty:
        print("DataFrame vazio. Nenhum dado será inserido.")
        return

    #Conection string feita para conectar ao SQL Server, se for outro BD, adaptar para realizar a conexão do cursor
    conn_str = f"DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={SQL_SERVER};DATABASE={SQL_DATABASE};UID={SQL_USERNAME};PWD={SQL_PASSWORD}"
    conn = pyodbc.connect(conn_str)
    cursor = conn.cursor()

    df['timestamp'] = pd.Timestamp("now")

    for index, row in df.iterrows():
        columns = ', '.join(df.columns)
        placeholders = ', '.join(['?' for _ in df.columns])
        sql = f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders})"
        cursor.execute(sql, tuple(row))
        print(f"Linha {index + 1} inserida com sucesso.")

    conn.commit()
    cursor.close()
    conn.close()

if __name__ == '__main__':
    try:
        attachment_paths = get_attachments_from_unread_emails()
        print("Anexos encontrados:", attachment_paths)

        for filepath in attachment_paths:
            if filepath.endswith('.csv') and 'CLIENTES' in filepath:
                df = process_attachment(filepath)
                insert_into_sql(df, 'Tabela alvo que irá gravar os dados')

                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                backup_dir = os.path.join(ATTACHMENTS_DIR, 'old')
                os.makedirs(backup_dir, exist_ok=True)
                new_path = os.path.join(backup_dir, f"{os.path.basename(filepath).replace('.csv', f'_{timestamp}.csv')}")
                os.rename(filepath, new_path)
                print(f"Arquivo movido para: {new_path}")

    except Exception as e:
        print("Erro:", str(e))