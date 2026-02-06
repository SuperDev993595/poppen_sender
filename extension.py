"""
Proxy Extension Generator for DrissionPage
Creates Chrome extension for authenticated proxy support
"""
import os
import zipfile
import time
import uuid
import json
import shutil
from pathlib import Path
from typing import List, Dict, Tuple


def create_proxy_extension(proxy_host: str, proxy_port: int, 
                          proxy_user: str = None, proxy_pass: str = None,
                          scheme: str = 'http') -> str:
    """
    Create a Chrome extension for proxy authentication.
    
    Args:
        proxy_host: Proxy server hostname/IP
        proxy_port: Proxy server port
        proxy_user: Proxy username (optional)
        proxy_pass: Proxy password (optional)
        scheme: Proxy scheme (http/https/socks5)
    
    Returns:
        Path to the generated extension directory
    """
    # Create extension directory next to this script (so you can always find it)
    base_dir = Path(__file__).resolve().parent
    extension_dir = base_dir / "temp_proxy_extensions"
    extension_dir.mkdir(exist_ok=True)
    
    # Create unique extension folder for this proxy
    # Use UUID to avoid conflicts when multiple instances run simultaneously
    unique_id = str(uuid.uuid4())[:8]
    proxy_ext_dir = extension_dir / f"proxy_ext_{proxy_port}_{unique_id}"
    
    # Try to remove existing extension if present, but handle permission errors gracefully
    if proxy_ext_dir.exists():
        try:
            # Try to remove with retry logic
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    shutil.rmtree(proxy_ext_dir)
                    break
                except PermissionError:
                    if attempt < max_retries - 1:
                        time.sleep(0.5)  # Wait a bit before retrying
                    else:
                        # If we can't delete, create a new unique directory
                        unique_id = str(uuid.uuid4())[:8]
                        proxy_ext_dir = extension_dir / f"proxy_ext_{proxy_port}_{unique_id}"
                        print(f"[WARNING] Could not remove existing extension, using new directory: {proxy_ext_dir}")
        except Exception as e:
            # If deletion fails, use a new unique directory
            unique_id = str(uuid.uuid4())[:8]
            proxy_ext_dir = extension_dir / f"proxy_ext_{proxy_port}_{unique_id}"
            print(f"[WARNING] Error removing extension directory, using new one: {e}")
    
    proxy_ext_dir.mkdir(exist_ok=True, parents=True)
    
    # Manifest V2 required: Chrome MV3 does not support blocking onAuthRequired (dialog cannot be bypassed)
    manifest = {
        "manifest_version": 2,
        "name": "UltraMars Proxy Auth Extension",
        "version": "1.0",
        "permissions": [
            "proxy",
            "webRequest",
            "webRequestBlocking",
            "<all_urls>"
        ],
        "background": {
            "scripts": ["background.js"],
            "persistent": True
        }
    }
    
    def js_escape(s):
        if s is None:
            return ""
        return str(s).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\r", "\\r")
    safe_user = js_escape(proxy_user) if proxy_user else ""
    safe_pass = js_escape(proxy_pass) if proxy_pass else ""
    
    # background.js - onAuthRequired (blocking) + Proxy-Authorization; MV2 so dialog is bypassed
    if proxy_user and proxy_pass:
        background_js = f"""
const PROXY_USER = "{safe_user}";
const PROXY_PASS = "{safe_pass}";
chrome.runtime.onInstalled.addListener(() => {{
  const config = {{
    mode: "fixed_servers",
    rules: {{
      singleProxy: {{
        scheme: "http",
        host: "{proxy_host}",
        port: {proxy_port}
      }},
      bypassList: ["localhost"]
    }}
  }};
  chrome.proxy.settings.set({{value: config, scope: "regular"}}, () => {{}});
}});

chrome.webRequest.onAuthRequired.addListener(
  (details) => {{
    return {{
      authCredentials: {{
        username: PROXY_USER,
        password: PROXY_PASS
      }}
    }};
  }},
  {{urls: ["<all_urls>"]}},
  ["blocking"]
);

chrome.webRequest.onBeforeSendHeaders.addListener(
  (details) => {{
    const headers = details.requestHeaders || [];
    headers.push({{
      name: 'Proxy-Authorization',
      value: 'Basic ' + btoa(PROXY_USER + ':' + PROXY_PASS)
    }});
    return {{requestHeaders: headers}};
  }},
  {{urls: ["<all_urls>"]}},
  ["blocking", "requestHeaders"]
);
"""
    else:
        background_js = """// No proxy authentication needed
console.log("Proxy extension loaded (no auth required)");
"""
    
    # Write files
    manifest_path = proxy_ext_dir / "manifest.json"
    background_path = proxy_ext_dir / "background.js"
    
    with open(manifest_path, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2)
    
    with open(background_path, 'w', encoding='utf-8') as f:
        f.write(background_js)
    
    # Return absolute path as string
    ext_path = str(proxy_ext_dir.absolute())
    
    # Verify files were created
    if not manifest_path.exists() or not background_path.exists():
        raise Exception(f"Failed to create extension files in {ext_path}")
    
    print(f"[DEBUG] Proxy extension created at: {ext_path}")
    print(f"[DEBUG] manifest.json exists: {manifest_path.exists()}")
    print(f"[DEBUG] background.js exists: {background_path.exists()}")
    
    return ext_path


def parse_proxy(proxy_string: str) -> Dict[str, str]:
    """
    Parse a proxy string in format: username:password@host:port
    
    Args:
        proxy_string: Proxy string in format username:password@host:port
    
    Returns:
        Dictionary with keys: username, password, host, port
    
    Raises:
        ValueError: If proxy format is invalid
    """
    proxy_string = proxy_string.strip()
    
    if "@" in proxy_string:
        # Format: username:password@host:port
        auth_part, server_part = proxy_string.split("@", 1)
        if ":" not in auth_part:
            raise ValueError(f"Invalid proxy format: missing username:password in {proxy_string}")
        
        username, password = auth_part.split(":", 1)
        if ":" not in server_part:
            raise ValueError(f"Invalid proxy format: missing host:port in {proxy_string}")
        
        host, port = server_part.rsplit(":", 1)
        
        return {
            "username": auth_part,
            "password": "",
            "host": host,
            "port": port
        }
    else:
        # Try old format: host:port:username:password
        parts = proxy_string.split(":")
        if len(parts) >= 4:
            return {
                "host": parts[0],
                "port": parts[1],
                "username": parts[2],
                "password": parts[3]
            }
        else:
            raise ValueError(f"Invalid proxy format: {proxy_string}")


def analyze_proxy_list(file_path: str = "proxys.txt") -> Dict:
    """
    Analyze proxy list from file.
    
    Args:
        file_path: Path to proxy list file
    
    Returns:
        Dictionary with analysis results:
        - total: Total number of proxies
        - valid: Number of valid proxies
        - invalid: List of invalid proxy strings
        - proxies: List of parsed proxy dictionaries
    """
    results = {
        "total": 0,
        "valid": 0,
        "invalid": [],
        "proxies": []
    }
    
    if not os.path.exists(file_path):
        print(f"[WARNING] Proxy file not found: {file_path}")
        return results
    
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    results["total"] = len(lines)
    
    for line_num, line in enumerate(lines, 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        
        try:
            parsed = parse_proxy(line)
            results["proxies"].append(parsed)
            results["valid"] += 1
        except ValueError as e:
            results["invalid"].append({
                "line": line_num,
                "proxy": line,
                "error": str(e)
            })
    
    print(f"[INFO] Proxy Analysis:")
    print(f"  Total proxies: {results['total']}")
    print(f"  Valid proxies: {results['valid']}")
    print(f"  Invalid proxies: {len(results['invalid'])}")
    
    if results["invalid"]:
        print(f"\n[WARNING] Invalid proxies found:")
        for inv in results["invalid"]:
            print(f"  Line {inv['line']}: {inv['proxy']} - {inv['error']}")
    
    return results


def proxies(username: str, password: str, endpoint: str, port: str) -> str:
    """
    Create proxy extension and return path to its zip (for add_extension).
    Loading as zip via add_extension is more reliable than --load-extension for auth.
    """
    port_int = int(port) if isinstance(port, str) else port
    ext_dir = create_proxy_extension(
        proxy_host=endpoint,
        proxy_port=port_int,
        proxy_user=username,
        proxy_pass=password,
        scheme='http'
    )
    ext_path = Path(ext_dir)
    zip_path = ext_path.parent / f"{ext_path.name}.zip"
    if zip_path.exists():
        try:
            zip_path.unlink()
        except PermissionError:
            zip_path = ext_path.parent / f"{ext_path.name}_{uuid.uuid4().hex[:8]}.zip"
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for f in ext_path.rglob('*'):
            if f.is_file():
                zipf.write(f, f.relative_to(ext_path))
    print(f"[DEBUG] Proxy extension zip: {zip_path}")
    return str(zip_path.resolve())


def cleanup_proxy_extensions(force: bool = False):
    """
    Remove all temporary proxy extension directories.
    
    Args:
        force: If True, will attempt to remove even if permission errors occur
    """
    extension_dir = Path("temp_proxy_extensions")
    if extension_dir.exists():
        try:
            shutil.rmtree(extension_dir)
            print("[INFO] Cleaned up proxy extension directories")
        except PermissionError as e:
            if force:
                print(f"[WARNING] Could not remove some extension directories (may be in use): {e}")
            else:
                print(f"[INFO] Some extension directories are in use, skipping cleanup: {e}")
        except Exception as e:
            print(f"[WARNING] Error during cleanup: {e}")


def cleanup_old_extensions(max_age_hours: int = 24):
    """
    Clean up old extension directories that are older than max_age_hours.
    This helps prevent accumulation of old extension directories.
    
    Args:
        max_age_hours: Maximum age in hours before cleanup (default: 24)
    """
    extension_dir = Path("temp_proxy_extensions")
    if not extension_dir.exists():
        return
    
    current_time = time.time()
    max_age_seconds = max_age_hours * 3600
    cleaned_count = 0
    failed_count = 0
    
    for ext_path in extension_dir.iterdir():
        if ext_path.is_dir():
            try:
                # Check if directory is old enough
                mtime = ext_path.stat().st_mtime
                if current_time - mtime > max_age_seconds:
                    shutil.rmtree(ext_path)
                    cleaned_count += 1
            except PermissionError:
                # Directory might be in use, skip it
                failed_count += 1
            except Exception as e:
                print(f"[WARNING] Error cleaning up {ext_path}: {e}")
                failed_count += 1
    
    if cleaned_count > 0:
        print(f"[INFO] Cleaned up {cleaned_count} old extension directories")
    if failed_count > 0:
        print(f"[INFO] Skipped {failed_count} extension directories (may be in use)")
