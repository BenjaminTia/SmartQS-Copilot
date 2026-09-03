"""One-shot HF Space deployment for Smart QS Copilot.
Token passed via env HFTOKEN (not persisted anywhere)."""
import os
import sys

token = os.environ.get("HFTOKEN", "")
if not token:
    print("NO TOKEN")
    sys.exit(1)

from huggingface_hub import HfApi

api = HfApi(token=token)
repo = "benjamintia/SmartQS-Copilot"

api.create_repo(repo, repo_type="space", space_sdk="streamlit", exist_ok=True)
print("space ready")

# DeepSeek key from local .env as masked Space secret
dk = ""
for line in open(os.path.expanduser("~/AppData/Local/hermes/.env"), encoding="utf-8", errors="ignore"):
    if line.strip().startswith("DEEPSEEK_API_KEY="):
        dk = line.strip().split("=", 1)[1].strip().strip('"').strip("'")
        break
if dk:
    api.add_space_secret(repo, "DEEPSEEK_API_KEY", dk)
    print("secret set (masked)")
else:
    print("no deepseek key found; app falls back to rule-based review")

api.upload_folder(
    repo_id=repo,
    repo_type="space",
    folder_path=".",
    ignore_patterns=[".git/*", "__pycache__/*", "*.pyc", "tests/*", "audit_correctness.py"],
)
print("upload done")
print("URL: https://huggingface.co/spaces/benjamintia/SmartQS-Copilot")
