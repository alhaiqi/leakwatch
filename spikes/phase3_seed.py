"""Phase 3 gate helper: commit a freshly generated FAKE AWS key on a leakwatch-e2e-* branch."""
import sys, time
sys.path[:0] = ["src", "tests"]
import fakes
from leakwatch import config
from leakwatch.gateway import Gateway
from leakwatch.github import GitHub

cfg = config.load(); repo = cfg.repos[0]
gh = GitHub(Gateway(), cfg.repos)
branch = f"leakwatch-e2e-phase3-{int(time.time())}"
gh.create_branch(repo, branch, gh.branch_sha(repo, gh.repo(repo)["default_branch"]))
content = f'import os\n\nREGION = "eu-west-1"\nAWS_ACCESS_KEY_ID = "{fakes.aws_key()}"\nTIMEOUT = 30\n'
c = gh.put_file(repo, branch, "app/settings.py", content, "phase3: add settings")
print(branch, c["commit"]["sha"])
