

import os
import shutil
import datetime

OUTPUT_DIR = "output_invoices"
OUTPUT_AUDIT_FILE = "output_audit.txt"
ARCHIVE_DIR = "archives"


def reset_output(audit_path: str = OUTPUT_AUDIT_FILE, out_dir: str = OUTPUT_DIR, archive_dir: str = ARCHIVE_DIR) -> None:
    """Archive the contents of out_dir and then remove them.

    - Creates `archive_dir` if missing.
    - Creates a zip file named `<timestamp>.zip` inside `archive_dir` containing the current contents of `out_dir`.
    - Overwrites the audit file with a short header and records the archive path and removed items.
    - Clears all files and subdirectories inside `out_dir`.
    """

    # Build archive directory name like 'Oct20#2'
    now = datetime.datetime.utcnow()
    timestamp = now.strftime("%Y%m%dT%H%M%SZ")
    month_day = now.strftime("%b%d")  # e.g. 'Oct20'
    # find next counter for this date
    os.makedirs(archive_dir, exist_ok=True)
    existing = [d for d in os.listdir(archive_dir) if os.path.isdir(os.path.join(archive_dir, d)) and d.startswith(month_day)]
    # parse suffix numbers
    counters = []
    for d in existing:
        try:
            suffix = d.split("#", 1)[1]
            counters.append(int(suffix))
        except Exception:
            continue
    next_counter = max(counters) + 1 if counters else 1
    archive_name = os.path.join(archive_dir, f"{month_day}#{next_counter}")

    # Copy contents of out_dir into archive_name directory, preserving relative paths
    if os.path.exists(archive_name):
        shutil.rmtree(archive_name)
    os.makedirs(archive_name, exist_ok=True)
    for root, dirs, files in os.walk(out_dir):
        rel_root = os.path.relpath(root, out_dir)
        target_root = archive_name if rel_root == "." else os.path.join(archive_name, rel_root)
        os.makedirs(target_root, exist_ok=True)
        for file in files:
            src = os.path.join(root, file)
            dst = os.path.join(target_root, file)
            shutil.copy2(src, dst)

    removed = []

    # Ensure output directory exists; if not, create it so the rest of the system can rely on it
    if not os.path.exists(out_dir):
        os.makedirs(out_dir, exist_ok=True)

    # Remove all files and directories inside output directory
    for name in os.listdir(out_dir):
        full_path = os.path.join(out_dir, name)
        try:
            if os.path.isfile(full_path) or os.path.islink(full_path):
                os.unlink(full_path)
                removed.append((full_path, "file"))
            elif os.path.isdir(full_path):
                shutil.rmtree(full_path)
                removed.append((full_path, "dir"))
        except Exception as e:
            # record failures in removed list as errors
            removed.append((full_path, f"error: {e}"))

    # Write audit header, archive path, and removed items
    with open(audit_path, "w", encoding="utf-8") as audit:
        audit.write("Reset performed\n")
        audit.write(f"Timestamp (UTC): {timestamp}\n")
        audit.write(f"Archive created: {archive_name}\n")
        audit.write("Removed items:\n")
        if not removed:
            audit.write("- (none)\n")
        else:
            for path, typ in removed:
                audit.write(f"- {typ}: {path}\n")


reset_output()

