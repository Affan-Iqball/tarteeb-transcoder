import os
import sys
import re
import json
import argparse
import gdown

def parse_args():
    parser = argparse.ArgumentParser(description="Prepare video batch for matrix transcoding.")
    parser.add_argument("--drive_url", required=True, help="Google Drive URL")
    parser.add_argument("--request_id", required=True, help="Supabase request ID")
    parser.add_argument("--subject_slug", required=True, help="Subject slug")
    # b2_bucket is kept for CLI compatibility but not used in this step anymore
    parser.add_argument("--b2_bucket", required=False, help="Backblaze B2 bucket name (unused)")
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
    
    print(f"Fetching metadata from Google Drive: {args.drive_url}")
    file_id, kind = extract_id(args.drive_url)
    
    if not file_id:
        print(f"Error: Could not extract Google Drive ID from URL: {args.drive_url}")
        sys.exit(1)
        
    matrix_data = []
    
    if kind == 'folder' or 'folders' in args.drive_url:
        print("Folder detected. Fetching file structure instantly...")
        files = gdown.download_folder(args.drive_url, skip_download=True, use_cookies=False, quiet=False)
        if not files:
            print("No files found or unable to access folder.")
            sys.exit(1)
            
        for f in files:
            file_path = f.path
            file_id = f.id
            if file_path.lower().endswith(('.mp4', '.mkv', '.mov', '.avi')):
                rel_path_no_ext, ext = os.path.splitext(file_path)
                clean_name = re.sub(r'[^A-Za-z0-9._-]', '_', rel_path_no_ext)
                
                # Check Idempotency (Skip if playlist.m3u8 already exists on B2)
                import subprocess
                if args.b2_bucket:
                    b2_dest_dir = f"subjects/{args.subject_slug}/batch_uploads/{clean_name}"
                    ls_cmd = ["b2", "ls", f"b2://{args.b2_bucket}/{b2_dest_dir}/"]
                    ls_result = subprocess.run(ls_cmd, capture_output=True, text=True)
                    
                    if "playlist.m3u8" in ls_result.stdout:
                        print(f"Already processed, skipping {file_path}...")
                        continue
                
                matrix_data.append({
                    "clean_name": clean_name,
                    "ext": ext,
                    "file_id": file_id
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
                
    print(f"Found {len(matrix_data)} video files.")
        
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
