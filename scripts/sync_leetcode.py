import os
import requests
from github import Github, InputGitTreeElement, Auth

GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]
LEETCODE_CSRF = os.environ["LEETCODE_CSRF"]
LEETCODE_SESSION = os.environ["LEETCODE_SESSION"]
REPO_OWNER = os.environ["REPO_OWNER"]
REPO_NAME = os.environ["REPO_NAME"]

headers = {
    "Cookie": f"LEETCODE_SESSION={LEETCODE_SESSION}; csrftoken={LEETCODE_CSRF}",
    "x-csrftoken": LEETCODE_CSRF,
    "referer": "https://leetcode.com",
}

GRAPHQL_URL = "https://leetcode.com/graphql/"

# Fetch all accepted submissions
def get_submissions():
    query = """
    query recentAcSubmissions($offset: Int!, $limit: Int!) {
      recentAcSubmissions(offset: $offset, limit: $limit) {
        titleSlug
        title
        timestamp
        lang
        code
        runtime
        memory
        questionId
      }
    }
    """
    submissions = []
    offset = 0
    limit = 50
    while True:
        resp = requests.post(GRAPHQL_URL, json={
            "query": query,
            "variables": {"offset": offset, "limit": limit}
        }, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        batch = data.get("data", {}).get("recentAcSubmissions", [])
        if not batch:
            break
        submissions.extend(batch)
        offset += limit
    return submissions

# Commit solution to GitHub
def commit_solution(repo, sub, solution_count):
    slug = sub["titleSlug"]
    qid = sub["questionId"].zfill(4)
    folder = f"{qid}_{slug}"
    code = sub.get("code")
    if not code:
        return  # Skip empty submissions
    solution_count.setdefault(slug, 0)
    solution_count[slug] += 1
    sol_file = f"solution_{solution_count[slug]}.py"

    elements = [
        InputGitTreeElement(f"{folder}/{sol_file}", "100644", "blob", code)
    ]

    # Create folder README if not exists
    readme_content = f"# {sub['title']}\nProblem slug: {slug}"
    elements.append(InputGitTreeElement(f"{folder}/README.md", "100644", "blob", readme_content))

    latest_commit = repo.get_branch(repo.default_branch).commit
    base_tree = latest_commit.commit.tree
    new_tree = repo.create_git_tree(elements, base_tree)

    commit_message = f"Runtime: {sub['runtime']}, Memory: {sub['memory']}"
    new_commit = repo.create_git_commit(commit_message, new_tree, [latest_commit.commit])
    repo.get_git_ref(f"heads/{repo.default_branch}").edit(new_commit.sha)
    print(f"✅ Committed {folder}/{sol_file}")

def main():
    g = Github(auth=Auth.Token(GITHUB_TOKEN))
    repo = g.get_repo(f"{REPO_OWNER}/{REPO_NAME}")
    submissions = get_submissions()
    print(f"[LeetCode Sync] Total accepted submissions found: {len(submissions)}")

    solution_count = {}
    for sub in submissions:
        commit_solution(repo, sub, solution_count)

if __name__ == "__main__":
    main()
