import sys
import gdown
import re
import traceback

# Monkey-patch gdown.download to prevent individual file errors from crashing the whole folder download
original_download = gdown.download
def safe_download(*args, **kwargs):
    try:
        return original_download(*args, **kwargs)
    except Exception as e:
        print(f"[Warning] Failed to download a file, skipping: {e}")
        return None

gdown.download = safe_download

def extract_id(url):
    # Try to match the ID in common Google Drive formats
    match = re.search(r'/folders/([^/?]+)', url)
    if match:
        return match.group(1), 'folder'
        
    match = re.search(r'/file/d/([^/?]+)', url)
    if match:
        return match.group(1), 'file'
    
    match = re.search(r'id=([^&]+)', url)
    if match:
        return match.group(1), 'unknown'
        
    return None, None

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python download.py <google_drive_url>")
        sys.exit(1)
        
    url = sys.argv[1]
    file_id, kind = extract_id(url)
    
    if not file_id:
        print(f"Error: Could not extract Google Drive File/Folder ID from URL: {url}")
        sys.exit(1)
        
    print(f"Extracted ID: {file_id}")
    
    try:
        if kind == 'folder' or 'folders' in url:
            import time
            max_retries = 5
            for attempt in range(max_retries):
                try:
                    # removing remaining_ok=True for gdown >= 6.x compatibility
                    output = gdown.download_folder(url, quiet=False, use_cookies=False)
                    if output:
                        print(f"Successfully downloaded folder contents to local directory.")
                        break
                    print(f"Attempt {attempt+1}/{max_retries} returned no files. Retrying in {(attempt+1)*5}s...")
                except Exception as e:
                    print(f"Exception during gdown download_folder (Attempt {attempt+1}/{max_retries}): {e}")
                
                if attempt < max_retries - 1:
                    time.sleep(5 * (attempt + 1))
            else:
                print("Error: gdown failed to download the folder after multiple attempts.")
                sys.exit(1)
        else:
            print("Detected File URL. Downloading single file...")
            download_url = f"https://drive.google.com/uc?id={file_id}"
            output_filename = "raw_video.mp4"
            
            import time
            max_retries = 5
            for attempt in range(max_retries):
                try:
                    output = gdown.download(download_url, output_filename, quiet=False, fuzzy=True, use_cookies=False)
                    if output:
                        print(f"Successfully downloaded to {output_filename}")
                        break
                    print(f"Attempt {attempt+1}/{max_retries} failed to download file. Retrying in {(attempt+1)*5}s...")
                except Exception as e:
                    print(f"Exception during gdown download (Attempt {attempt+1}/{max_retries}): {e}")
                
                if attempt < max_retries - 1:
                    time.sleep(5 * (attempt + 1))
            else:
                print("Error: gdown failed to download the file after multiple attempts.")
                sys.exit(1)
        
        sys.exit(0)
    except Exception as e:
        print(f"Download failed with exception: {str(e)}")
        sys.exit(1)
