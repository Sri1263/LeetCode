import os
import requests
import json
import time
import math
from github import Github, InputGitTreeElement, Auth

# ===================== CONFIG =====================
GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]
LEETCODE_CSRF = os.environ["LEETCODE_CSRF"]
LEETCODE_SESSION = os.environ["LEETCODE_SESSION"]
REPO_OWNER = os.environ["REPO_OWNER"]
REPO_NAME = os.environ["REPO_NAME"]

BASE_URL = "https://leetcode.com"
COMMIT_MESSAGE = "LeetCode Sync"

LANG_TO_EXTENSION = {
    "python": "py", "python3": "py", "cpp": "cpp", "java": "java",
    "c": "c", "csharp": "cs", "javascript": "js", "typescript": "ts",
    "ruby": "rb", "swift": "swift", "golang": "go", "kotlin": "kt",
    "rust": "rs", "php": "php", "bash": "sh"
}

# ================ HELPER FUNCTIONS =================

def log(msg):
    print(f"[LeetCode Sync] {msg}")

def pad(n):
    s = "0000" + str(n)
    return s[-4:]

def normalize_name(name):
    return name.lower().replace(" ", "_").replace("-", "_").replace("/", "_")

def graphql_headers():
    return {
        "content-type": "application/json",
        "origin": BASE_URL,
        "referer": BASE_URL,
        "cookie": f"csrftoken={LEETCODE_CSRF}; LEETCODE_SESSION={LEETCODE_SESSION};",
        "x-csrftoken": LEETCODE_CSRF
    }

def get_submissions():
    log("Fetching submissions...")
    submissions = []
    offset = 0
    while True:
        query = json.dumps({
            "query": """query ($offset: Int!, $limit: Int!) {
              submissionList(offset: $offset, limit: $limit) {
                hasNext
                submissions {
                  id
                  statusDisplay
                  lang
                  runtime
                  memory
                  timestamp
                  title
                  titleSlug
                  question { questionId }
                }
              }
            }""",
            "variables": {"offset": offset, "limit": 20}
        })
        response = requests.post(f"{BASE_URL}/graphql/", headers=graphql_headers(), data=query)
        data = response.json()
        if "data" not in data:
            log(f"Error fetching submissions: {data}")
            break
        subs = data["data"]["submissionList"]["submissions"]
        for s in subs:
            if s["statusDisplay"] == "Accepted":
                submissions.append(s)
        if not data["data"]["submissionList"]["hasNext"]:
            break
        offset += 20
        time.sleep(1)
    log(f"Total accepted submissions found: {len(submissions)}")
    return submissions

def get_problem_content(titleSlug):
    query = json.dumps({
        "query": """query getQuestionDetail($titleSlug: String!) {
          question(titleSlug: $titleSlug) { content }
        }""",
        "variables": {"titleSlug": titleSlug}
    })
    response = requests.post(f"{BASE_URL}/graphql/", headers=graphql_headers(), data=query)
    data = response.json()
    if "data" not in data or not data["data"]["question"]:
        return None
    return data["data"]["question"]["content"]

# ===================== MAIN SYNC =====================

def commit_solution(repo, latest_commit, base_tree, default_branch, sub, problem_content, solution_index):
    qid = pad(sub["question"]["questionId"])
    folder_name = f"{qid}_{normalize_name(sub['title'])}"

    # Prepare tree elements
    readme_path = f"{folder_name}/README.md"
    solution_path = f"{folder_name}/solution_{solution_index}.py"

    elements = [
        InputGitTreeElement(readme_path, "100644", "blob", problem_content or "Unable to fetch problem content."),
        InputGitTreeElement(solution_path, "100644", "blob", sub.get("code", "# solution code unavailable"))
    ]

    # Create tree
    new_tree = repo.create_git_tree(elements, base_tree)
    
    # Commit message with runtime/memory only
    commit_message = f"Runtime: {sub['runtime']}, Memory: {sub['memory']}"

    # Create commit
    commit = repo.create_git_commit(commit_message, new_tree, [latest_commit])
    # Update branch
    ref = repo.get_git_ref(f"heads/{default_branch}")
    ref.edit(commit.sha)
    log(f"✅ Committed {solution_path}")
    return commit, new_tree

def main():
    # Github auth
    g = Github(auth=Auth.Token(GITHUB_TOKEN))
    repo = g.get_repo(f"{REPO_OWNER}/{REPO_NAME}")
    default_branch = repo.default_branch

    # Latest commit
    latest_commit = repo.get_branch(default_branch).commit
    base_tree = latest_commit.commit.tree

    # Fetch submissions
    submissions = get_submissions()
    problem_count = {}  # tracks solution index per problem

    for sub in submissions:
        # skip if question missing
        if "question" not in sub or not sub["question"]:
            continue
        problem_key = sub["question"]["questionId"]
        if problem_key not in problem_count:
            problem_count[problem_key] = 1
        else:
            problem_count[problem_key] += 1

        problem_content = get_problem_content(sub["titleSlug"])
        latest_commit, base_tree = commit_solution(
            repo, latest_commit, base_tree, default_branch, sub, problem_content, problem_count[problem_key]
        )

if __name__ == "__main__":
    main()
