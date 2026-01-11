import os
import requests
import json
import re
from github import Github, InputGitTreeElement, Auth

# ------------------ CONFIG ------------------
GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]
LEETCODE_USERNAME = os.environ.get("LEETCODE_USERNAME", "")
LEETCODE_CSRF = os.environ["LEETCODE_CSRF"]
LEETCODE_SESSION = os.environ["LEETCODE_SESSION"]
REPO_OWNER = os.environ["REPO_OWNER"]
REPO_NAME = os.environ["REPO_NAME"]

# ------------------ GRAPHQL QUERY ------------------
SUBMISSIONS_QUERY = """
query recentAcSubmissions($username: String!) {
  recentAcSubmissionList(username: $username, limit: 100) {
    id
    title
    titleSlug
    lang
    code
    timestamp
    statusDisplay
    memory
    runtime
  }
}
"""

# ------------------ FUNCTIONS ------------------
def get_submissions(username):
    headers = {
        "Content-Type": "application/json",
        "x-csrftoken": LEETCODE_CSRF,
        "cookie": f"LEETCODE_SESSION={LEETCODE_SESSION};csrftoken={LEETCODE_CSRF}",
        "referer": "https://leetcode.com",
        "origin": "https://leetcode.com",
        "user-agent": "Mozilla/5.0",
    }
    payload = {
        "query": SUBMISSIONS_QUERY,
        "variables": {"username": username},
    }
    resp = requests.post("https://leetcode.com/graphql/", headers=headers, json=payload)
    resp.raise_for_status()
    data = resp.json()
    if "data" not in data or "recentAcSubmissionList" not in data["data"]:
        print("No submissions found or invalid response")
        return []
    return data["data"]["recentAcSubmissionList"]

def sanitize_slug(title):
    slug = title.lower().replace(" ", "_")
    slug = re.sub(r"[^a-z0-9_]", "", slug)
    return slug

def format_folder_name(index, slug):
    return f"{str(index).zfill(4)}_{slug}"

def commit_solution(repo, submission, folder_index):
    title_slug = sanitize_slug(submission["titleSlug"])
    folder_name = format_folder_name(folder_index, title_slug)

    # Only keep file extension for Python
    lang_ext = {
        "python3": "py",
        "cpp": "cpp",
        "java": "java",
        "c": "c",
    }
    ext = lang_ext.get(submission["lang"].lower(), "txt")
    solution_files = [f"solution_1.{ext}"]  # can extend to multiple solutions if needed

    # Prepare tree elements
    elements = []
    readme_content = f"# {submission['title']}\nProblem slug: {submission['titleSlug']}\n"
    elements.append(InputGitTreeElement(f"{folder_name}/README.md", "100644", "blob", readme_content))

    code_content = submission["code"]
    if not code_content.strip():
        print(f"Skipping empty code for {submission['title']}")
        return

    elements.append(InputGitTreeElement(f"{folder_name}/{solution_files[0]}", "100644", "blob", code_content))

    # Get default branch and latest commit
    ref = repo.get_git_ref(f"heads/{repo.default_branch}")
    latest_commit = repo.get_git_commit(ref.object.sha)
    base_tree = latest_commit.tree

    # Create new tree and commit
    new_tree = repo.create_git_tree(elements, base_tree)
    commit_message = f"Runtime: {submission['runtime']}, Memory: {submission['memory']}"
    new_commit = repo.create_git_commit(commit_message, new_tree, [latest_commit])

    # Update branch ref
    try:
        ref.edit(new_commit.sha)
    except Exception as e:
        print("Fast-forward failed, skipping update:", e)
        return

    print(f"✅ Committed {folder_name}/{solution_files[0]}")

# ------------------ MAIN ------------------
def main():
    submissions = get_submissions(LEETCODE_USERNAME)
    if not submissions:
        print("No accepted submissions found.")
        return

    g = Github(auth=Auth.Token(GITHUB_TOKEN))
    repo = g.get_repo(f"{REPO_OWNER}/{REPO_NAME}")

    for idx, sub in enumerate(submissions, start=1):
        commit_solution(repo, sub, idx)

if __name__ == "__main__":
    main()
