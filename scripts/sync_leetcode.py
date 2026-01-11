import os
import requests
import base64
from github import Github, InputGitTreeElement, GithubException, Auth

# --------- ENV VARIABLES ---------
GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]
LEETCODE_CSRF = os.environ["LEETCODE_CSRF"]
LEETCODE_SESSION = os.environ["LEETCODE_SESSION"]
REPO_OWNER = os.environ["REPO_OWNER"]
REPO_NAME = os.environ["REPO_NAME"]

# --------- CONSTANTS ---------
HEADERS = {
    "Content-Type": "application/json",
    "x-csrftoken": LEETCODE_CSRF,
    "cookie": f"LEETCODE_SESSION={LEETCODE_SESSION}; csrftoken={LEETCODE_CSRF}"
}
GRAPHQL_URL = "https://leetcode.com/graphql/"

# --------- GITHUB SETUP ---------
g = Github(auth=Auth.Token(GITHUB_TOKEN))
repo = g.get_repo(f"{REPO_OWNER}/{REPO_NAME}")
default_branch = repo.default_branch
latest_commit = repo.get_branch(default_branch).commit
base_tree = latest_commit.commit.tree

# --------- HELPER FUNCTIONS ---------
def get_submissions(limit=50):
    query = """
    query recentAcSubmissions($limit: Int!) {
      recentAcSubmissions(limit: $limit) {
        id
        title
        titleSlug
        lang
        code
        timestamp
        runtime
        memory
      }
    }
    """
    payload = {"query": query, "variables": {"limit": limit}}
    resp = requests.post(GRAPHQL_URL, headers=HEADERS, json=payload)
    resp.raise_for_status()
    data = resp.json()
    if "errors" in data:
        raise Exception(f"Error fetching submissions: {data['errors']}")
    return data["data"]["recentAcSubmissions"]

def sanitize_filename(s):
    return "".join(c if c.isalnum() or c in "_-" else "_" for c in s)

def commit_solution(submission, solution_index):
    problem_num = submission["id"].zfill(4)  # zero-padded
    folder_name = f"{problem_num}_{sanitize_filename(submission['titleSlug'])}"
    file_name = f"solution_{solution_index}.py"
    content = submission["code"]
    
    elements = [
        InputGitTreeElement(f"{folder_name}/{file_name}", "100644", "blob", content)
    ]

    # Create new tree
    new_tree = repo.create_git_tree(elements, base_tree)

    # Commit message only includes runtime/memory
    commit_message = f"Runtime: {submission['runtime']}, Memory: {submission['memory']}"
    new_commit = repo.create_git_commit(commit_message, new_tree, [latest_commit.commit])

    # Update branch
    try:
        repo.get_git_ref(f"heads/{default_branch}").edit(new_commit.sha, force=True)
    except GithubException as e:
        print(f"Warning: branch update not fast-forward, forcing: {e}")

    print(f"✅ Committed {folder_name}/{file_name}")
    return new_commit

# --------- MAIN ---------
def main():
    submissions = get_submissions()
    solution_count = {}
    
    global latest_commit, base_tree

    for sub in submissions:
        key = sub["titleSlug"]
        solution_count[key] = solution_count.get(key, 0) + 1
        latest_commit = commit_solution(sub, solution_count[key])
        base_tree = latest_commit.commit.tree

if __name__ == "__main__":
    main()
