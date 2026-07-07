import os
import sys
import re
import json
import subprocess
import argparse

def parse_args():
    parser = argparse.ArgumentParser(description="Prepare video batch for matrix transcoding.")
    parser.add_argument("--drive_url", required=True, help="Google Drive URL")
    parser.add_argument("--request_id", required=True, help="Supabase request ID")
    parser.add_argument("--subject_slug", required=True, help="Subject slug")
    parser.add_argument("--b2_bucket", required=True, help="Backblaze B2 bucket name")
    return parser.parse_args()

def main():
    args = parse_args()
    
    # 1. Create downloads folder
    os.makedirs("raw_downloads", exist_ok=True)
    
    # 2. Call download.py
    print(f"Downloading from Google Drive: {args.drive_url}")
    download_cmd = [sys.executable, "../download.py", args.drive_url]
    subprocess.run(download_cmd, cwd="raw_downloads", check=True)
    
    # 3. Find video files
    video_files = []
    for root, _, files in os.walk("raw_downloads"):
        for file in files:
            if file.lower().endswith(('.mp4', '.mkv', '.mov', '.avi')):
                video_files.append(os.path.join(root, file))
                
    print(f"Found {len(video_files)} video files.")
    
    matrix_data = []
    
    # 4. Process each video file
    for video_path in video_files:
        # Get relative path from raw_downloads/
        rel_path = os.path.relpath(video_path, "raw_downloads")
        rel_path_no_ext, ext = os.path.splitext(rel_path)
        
        # Clean relative path to get a unique, safe identifier
        clean_name = re.sub(r'[^A-Za-z0-9._-]', '_', rel_path_no_ext)
        print(f"Found file: {rel_path} -> Cleaned name: {clean_name}")
        
        # Check Idempotency (Skip if playlist.m3u8 already exists on B2)
        b2_dest_dir = f"subjects/{args.subject_slug}/batch_uploads/{clean_name}"
        ls_cmd = ["b2", "ls", f"b2://{args.b2_bucket}/{b2_dest_dir}/"]
        ls_result = subprocess.run(ls_cmd, capture_output=True, text=True)
        
        if "playlist.m3u8" in ls_result.stdout:
            print(f"Already processed, skipping {rel_path}...")
            continue
            
        # Upload raw video to temp storage on B2
        temp_b2_key = f"raw_temp/{args.request_id}/{clean_name}{ext}"
        print(f"Uploading raw file to temporary B2 storage: {temp_b2_key}")
        upload_cmd = ["b2", "upload-file", args.b2_bucket, video_path, temp_b2_key]
        subprocess.run(upload_cmd, check=True)
        
        matrix_data.append({
            "clean_name": clean_name,
            "ext": ext,
            "temp_b2_key": temp_b2_key
        })
        
    # 5. Output matrix to GITHUB_OUTPUT
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
