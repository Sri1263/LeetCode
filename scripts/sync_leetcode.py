import os
import requests
from github import Github, InputGitTreeElement
import time

# --- CONFIG ---
GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]
LEETCODE_USERNAME = os.environ.get("LEETCODE_USERNAME")
LEETCODE_CSRF = os.environ["LEETCODE_CSRF"]
LEETCODE_SESSION = os.environ["LEETCODE_SESSION"]
REPO_OWNER = os.environ["REPO_OWNER"]
REPO_NAME = os.environ["REPO_NAME"]

GRAPHQL_URL = "https://leetcode.com/graphql/"
HEADERS = {
    "Content-Type": "application/json",
    "x-csrftoken": LEETCODE_CSRF,
    "cookie": f"LEETCODE_SESSION={LEETCODE_SESSION}; csrftoken={LEETCODE_CSRF}"
}

# --- FETCH SUBMISSIONS ---
def get_submissions(username):
    query = """
    query recentAcSubmissions($username: String!) {
      submissionList(username: $username) {
        submissions {
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
    }
    """
    payload = {"query": query, "variables": {"username": username}}
    resp = requests.post(GRAPHQL_URL, headers=HEADERS, json=payload)
    resp.raise_for_status()
    data = resp.json()
    if "errors" in data:
        raise Exception(f"Error fetching submissions: {data['errors']}")
    return data["data"]["submissionList"]["submissions"]

# --- COMMIT LOGIC ---
def commit_solution(repo, sub, solution_idx):
    # Folder name: zero-padded problem number + titleSlug
    problem_number = sub.get("id").zfill(4)
    folder_name = f"{problem_number}_{sub['titleSlug']}"
    file_name = f"solution_{solution_idx}.py"
    path = f"{folder_name}/{file_name}"

    # Code content
    content = sub["code"]
    if not content.strip():
        print(f"Skipping empty solution for {folder_name}")
        return

    # Prepare tree element
    element = InputGitTreeElement(path, "100644", "blob", content)
    
    # Latest commit & tree
    latest_commit = repo.get_branch(repo.default_branch).commit
    base_tree = latest_commit.commit.tree

    new_tree = repo.create_git_tree([element], base_tree)
    commit_message = f"Runtime: {sub['runtime']} ms, Memory: {sub['memory']} MB"
    new_commit = repo.create_git_commit(commit_message, new_tree, [latest_commit.commit])
    repo.get_git_ref(f"heads/{repo.default_branch}").edit(new_commit.sha)
    print(f"✅ Committed {path}")

# --- MAIN ---
def main():
    g = Github(GITHUB_TOKEN)
    repo = g.get_repo(f"{REPO_OWNER}/{REPO_NAME}")

    submissions = get_submissions(LEETCODE_USERNAME)
    
    # Count solutions per problem
    solution_count = {}
    for sub in submissions:
        slug = sub['titleSlug']
        solution_count[slug] = solution_count.get(slug, 0) + 1
        commit_solution(repo, sub, solution_count[slug])
        time.sleep(1)  # avoid API rate limits

if __name__ == "__main__":
    main()
