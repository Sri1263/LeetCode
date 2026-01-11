import os
import math
import requests
from github import Github, Auth, InputGitTreeElement
from datetime import datetime

# ---------------- CONFIG ----------------
GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]
REPO_OWNER = os.environ["REPO_OWNER"]
REPO_NAME = os.environ["REPO_NAME"]
LEETCODE_SESSION = os.environ["LEETCODE_SESSION"]
LEETCODE_CSRF = os.environ["LEETCODE_CSRF"]
FILTER_DUPLICATE_SECS = 86400  # 1 day

# ---------------------------------------

BASE_URL = "https://leetcode.com"
HEADERS = {
    "cookie": f"LEETCODE_SESSION={LEETCODE_SESSION}; csrftoken={LEETCODE_CSRF};",
    "x-csrftoken": LEETCODE_CSRF,
    "origin": BASE_URL,
    "referer": BASE_URL,
    "content-type": "application/json",
}

LANG_EXT = {
    "python": "py",
    "python3": "py",
    "cpp": "cpp",
    "java": "java",
    "c": "c",
    "csharp": "cs",
    "javascript": "js",
    "typescript": "ts",
    "ruby": "rb",
    "go": "go",
    "rust": "rs",
    "swift": "swift",
}

def normalize_name(name):
    return name.lower().replace(" ", "_").replace("-", "_")

def fetch_submissions():
    submissions = []
    offset = 0
    while True:
        data = {
            "query": """
            query ($offset: Int!, $limit: Int!) {
              submissionList(offset: $offset, limit: $limit) {
                hasNext
                submissions {
                  id
                  title
                  titleSlug
                  statusDisplay
                  lang
                  runtime
                  memory
                  timestamp
                }
              }
            }
            """,
            "variables": {"offset": offset, "limit": 20},
        }
        r = requests.post(f"{BASE_URL}/graphql/", headers=HEADERS, json=data)
        r.raise_for_status()
        resp = r.json()
        subs = resp["data"]["submissionList"]["submissions"]
        submissions.extend([s for s in subs if s["statusDisplay"] == "Accepted"])
        if not resp["data"]["submissionList"]["hasNext"]:
            break
        offset += 20
    return submissions

def fetch_code(sub_id):
    data = {
        "query": """
        query submissionDetails($submissionId: Int!) {
          submissionDetails(submissionId: $submissionId) {
            code
          }
        }""",
        "variables": {"submissionId": sub_id},
    }
    r = requests.post(f"{BASE_URL}/graphql/", headers=HEADERS, json=data)
    r.raise_for_status()
    return r.json()["data"]["submissionDetails"]["code"]

def fetch_question(titleSlug):
    data = {
        "query": """
        query getQuestionDetail($titleSlug: String!) {
          question(titleSlug: $titleSlug) {
            content
          }
        }""",
        "variables": {"titleSlug": titleSlug},
    }
    r = requests.post(f"{BASE_URL}/graphql/", headers=HEADERS, json=data)
    r.raise_for_status()
    return r.json()["data"]["question"]["content"]

def main():
    g = Github(auth=Auth.Token(GITHUB_TOKEN))
    repo = g.get_repo(f"{REPO_OWNER}/{REPO_NAME}")

    # get last synced timestamp from commits
    commits = repo.get_commits()
    last_ts = 0
    for c in commits:
        msg = c.commit.message
        if "Time:" in msg and "Space:" in msg:
            last_ts = max(last_ts, int(c.commit.committer.date.timestamp()))
            break

    submissions = fetch_submissions()
    submissions = [s for s in submissions if int(s["timestamp"]) > last_ts]

    # sort by oldest first
    submissions.sort(key=lambda x: int(x["timestamp"]))

    parent_sha = repo.get_branch(repo.default_branch).commit.sha
    base_tree = repo.get_git_commit(parent_sha).tree

    elements = []
    solution_count = {}  # track solution_1.py, solution_2.py per problem

    for sub in submissions:
        problem_name = normalize_name(sub["title"])
        folder = f"{problem_name}"

        # solution count
        solution_count.setdefault(problem_name, 0)
        solution_count[problem_name] += 1
        sol_num = solution_count[problem_name]

        # fetch code & question content
        try:
            code = fetch_code(sub["id"])
            question_content = fetch_question(sub["titleSlug"])
        except Exception as e:
            print(f"⚠️ Skipping submission {sub['id']} – {e}")
            continue

        readme_path = f"{folder}/README.md"
        solution_path = f"{folder}/solution_{sol_num}.{LANG_EXT.get(sub['lang'].lower(),'txt')}"

        elements.append(
            InputGitTreeElement(readme_path, "100644", "blob", f"{question_content}\nProblem slug: {sub['titleSlug']}"))
        elements.append(
            InputGitTreeElement(solution_path, "100644", "blob", code+"\n"))

        commit_message = f"Time: {sub['runtime']} ({sub['runtime']}ms), Space: {sub['memory']} ({sub['memory']}MB)"

        # create tree and commit
        new_tree = repo.create_git_tree(elements, base_tree)
        parent_commit = repo.get_git_commit(parent_sha)
        commit = repo.create_git_commit(commit_message, new_tree, [parent_commit])
        repo.get_git_ref(f"heads/{repo.default_branch}").edit(commit.sha)

        # update parent_sha and base_tree for next commit
        parent_sha = commit.sha
        base_tree = new_tree.sha
        elements = []  # clear elements for next commit

        print(f"✅ Committed {folder}/solution_{sol_num}")

if __name__ == "__main__":
    main()
