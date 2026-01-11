import os
import math
import requests
from github import Github, InputGitTreeElement, Auth
from datetime import datetime

# ------------------ CONFIG ------------------
GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]
LEETCODE_CSRF = os.environ["LEETCODE_CSRF"]
LEETCODE_SESSION = os.environ["LEETCODE_SESSION"]
REPO_OWNER = os.environ["REPO_OWNER"]
REPO_NAME = os.environ["REPO_NAME"]

# Constants
BASE_URL = "https://leetcode.com"
COMMIT_MESSAGE = "Sync LeetCode submission"

# Map LeetCode languages to file extensions
LANG_TO_EXTENSION = {
    "python": "py", "python3": "py", "cpp": "cpp", "java": "java",
    "javascript": "js", "c": "c", "csharp": "cs", "golang": "go",
    "ruby": "rb", "swift": "swift", "kotlin": "kt"
}

# ------------------ UTILS ------------------
def log(msg):
    print(f"[LeetCode Sync] {msg}")

def pad(n):
    s = "0000" + str(n)
    return s[-4:]

def normalize_name(name):
    return name.lower().replace(" ", "_").replace("-", "_")

def graphql_headers(session, csrf):
    return {
        "content-type": "application/json",
        "origin": BASE_URL,
        "referer": BASE_URL,
        "cookie": f"csrftoken={csrf}; LEETCODE_SESSION={session};",
        "x-csrftoken": csrf,
    }

# ------------------ GET SUBMISSIONS ------------------
def get_submissions():
    log("Fetching submissions...")
    url = BASE_URL + "/graphql/"
    query = """
    query ($offset: Int!, $limit: Int!) {
      submissionList(offset: $offset, limit: $limit) {
        hasNext
        submissions {
          id
          title
          titleSlug
          lang
          statusDisplay
          runtime
          memory
          timestamp
          question {
            questionId
          }
        }
      }
    }
    """
    offset = 0
    submissions = []
    while True:
        resp = requests.post(url, headers=graphql_headers(LEETCODE_SESSION, LEETCODE_CSRF),
                             json={"query": query, "variables": {"offset": offset, "limit": 20}})
        data = resp.json()
        for sub in data["data"]["submissionList"]["submissions"]:
            if sub["statusDisplay"] == "Accepted":
                submissions.append(sub)
        if not data["data"]["submissionList"]["hasNext"]:
            break
        offset += 20
    log(f"Total accepted submissions found: {len(submissions)}")
    return submissions

# ------------------ GET PROBLEM CONTENT ------------------
def get_problem_content(title_slug):
    url = BASE_URL + "/graphql/"
    query = """
    query getQuestionDetail($titleSlug: String!) {
      question(titleSlug: $titleSlug) {
        content
        questionId
      }
    }
    """
    resp = requests.post(url, headers=graphql_headers(LEETCODE_SESSION, LEETCODE_CSRF),
                         json={"query": query, "variables": {"titleSlug": title_slug}})
    try:
        return resp.json()["data"]["question"]["content"], resp.json()["data"]["question"]["questionId"]
    except:
        log(f"Problem locked or missing: {title_slug}")
        return None, None

# ------------------ COMMIT FUNCTION ------------------
def commit_solution(repo, submission, problem_content, solution_index):
    lang_ext = LANG_TO_EXTENSION.get(submission["lang"])
    if not lang_ext:
        log(f"Skipping {submission['title']} due to unsupported language: {submission['lang']}")
        return

    # Folder with 4-digit question ID + normalized name
    qid = pad(submission["question"]["questionId"])
    folder_name = f"{qid}_{normalize_name(submission['title'])}"

    # Files to commit
    elements = [
        InputGitTreeElement(
            path=f"{folder_name}/README.md",
            mode="100644",
            type="blob",
            content=problem_content or "Unable to fetch problem content."
        ),
        InputGitTreeElement(
            path=f"{folder_name}/solution_{solution_index}.{lang_ext}",
            mode="100644",
            type="blob",
            content=submission.get("code", "") + "\n"
        )
    ]

    # Get latest commit
    ref = repo.get_git_ref(f"heads/{repo.default_branch}")
    latest_commit = repo.get_git_commit(ref.object.sha)
    base_tree = latest_commit.tree

    # Create new tree and commit
    new_tree = repo.create_git_tree(elements, base_tree)
    commit_message = f"{COMMIT_MESSAGE} - Runtime: {submission['runtime']}, Memory: {submission['memory']}"
    new_commit = repo.create_git_commit(commit_message, new_tree, [latest_commit])
    ref.edit(new_commit.sha, force=True)
    log(f"✅ Committed {folder_name}/solution_{solution_index}.{lang_ext}")

# ------------------ MAIN ------------------
def main():
    g = Github(auth=Auth.Token(GITHUB_TOKEN))  # fixes deprecation warning
    repo = g.get_repo(f"{REPO_OWNER}/{REPO_NAME}")

    submissions = get_submissions()

    # Count solutions per problem
    solution_count = {}
    for sub in submissions:
        key = sub["titleSlug"]
        solution_count[key] = solution_count.get(key, 0) + 1
        problem_content, question_id = get_problem_content(sub["titleSlug"])
        if not problem_content:
            continue
        sub["code"] = sub.get("code", "")  # fallback
        sub["question"]["questionId"] = question_id
        commit_solution(repo, sub, problem_content, solution_count[key])

if __name__ == "__main__":
    main()
