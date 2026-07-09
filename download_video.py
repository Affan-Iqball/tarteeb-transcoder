import os
import io
import sys
import argparse
import json
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

SCOPES = ['https://www.googleapis.com/auth/drive.readonly']

def get_drive_service():
    creds_json = os.environ.get('GOOGLE_SERVICE_ACCOUNT_KEY')
    if not creds_json:
        raise ValueError("GOOGLE_SERVICE_ACCOUNT_KEY environment variable not set")
    
    if creds_json.strip().startswith('/') or creds_json.strip().endswith('.json'):
        if os.path.exists(creds_json.strip()):
            with open(creds_json.strip(), 'r') as f:
                creds_json = f.read()
                
    creds_info = json.loads(creds_json)
    creds = service_account.Credentials.from_service_account_info(
        creds_info, scopes=SCOPES)
    
    return build('drive', 'v3', credentials=creds)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--file_id", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    service = get_drive_service()
    print(f"Downloading file {args.file_id} to {args.output}...")
    request = service.files().get_media(fileId=args.file_id)
    
    fh = io.FileIO(args.output, 'wb')
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while not done:
        status, done = downloader.next_chunk()
        if status:
            print(f"Download {int(status.progress() * 100)}%.")
    fh.close()
    print("Download completed.")

if __name__ == "__main__":
    main()
