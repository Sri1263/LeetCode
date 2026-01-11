import os
import math
import time
import requests
from github import Github, InputGitTreeElement

# ----------------------- CONFIG -----------------------
GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]
LEETCODE_CSRF = os.environ["LEETCODE_CSRF"]
LEETCODE_SESSION = os.environ["LEETCODE_SESSION"]
REPO_OWNER = os.environ["REPO_OWNER"]
REPO_NAME = os.environ["REPO_NAME"]

# ----------------------- HELPERS -----------------------
LANG_TO_EXTENSION = {
    "python": "py",
    "python3": "py",
    "cpp": "cpp",
    "java": "java",
    "c": "c",
    "csharp": "cs",
    "javascript": "js",
    "typescript": "ts",
    "go": "go",
    "ruby": "rb",
    "swift": "swift",
}

def log(message):
    print(f"[LeetCode Sync] {message}")

def pad(n):
    """Pad question ID to 4 digits"""
    s = "000" + str(n)
    return s[-4:]

def normalize_name(title):
    """Convert problem title to folder-friendly name"""
    return title.lower().replace(" ", "_").replace("-", "_")

def graphql_headers(session, csrf):
    return {
        "Content-Type": "application/json",
        "Origin": "https://leetcode.com",
        "Referer": "https://leetcode.com",
        "Cookie": f"LEETCODE_SESSION={session}; csrftoken={csrf};",
        "x-csrftoken": csrf,
    }

# ----------------------- LEETCODE API -----------------------
def get_submissions(session, csrf):
    log("Fetching submissions...")
    submissions = []
    offset = 0
    while True:
        query = {
            "query": """
            query submissionList($offset: Int!, $limit: Int!) {
              submissionList(offset: $offset, limit: $limit) {
                hasNext
                submissions {
                  id
                  title
                  titleSlug
                  timestamp
                  lang
                  statusDisplay
                  runtime
                  memory
                  question {
                    questionId
                  }
                }
              }
            }""",
            "variables": {"offset": offset, "limit": 20},
        }
        resp = requests.post(
            "https://leetcode.com/graphql/",
            json=query,
            headers=graphql_headers(session, csrf),
        )
        data = resp.json()["data"]["submissionList"]
        submissions.extend(data["submissions"])
        if not data["hasNext"]:
            break
        offset += 20
        time.sleep(1)
    log(f"Total accepted submissions found: {len(submissions)}")
    return [s for s in submissions if s["statusDisplay"] == "Accepted"]

def get_question_content(titleSlug, session, csrf):
    query = {
        "query": """
        query getQuestionDetail($titleSlug: String!) {
          question(titleSlug: $titleSlug) {
            content
            questionId
          }
        }""",
        "variables": {"titleSlug": titleSlug},
    }
    resp = requests.post(
        "https://leetcode.com/graphql/",
        json=query,
        headers=graphql_headers(session, csrf),
    )
    try:
        return resp.json()["data"]["question"]["content"]
    except:
        log(f"Problem locked or failed to fetch: {titleSlug}")
        return None

# ----------------------- GITHUB COMMIT -----------------------
def commit_solution(repo, submission, question_content, solution_index):
    qid = submission.get("question", {}).get("questionId", submission.get("id", 0))
    folder_name = f"{pad(qid)} {normalize_name(submission['title'])}"

    readme_path = f"{folder_name}/README.md"
    solution_file = f"{folder_name}/solution_{solution_index}.py"

    elements = [
        InputGitTreeElement(readme_path, "100644", "blob", question_content),
        InputGitTreeElement(solution_file, "100644", "blob", submission["code"] + "\n"),
    ]

    # Latest commit and its tree
    parent_commit = repo.get_commits()[0]
    base_tree = repo.get_git_tree(parent_commit.commit.tree.sha)

    # Commit message with runtime/memory info only
    runtime = submission.get("runtime", "N/A")
    memory = submission.get("memory", "N/A")
    msg = f"Sync LeetCode - Runtime: {runtime}, Memory: {memory}"

    new_tree = repo.create_git_tree(elements, base_tree)
    commit = repo.create_git_commit(msg, new_tree, [parent_commit.commit])

    master_ref = repo.get_git_ref(f"heads/{repo.default_branch}")
    master_ref.edit(commit.sha)

    log(f"✅ Committed {folder_name}/solution_{solution_index}")

# ----------------------- MAIN -----------------------
def main():
    g = Github(GITHUB_TOKEN)
    repo = g.get_repo(f"{REPO_OWNER}/{REPO_NAME}")

    submissions = get_submissions(LEETCODE_SESSION, LEETCODE_CSRF)

    # Track solution count for each problem
    solution_count = {}

    for sub in submissions:
        key = sub["title"]
        solution_count[key] = solution_count.get(key, 0) + 1
        question_content = get_question_content(sub["titleSlug"], LEETCODE_SESSION, LEETCODE_CSRF)
        if question_content:
            commit_solution(repo, sub, question_content, solution_count[key])

if __name__ == "__main__":
    main()
