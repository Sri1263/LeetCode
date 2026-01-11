import os
import math
import time
import requests
from github import Github, InputGitTreeElement, Auth

# ---------------- CONFIG ----------------
GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]
LEETCODE_SESSION = os.environ["LEETCODE_SESSION"]
LEETCODE_CSRF = os.environ["LEETCODE_CSRF"]
REPO_OWNER = os.environ["REPO_OWNER"]
REPO_NAME = os.environ["REPO_NAME"]
BASE_URL = "https://leetcode.com"
# ---------------------------------------

LANG_TO_EXTENSION = {
    "python": "py",
    "python3": "py",
    "cpp": "cpp",
    "java": "java",
    "javascript": "js",
    "c": "c",
    "csharp": "cs",
    "golang": "go",
    "kotlin": "kt",
    "swift": "swift",
    "ruby": "rb",
    "php": "php",
}

def log(msg):
    print(f"[LeetCode Sync] {msg}")

def pad(n):
    s = "0000" + str(n)
    return s[-4:]

def normalize_name(name):
    return name.lower().replace(" ", "_").replace("-", "_")

def graphql_headers():
    return {
        "content-type": "application/json",
        "origin": BASE_URL,
        "referer": BASE_URL,
        "cookie": f"csrftoken={LEETCODE_CSRF}; LEETCODE_SESSION={LEETCODE_SESSION};",
        "x-csrftoken": LEETCODE_CSRF,
    }

def fetch_submissions():
    offset = 0
    submissions = []
    while True:
        graphql = {
            "query": """query ($offset: Int!, $limit: Int!) {
                submissionList(offset: $offset, limit: $limit) {
                    hasNext
                    submissions {
                        id
                        lang
                        timestamp
                        statusDisplay
                        runtime
                        memory
                        title
                        titleSlug
                    }
                }
            }""",
            "variables": {"offset": offset, "limit": 20},
        }
        r = requests.post(
            BASE_URL + "/graphql/",
            headers=graphql_headers(),
            json=graphql
        ).json()

        subs = r["data"]["submissionList"]["submissions"]
        for sub in subs:
            if sub["statusDisplay"] == "Accepted":
                submissions.append(sub)

        if not r["data"]["submissionList"]["hasNext"]:
            break
        offset += 20
        time.sleep(1)
    log(f"Total accepted submissions found: {len(submissions)}")
    return submissions

def fetch_problem_content(title_slug):
    graphql = {
        "query": """query getQuestionDetail($titleSlug: String!) {
            question(titleSlug: $titleSlug) {
                questionId
                content
            }
        }""",
        "variables": {"titleSlug": title_slug},
    }
    r = requests.post(BASE_URL + "/graphql/", headers=graphql_headers(), json=graphql).json()
    return r["data"]["question"]["content"], r["data"]["question"]["questionId"]

def commit_solution(repo, submission, problem_content, solution_index):
    title_slug = submission["titleSlug"]
    lang = submission["lang"]
    ext = LANG_TO_EXTENSION.get(lang, "txt")

    problem_content = problem_content or "Unable to fetch problem description."
    folder_name = f"{pad(submission['id'])}_{normalize_name(submission['title'])}"

    # Files
    elements = [
        InputGitTreeElement(f"{folder_name}/README.md", "100644", "blob", problem_content),
        InputGitTreeElement(f"{folder_name}/solution_{solution_index}.{ext}", "100644", "blob", submission.get("code", "")),
    ]

    # Get latest commit & tree
    default_branch = repo.default_branch
    latest_commit = repo.get_branch(default_branch).commit
    base_tree = repo.get_git_tree(latest_commit.commit.tree.sha)

    # Create new tree & commit
    new_tree = repo.create_git_tree(elements, base_tree)
    commit_msg = f"Runtime: {submission['runtime']}, Memory: {submission['memory']}"
    new_commit = repo.create_git_commit(commit_msg, new_tree, [latest_commit.commit])

    # Update branch to point to new commit
    repo.get_git_ref(f"heads/{default_branch}").edit(new_commit.sha)
    log(f"✅ Committed {folder_name}/solution_{solution_index}.{ext}")

def main():
    log("Fetching submissions...")
    submissions = fetch_submissions()

    g = Github(auth=Auth.Token(GITHUB_TOKEN))
    repo = g.get_repo(f"{REPO_OWNER}/{REPO_NAME}")

    # Track solution index per problem
    solution_count = {}

    for sub in submissions:
        key = normalize_name(sub["title"])
        solution_count[key] = solution_count.get(key, 0) + 1

        problem_content, question_id = fetch_problem_content(sub["titleSlug"])
        sub["code"] = sub.get("code", "# Solution code not fetched yet")  # Add code field if missing
        commit_solution(repo, sub, problem_content, solution_count[key])

if __name__ == "__main__":
    main()
