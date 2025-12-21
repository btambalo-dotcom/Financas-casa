
# PATCH v15
import re  # <<< FIX DEFINITIVO

def sanitize_filename(base_name):
    return re.sub(r"[^A-Za-z0-9_\-]", "_", base_name)
