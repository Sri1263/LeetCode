import os
import requests
import base64
from github import Github, InputGitTreeElement

# ------------------- CONFIG -------------------
GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]
LEETCODE_CSRF = os.environ["LEETCODE_CSRF"]
LEETCODE_SESSION = os.environ["LEETCODE_SESSION"]
REPO_OWNER = os.environ["REPO_OWNER"]
REPO_NAME = os.environ["REPO_NAME"]
GRAPHQL_URL = "https://leetcode.com/graphql/"

headers = {
    "Content-Type": "application/json",
    "x-csrftoken": LEETCODE_CSRF,
    "cookie": f"LEETCODE_SESSION={LEETCODE_SESSION}; csrftoken={LEETCODE_CSRF}",
}

# ------------------- FETCH SUBMISSIONS -------------------
def get_submissions():
    query = """
    query getRecentSubmissions {
      allAcceptedSubmissions {
        titleSlug
        title
        timestamp
        lang
        code
        runtime
        memory
        question {
          questionId
        }
      }
    }
    """
    resp = requests.post(GRAPHQL_URL, json={"query": query}, headers=headers)
    resp.raise_for_status()
    data = resp.json()
    if "errors" in data:
        print("Error fetching submissions:", data["errors"])
        return []
    submissions = data.get("data", {}).get("allAcceptedSubmissions", [])
    # flatten questionId to top level
    for sub in submissions:
        sub["questionId"] = sub.get("question", {}).get("questionId", "")
    return submissions

# ------------------- GITHUB SETUP -------------------
g = Github(GITHUB_TOKEN)
repo = g.get_repo(f"{REPO_OWNER}/{REPO_NAME}")
latest_commit = repo.get_branch(repo.default_branch).commit
base_tree = latest_commit.commit.tree

# ------------------- COMMIT FUNCTION -------------------
def commit_solution(repo, submission, solution_index):
    # folder name: problemNumber_titleSlug
    problem_number = submission["questionId"].zfill(4)
    folder_name = f"{problem_number}_{submission['titleSlug']}"

    # files: README.md + solution_<n>.py
    readme_path = f"{folder_name}/README.md"
    readme_content = f"# {submission['title']}\nProblem slug: {submission['titleSlug']}\n"

    solution_path = f"{folder_name}/solution_{solution_index}.py"
    solution_content = submission["code"] or "# solution code not found"

    elements = [
        InputGitTreeElement(readme_path, "100644", "blob", readme_content),
        InputGitTreeElement(solution_path, "100644", "blob", solution_content),
    ]

    new_tree = repo.create_git_tree(elements, base_tree)
    commit_message = f"Runtime: {submission['runtime']}, Memory: {submission['memory']}"
    new_commit = repo.create_git_commit(commit_message, new_tree, [latest_commit.commit])
    repo.get_git_ref(f"heads/{repo.default_branch}").edit(new_commit.sha)

    print(f"✅ Committed {solution_path}")

# ------------------- MAIN -------------------
def main():
    submissions = get_submissions()
    if not submissions:
        print("No submissions found!")
        return

    # track number of solutions per problem
    solution_count = {}
    for sub in submissions:
        key = sub["titleSlug"]
        solution_count[key] = solution_count.get(key, 0) + 1
        commit_solution(repo, sub, solution_count[key])

if __name__ == "__main__":
    main()
