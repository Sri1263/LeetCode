import os
import json
import time
import math
import requests
from github import Github, InputGitTreeElement

BASE_URL = "https://leetcode.com"
GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]
LEETCODE_CSRF = os.environ["LEETCODE_CSRF"]
LEETCODE_SESSION = os.environ["LEETCODE_SESSION"]
REPO_OWNER = os.environ["REPO_OWNER"]
REPO_NAME = os.environ["REPO_NAME"]

COMMIT_MESSAGE = "Sync LeetCode submission"

LANG_TO_EXTENSION = {
    "bash": "sh",
    "c": "c",
    "cpp": "cpp",
    "csharp": "cs",
    "dart": "dart",
    "elixir": "ex",
    "erlang": "erl",
    "golang": "go",
    "java": "java",
    "javascript": "js",
    "kotlin": "kt",
    "mssql": "sql",
    "mysql": "sql",
    "oraclesql": "sql",
    "php": "php",
    "python": "py",
    "python3": "py",
    "pythondata": "py",
    "postgresql": "sql",
    "racket": "rkt",
    "ruby": "rb",
    "rust": "rs",
    "scala": "scala",
    "swift": "swift",
    "typescript": "ts",
}

def log(message):
    print(f"[LeetCode Sync] {message}")

def pad(n):
    s = "0000" + str(n)
    return s[-4:]

def normalize_name(problemName):
    return problemName.lower().replace(" ", "_").replace("/", "_")

def graphql_headers():
    return {
        "content-type": "application/json",
        "origin": BASE_URL,
        "referer": BASE_URL,
        "cookie": f"csrftoken={LEETCODE_CSRF}; LEETCODE_SESSION={LEETCODE_SESSION};",
        "x-csrftoken": LEETCODE_CSRF,
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

def get_problem_metadata(titleSlug):
    query = json.dumps({
        "query": """query getQuestionDetail($titleSlug: String!) {
          question(titleSlug: $titleSlug) {
            questionId
            content
          }
        }""",
        "variables": {"titleSlug": titleSlug}
    })
    response = requests.post(f"{BASE_URL}/graphql/", headers=graphql_headers(), data=query)
    data = response.json()
    if "data" in data and data["data"]["question"]:
        q = data["data"]["question"]
        return q["questionId"], q["content"]
    return None, None

from github import InputGitTreeElement

def commit_solution(repo, submission, problem_content, solution_idx):
    lang = submission["lang"]
    if lang not in LANG_TO_EXTENSION:
        log(f"Skipping {submission['title']} due to unknown lang {lang}")
        return

    qid, _ = get_problem_metadata(submission["titleSlug"])
    folder_name = f"{pad(qid)}_{normalize_name(submission['title'])}"
    solution_file = f"solution_{solution_idx}.{LANG_TO_EXTENSION[lang]}"
    readme_file = "README.md"

    elements = [
        InputGitTreeElement(f"{folder_name}/{readme_file}", "100644", "blob", problem_content),
        InputGitTreeElement(f"{folder_name}/{solution_file}", "100644", "blob", submission.get("code", "")),
    ]

    # Latest commit
    latest_commit = repo.get_branch(repo.default_branch).commit
    base_tree = latest_commit.commit.tree  # GitTree object

    # Create tree
    new_tree = repo.create_git_tree(elements, base_tree)

    # Get GitCommit object
    git_commit = repo.get_git_commit(latest_commit.sha)

    # Commit
    commit_message = f"Runtime: {submission['runtime']}, Memory: {submission['memory']}"
    new_commit = repo.create_git_commit(commit_message, new_tree, [git_commit])

    # Update branch
    repo.get_git_ref(f"heads/{repo.default_branch}").edit(new_commit.sha)

    log(f"✅ Committed {folder_name}/{solution_file}")
    
def main():
    g = Github(GITHUB_TOKEN)
    repo = g.get_repo(f"{REPO_OWNER}/{REPO_NAME}")

    submissions = get_submissions()
    # Count solutions per problem
    solution_count = {}
    for sub in submissions:
        key = normalize_name(sub["title"])
        solution_count[key] = solution_count.get(key, 0) + 1
        problem_id, content = get_problem_metadata(sub["titleSlug"])
        if not content:
            continue
        sub["code"] = ""  # Optional: fetch code if you want to include
        commit_solution(repo, sub, content, solution_count[key])

if __name__ == "__main__":
    main()
