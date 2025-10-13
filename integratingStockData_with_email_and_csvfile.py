import imaplib
import email
import pandas as pd
import pyodbc
import os
from datetime import datetime

#Estrutura semelhante que integra arquivos csv via email ao banco, integra informações de estoque

# Email server connection details
IMAP_SERVER = 'Colocar seu servidor Imap do e-mail'  # Replace with your IMAP server
EMAIL_ACCOUNT = 'Login do seu e-mail'
EMAIL_PASSWORD = 'Senha do e-mail'

# SQL Server connection details
# Caso for usar outro banco de dados, alterar ou acrescentar mais informações para conexão
SQL_SERVER = 'Ip que seu banco de dados comunica'
SQL_DATABASE = 'Nome do BD'
SQL_USERNAME = 'Login do BD'
SQL_PASSWORD = 'Senha do BD'

# Directory to store attachments temporarily
ATTACHMENTS_DIR = os.path.dirname(os.path.abspath(__file__))
os.makedirs(os.path.join(ATTACHMENTS_DIR, 'old'), exist_ok=True)
print("Diretório de trabalho:", ATTACHMENTS_DIR)

def get_attachments_from_unread_emails():
    #Fetch attachments from unread emails matching specific criteria.
    mail = imaplib.IMAP4_SSL(IMAP_SERVER)
    mail.login(EMAIL_ACCOUNT, EMAIL_PASSWORD)
    mail.select('Caixa alvo para integrar os arquivos')

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
                if filename and filename.startswith('ESTOQUE') and filename.endswith('.csv'):
                    unique_filename = f"{os.path.splitext(filename)[0]}_{email_id.decode()}.csv"
                    filepath = os.path.join(ATTACHMENTS_DIR, unique_filename)
                    with open(filepath, 'wb') as f:
                        f.write(part.get_payload(decode=True))
                        attachments.append(filepath)
                        print(f"Arquivo salvo: {filepath}")


      # Mark the email as read
      #Caso for integrar mais de um arquvio nas tabelas do banco, e automatizar, checar se a essa regra precisa estar comentada para não acarretar em erros 
        mail.store(email_id, '+FLAGS', "\\SEEN")

    mail.logout()
    return attachments

def process_attachment(filepath):
    #Process a CSV file into a DataFrame.
    if not os.path.exists(filepath) or os.stat(filepath).st_size == 0:
        print(f"Arquivo {filepath} não encontrado ou vazio. Ignorando.")
        return pd.DataFrame()

    df = pd.read_csv(filepath, delimiter=';', encoding='utf-8')
    df = df.replace(to_replace=r"^\s*NULL\s*$", value=0, regex=True).fillna(0)

    if 'NUMERO' in df.columns:
        df['NUMERO'] = pd.to_numeric(df['NUMERO'], errors='coerce').fillna(0)
        print("DataFrame atualizado:", df.head())

    return df

def insert_into_sql(df, table_name):
    #Insert a DataFrame into a SQL Server table.
    if df.empty:
        print("DataFrame vazio. Nenhum dado será inserido.")
        return

    #Conection string feita para conectar ao SQL Server, se for outro BD, adaptar para realizar a conexão do cursor
    conn_str = f"DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={SQL_SERVER};DATABASE={SQL_DATABASE};UID={SQL_USERNAME};PWD={SQL_PASSWORD}"
    conn = pyodbc.connect(conn_str)
    cursor = conn.cursor()

    #Regra adicionada, pois se for analisar dados de estoque, sempre precisamos de limpar a tabela antes de inserir os novos dados
    #Estoque é visto no cenário atual, não é integração incremental 
    cursor.execute(f"TRUNCATE TABLE {table_name}")
    conn.commit()

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

def move_processed_file(filepath):
    #Move a processed file to the 'old' directory with a timestamp.
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_dir = os.path.join(ATTACHMENTS_DIR, 'old')
    new_path = os.path.join(backup_dir, f"{os.path.basename(filepath).replace('.csv', f'_{timestamp}.csv')}")
    os.rename(filepath, new_path)
    print(f"Arquivo movido para: {new_path}")

if __name__ == '__main__':
    try:
        attachment_paths = get_attachments_from_unread_emails()
        print("Anexos encontrados:", attachment_paths)

        for filepath in attachment_paths:
            if filepath.endswith('.csv') and 'ESTOQUE' in filepath:
                df = process_attachment(filepath)
                insert_into_sql(df, 'Tabela alvo para integração')
                move_processed_file(filepath)

    except Exception as e:
        print("Erro:", str(e))