import os
import sys
import re
import json
import argparse
import urllib.request
from google.oauth2 import service_account
from googleapiclient.discovery import build

def get_drive_service():
    creds_json = os.environ.get('GOOGLE_SERVICE_ACCOUNT_KEY')
    if not creds_json:
        print("GOOGLE_SERVICE_ACCOUNT_KEY not set")
        sys.exit(1)
    if creds_json.strip().startswith('/') or creds_json.strip().endswith('.json'):
        if os.path.exists(creds_json.strip()):
            with open(creds_json.strip(), 'r') as f:
                creds_json = f.read()
    creds_info = json.loads(creds_json)
    creds = service_account.Credentials.from_service_account_info(
        creds_info, scopes=['https://www.googleapis.com/auth/drive.readonly'])
    return build('drive', 'v3', credentials=creds)

def list_videos(service, folder_id, current_path=""):
    videos = []
    query = f"'{folder_id}' in parents and trashed = false"
    page_token = None
    while True:
        results = service.files().list(
            q=query,
            pageSize=100,
            pageToken=page_token,
            fields="nextPageToken, files(id, name, mimeType)"
        ).execute()
        
        for item in results.get('files', []):
            mime = item['mimeType']
            if mime == 'application/vnd.google-apps.folder':
                sub_path = os.path.join(current_path, item['name'])
                videos.extend(list_videos(service, item['id'], sub_path))
            else:
                name_lower = item['name'].lower()
                if name_lower.endswith(('.mp4', '.mkv', '.mov', '.avi')):
                    videos.append({
                        'id': item['id'],
                        'path': os.path.join(current_path, item['name'])
                    })
        page_token = results.get('nextPageToken')
        if not page_token:
            break
    return videos

def push_log(request_id, message):
    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not supabase_url or not supabase_key:
        return
    
    url = f"{supabase_url}/rest/v1/request_logs"
    headers = {
        "apikey": supabase_key,
        "Authorization": f"Bearer {supabase_key}",
        "Content-Type": "application/json"
    }
    data = json.dumps({"request_id": request_id, "message": message}).encode("utf-8")
    
    try:
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        with urllib.request.urlopen(req) as response:
            pass
    except Exception as e:
        print(f"Failed to push log: {e}")

def parse_args():
    parser = argparse.ArgumentParser(description="Prepare video batch for matrix transcoding.")
    parser.add_argument("--drive_url", required=True, help="Google Drive URL")
    parser.add_argument("--request_id", required=True, help="Supabase request ID")
    parser.add_argument("--subject_slug", required=True, help="Subject slug")
    parser.add_argument("--b2_bucket", required=False, help="Backblaze B2 bucket name (unused)")
    parser.add_argument("--file_ids_only", required=False, help="JSON string of specific file IDs to process")
    return parser.parse_args()

def extract_id(url):
    match = re.search(r'/folders/([^/?]+)', url)
    if match: return match.group(1), 'folder'
    match = re.search(r'/file/d/([^/?]+)', url)
    if match: return match.group(1), 'file'
    match = re.search(r'id=([^&]+)', url)
    if match: return match.group(1), 'unknown'
    return None, None

def main():
    args = parse_args()
    
    msg = f"Initializing batch pipeline. Fetching metadata from Google Drive..."
    print(msg)
    push_log(args.request_id, msg)
    
    file_id, kind = extract_id(args.drive_url)
    
    if not file_id:
        print(f"Error: Could not extract Google Drive ID from URL: {args.drive_url}")
        sys.exit(1)
        
    matrix_data = []
    
    target_file_ids = []
    if args.file_ids_only:
        try:
            target_file_ids = json.loads(args.file_ids_only)
            print(f"Targeting specific files: {target_file_ids}")
        except:
            print("Failed to parse file_ids_only JSON.")
    
    if kind == 'folder' or 'folders' in args.drive_url:
        msg = "Folder detected. Scanning files recursively..."
        print(msg)
        push_log(args.request_id, msg)
        
        service = get_drive_service()
        files = list_videos(service, file_id)
        if not files:
            print("No files found or unable to access folder.")
            sys.exit(1)
            
        for f in files:
            file_path = f['path']
            current_file_id = f['id']
            
            # If specific file IDs were requested, skip others
            if target_file_ids and current_file_id not in target_file_ids:
                continue
            
            base_name = os.path.basename(file_path)
            _, ext = os.path.splitext(base_name)
            
            # Use File ID as the unique identifier for storage
            clean_name = current_file_id
            
            # Check Idempotency (Skip if playlist.m3u8 already exists on B2 under this file ID)
            import subprocess
            if args.b2_bucket:
                b2_dest_dir = f"subjects/{args.subject_slug}/batch_uploads/{clean_name}"
                ls_cmd = ["b2", "ls", f"b2://{args.b2_bucket}/{b2_dest_dir}/"]
                ls_result = subprocess.run(ls_cmd, capture_output=True, text=True)
                
                if "playlist.m3u8" in ls_result.stdout:
                    print(f"Already processed, skipping {file_path} (ID: {clean_name})...")
                    continue
            
            matrix_data.append({
                "clean_name": clean_name,
                "ext": ext,
                "file_id": current_file_id
            })
    else:
        print("Single file detected.")
        clean_name = f"video_{args.request_id}"
        ext = ".mp4"  # Default assumption for single file without metadata
        matrix_data.append({
            "clean_name": clean_name,
            "ext": ext,
            "file_id": file_id
        })
                
    msg = f"Scan complete. Found {len(matrix_data)} video files to transcode."
    print(msg)
    push_log(args.request_id, msg)
        
    # Output matrix to GITHUB_OUTPUT
    print(f"Matrix output: {json.dumps(matrix_data)}")
    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, "a") as f:
            f.write(f"matrix={json.dumps(matrix_data)}\n")
            f.write(f"has_videos={'true' if len(matrix_data) > 0 else 'false'}\n")
    else:
        print("GITHUB_OUTPUT is not set (not running in GitHub Actions).")

if __name__ == "__main__":
    main()
