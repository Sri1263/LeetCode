import os
import requests
import json
import math
from github import Github, InputGitTreeElement

# ---------------- CONFIG ---------------- #
GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]
LEETCODE_CSRF = os.environ["LEETCODE_CSRF"]
LEETCODE_SESSION = os.environ["LEETCODE_SESSION"]
REPO_OWNER = os.environ["REPO_OWNER"]
REPO_NAME = os.environ["REPO_NAME"]

DEST_FOLDER = ""  # Can set to "LeetCode/" or leave empty
COMMIT_MESSAGE_PREFIX = "Sync LeetCode submission"

LANG_TO_EXT = {
    "python3": "py",
    "python": "py",
    "cpp": "cpp",
    "c": "c",
    "java": "java",
    "csharp": "cs",
    "javascript": "js",
    "typescript": "ts",
    "go": "go",
    "ruby": "rb",
    "swift": "swift",
    "kotlin": "kt",
    "php": "php",
}

# ---------------- HELPERS ---------------- #
def pad(n):
    s = "0000" + str(n)
    return s[-4:]


def normalize_name(name):
    return (
        name.lower()
        .replace(" ", "_")
        .replace("-", "_")
        .replace(".", "")
        .replace("/", "_")
    )


def graphql_headers():
    return {
        "content-type": "application/json",
        "origin": "https://leetcode.com",
        "referer": "https://leetcode.com",
        "cookie": f"csrftoken={LEETCODE_CSRF}; LEETCODE_SESSION={LEETCODE_SESSION};",
        "x-csrftoken": LEETCODE_CSRF,
    }


# ---------------- FETCH SUBMISSIONS ---------------- #
def get_submissions(offset=0, limit=50):
    query = """
    query submissionList($offset: Int!, $limit: Int!) {
      submissionList(offset: $offset, limit: $limit) {
        submissions {
          id
          title
          titleSlug
          lang
          timestamp
          runtime
          memory
        }
      }
    }"""
    variables = {"offset": offset, "limit": limit}

    response = requests.post(
        "https://leetcode.com/graphql/",
        headers=graphql_headers(),
        data=json.dumps({"query": query, "variables": variables}),
    )
    data = response.json()
    if "data" not in data:
        print("[LeetCode Sync] ❌ Failed to fetch submissions", data)
        return []
    return data["data"]["submissionList"]["submissions"]


# ---------------- FETCH SUBMISSION INFO ---------------- #
def get_submission_info(submission_id):
    query = """
    query submissionDetails($submissionId: Int!) {
      submissionDetails(submissionId: $submissionId) {
        runtime
        memory
        code
        question {
          questionId
        }
      }
    }"""
    variables = {"submissionId": submission_id}

    response = requests.post(
        "https://leetcode.com/graphql/",
        headers=graphql_headers(),
        data=json.dumps({"query": query, "variables": variables}),
    )
    data = response.json()
    if "data" not in data or data["data"]["submissionDetails"] is None:
        return None
    sub = data["data"]["submissionDetails"]
    questionId = sub.get("question", {}).get("questionId", 0)
    return {
        "runtime": sub.get("runtime", 0),
        "memory": sub.get("memory", 0),
        "code": sub.get("code", ""),
        "questionId": questionId,
    }


# ---------------- FETCH QUESTION CONTENT ---------------- #
def get_question_content(title_slug):
    query = """
    query getQuestionDetail($titleSlug: String!) {
      question(titleSlug: $titleSlug) {
        content
      }
    }"""
    variables = {"titleSlug": title_slug}

    response = requests.post(
        "https://leetcode.com/graphql/",
        headers=graphql_headers(),
        data=json.dumps({"query": query, "variables": variables}),
    )
    data = response.json()
    if "data" not in data or data["data"]["question"] is None:
        return None
    return data["data"]["question"]["content"]


# ---------------- COMMIT LOGIC ---------------- #
def commit_solution(repo, sub, problem_content, solution_index):
    folder_name = f"{pad(sub['question']['questionId'])}_{normalize_name(sub['title'])}"
    readme_path = f"{DEST_FOLDER}{folder_name}/README.md"
    solution_file = f"{DEST_FOLDER}{folder_name}/solution_{solution_index}.{LANG_TO_EXT.get(sub['lang'], 'txt')}"

    elements = [
        InputGitTreeElement(readme_path, "100644", "blob", problem_content),
        InputGitTreeElement(solution_file, "100644", "blob", sub["code"]),
    ]

    # Create tree
    new_tree = repo.create_git_tree(elements, base_tree)

    commit_message = f"{COMMIT_MESSAGE_PREFIX} - Runtime: {sub['runtime']} ms, Memory: {sub['memory']} MB"

    new_commit = repo.create_git_commit(commit_message, new_tree, [latest_commit])

    repo.get_git_ref(f"heads/{default_branch}").edit(new_commit.sha)

    # Update parent tree/commit for next iteration
    global latest_commit, base_tree
    latest_commit = new_commit
    base_tree = new_tree

    print(f"[LeetCode Sync] ✅ Committed {folder_name}/solution_{solution_index}")


# ---------------- MAIN ---------------- #
if __name__ == "__main__":
    print("[LeetCode Sync] Fetching submissions...")

    g = Github(GITHUB_TOKEN)  # Works without deprecation warning
    repo = g.get_repo(f"{REPO_OWNER}/{REPO_NAME}")

    default_branch = repo.default_branch
    latest_commit = repo.get_branch(default_branch).commit
    base_tree = latest_commit.commit.tree

    submissions = get_submissions()
    print(f"[LeetCode Sync] Total accepted submissions found: {len(submissions)}")

    solution_count = {}

    for sub in submissions:
        info = get_submission_info(sub["id"])
        if info is None:
            continue
        sub.update(info)

        content = get_question_content(sub["titleSlug"])
        if content is None:
            continue

        qid = sub["questionId"]
        sub["question"] = {"questionId": qid}

        key = f"{pad(qid)}_{normalize_name(sub['title'])}"
        solution_count[key] = solution_count.get(key, 0) + 1
        commit_solution(repo, sub, content, solution_count[key])
