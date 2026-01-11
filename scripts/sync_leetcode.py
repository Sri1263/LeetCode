import os
import requests
from github import Github, InputGitTreeElement

# ----------------- CONFIG -----------------
GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]
LEETCODE_CSRF = os.environ["LEETCODE_CSRF"]
LEETCODE_SESSION = os.environ["LEETCODE_SESSION"]
REPO_OWNER = os.environ["REPO_OWNER"]
REPO_NAME = os.environ["REPO_NAME"]

GRAPHQL_URL = "https://leetcode.com/graphql/"

HEADERS = {
    "cookie": f"LEETCODE_SESSION={LEETCODE_SESSION}; csrftoken={LEETCODE_CSRF}",
    "x-csrftoken": LEETCODE_CSRF,
    "referer": "https://leetcode.com",
}
# ------------------------------------------

def get_submissions(limit=50):
    query = """
    query recentAcSubmissions($limit: Int!) {
      recentAcSubmissionList(limit: $limit) {
        id
        title
        titleSlug
        lang
        runtime
        memory
        code
        timestamp
        questionId
      }
    }
    """
    resp = requests.post(GRAPHQL_URL, json={"query": query, "variables": {"limit": limit}}, headers=HEADERS)
    resp.raise_for_status()
    data = resp.json()
    if "errors" in data:
        print("Error fetching submissions:", data["errors"])
        return []
    return data["data"]["recentAcSubmissionList"]

def format_folder_name(sub):
    qid = str(sub["questionId"]).zfill(4)
    return f"{qid}_{sub['titleSlug']}"

def commit_solution(repo, sub, solution_count, latest_commit):
    folder_name = format_folder_name(sub)
    elements = []

    # README.md
    readme_content = f"# {sub['title']}\nProblem slug: {sub['titleSlug']}"
    elements.append(InputGitTreeElement(f"{folder_name}/README.md", "100644", "blob", readme_content))

    # Solution file
    idx = solution_count.get(sub["titleSlug"], 1)
    solution_path = f"{folder_name}/solution_{idx}.py"
    elements.append(InputGitTreeElement(solution_path, "100644", "blob", sub["code"]))
    solution_count[sub["titleSlug"]] = idx + 1

    # Create new tree
    base_tree = latest_commit.commit.tree
    new_tree = repo.create_git_tree(elements, base_tree)

    # Commit message
    commit_message = f"Runtime: {sub['runtime']}, Memory: {sub['memory']}"
    new_commit = repo.create_git_commit(commit_message, new_tree, [latest_commit])
    repo.get_git_ref(f"heads/{repo.default_branch}").edit(new_commit.sha)
    print(f"✅ Committed {solution_path}")
    return new_commit

def main():
    g = Github(GITHUB_TOKEN)
    repo = g.get_repo(f"{REPO_OWNER}/{REPO_NAME}")

    submissions = get_submissions()
    if not submissions:
        print("No submissions fetched!")
        return

    solution_count = {}
    latest_commit = repo.get_branch(repo.default_branch).commit

    for sub in submissions:
        # Skip empty code submissions
        if not sub.get("code"):
            continue
        latest_commit = commit_solution(repo, sub, solution_count, latest_commit)

if __name__ == "__main__":
    main()
