import os
import math
import time
from github import Github, InputGitTreeElement

# ---------------- CONFIG ----------------
GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]
LEETCODE_CSRF = os.environ["LEETCODE_CSRF"]
LEETCODE_SESSION = os.environ["LEETCODE_SESSION"]
REPO_OWNER = os.environ["REPO_OWNER"]
REPO_NAME = os.environ["REPO_NAME"]

COMMIT_HEADER = "Sync LeetCode submission"
FILTER_DUPLICATE_SECS = 86400  # 1 day

# ---------------- UTILS ----------------
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

BASE_URL = "https://leetcode.com"


def log(msg):
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime())}] {msg}")


def pad(n):
    return str(n).zfill(4)


def normalize_name(title):
    return title.lower().replace(" ", "_").replace("/", "_")


def graphql_headers():
    return {
        "content-type": "application/json",
        "origin": BASE_URL,
        "referer": BASE_URL,
        "cookie": f"csrftoken={LEETCODE_CSRF}; LEETCODE_SESSION={LEETCODE_SESSION};",
        "x-csrftoken": LEETCODE_CSRF,
    }


# ---------------- LEETCODE API ----------------
import requests
import json


def get_submissions(offset=0, limit=20):
    query = json.dumps({
        "query": """
        query submissionList($offset: Int!, $limit: Int!) {
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
        "variables": {"offset": offset, "limit": limit}
    })
    r = requests.post(f"{BASE_URL}/graphql/", data=query, headers=graphql_headers())
    r.raise_for_status()
    return r.json()


def get_submission_detail(submission_id):
    query = json.dumps({
        "query": """
        query submissionDetails($submissionId: Int!) {
            submissionDetails(submissionId: $submissionId) {
                code
                runtimePercentile
                memoryPercentile
                question { questionId }
            }
        }""",
        "variables": {"submissionId": submission_id}
    })
    r = requests.post(f"{BASE_URL}/graphql/", data=query, headers=graphql_headers())
    r.raise_for_status()
    return r.json()["data"]["submissionDetails"]


def get_question_content(title_slug):
    query = json.dumps({
        "query": """
        query getQuestionDetail($titleSlug: String!) {
            question(titleSlug: $titleSlug) { content }
        }""",
        "variables": {"titleSlug": title_slug}
    })
    r = requests.post(f"{BASE_URL}/graphql/", data=query, headers=graphql_headers())
    r.raise_for_status()
    return r.json()["data"]["question"]["content"]


# ---------------- GITHUB ----------------
def commit_solution(repo, submission, question_content, solution_index):
    qid = submission["qid"]
    folder_name = f"{pad(qid)} {normalize_name(submission['title'])}"

    readme_path = f"{folder_name}/README.md"
    solution_file = f"{folder_name}/solution_{solution_index}.py"

    elements = [
        InputGitTreeElement(readme_path, "100644", "blob", question_content),
        InputGitTreeElement(solution_file, "100644", "blob", submission["code"] + "\n")
    ]

    parent = repo.get_commits()[0]
    # Fetch GitTree object instead of passing SHA
    base_tree = repo.get_git_tree(parent.commit.tree.sha)

    runtime = submission.get("runtime", "N/A")
    memory = submission.get("memory", "N/A")
    runtime_perc = submission.get("runtimePerc")
    memory_perc = submission.get("memoryPerc")

    if runtime_perc:
        msg = f"{COMMIT_HEADER} - Runtime: {runtime} ({runtime_perc}), Memory: {memory} ({memory_perc})"
    else:
        msg = f"{COMMIT_HEADER} - Runtime: {runtime}, Memory: {memory}"

    new_tree = repo.create_git_tree(elements, base_tree)  # <- pass GitTree object
    commit = repo.create_git_commit(msg, new_tree, [parent.commit])
    master_ref = repo.get_git_ref("heads/main")
    master_ref.edit(commit.sha)
    log(f"✅ Committed {folder_name}/solution_{solution_index}")

# ---------------- MAIN ----------------
def main():
    g = Github(GITHUB_TOKEN)
    repo = g.get_repo(f"{REPO_OWNER}/{REPO_NAME}")

    log("Fetching submissions...")
    submissions = []
    offset = 0
    submissions_dict = {}
    while True:
        data = get_submissions(offset)
        for s in data["data"]["submissionList"]["submissions"]:
            if s["statusDisplay"] != "Accepted":
                continue
            title = s["title"]
            lang = s["lang"]
            ts = int(s["timestamp"])
            key = f"{title}_{lang}"
            # Filter duplicates within 1 day
            if key in submissions_dict and ts - submissions_dict[key] < FILTER_DUPLICATE_SECS:
                continue
            submissions_dict[key] = ts
            submissions.append(s)
        if not data["data"]["submissionList"]["hasNext"]:
            break
        offset += 20

    log(f"Total accepted submissions found: {len(submissions)}")

    solution_count = {}
    for sub in reversed(submissions):  # oldest first
        details = get_submission_detail(sub["id"])
        sub["code"] = details["code"]
        sub["runtimePerc"] = details.get("runtimePercentile")
        sub["memoryPerc"] = details.get("memoryPercentile")
        sub["qid"] = details["question"]["questionId"]
        question_content = get_question_content(sub["titleSlug"])

        # Count multiple solutions per problem
        key = sub["title"]
        solution_count[key] = solution_count.get(key, 0) + 1
        commit_solution(repo, sub, question_content, solution_count[key])


if __name__ == "__main__":
    main()
