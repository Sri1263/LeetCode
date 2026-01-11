import os
import requests
import base64
import time
from github import Github, InputGitTreeElement

# ------------------ CONFIG ------------------
GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]
REPO_OWNER = os.environ["REPO_OWNER"]
REPO_NAME = os.environ["REPO_NAME"]
LEETCODE_SESSION = os.environ["LEETCODE_SESSION"]
LEETCODE_CSRF = os.environ["LEETCODE_CSRF"]

# Folder prefix
DEST_FOLDER = ""
COMMIT_MESSAGE_PREFIX = "LeetCode Sync"

# Extensions mapping
LANG_TO_EXT = {
    "cpp": "cpp",
    "java": "java",
    "python3": "py",
    "python": "py",
    "c": "c",
    "csharp": "cs",
    "javascript": "js",
    "typescript": "ts",
    "go": "go",
    "ruby": "rb",
    "swift": "swift",
    "kotlin": "kt",
    "php": "php",
    "rust": "rs",
    # Add more if needed
}


# ------------------ HELPERS ------------------
def pad(n):
    return str(n).zfill(4)


def normalize_name(name):
    return (
        name.lower().replace(" ", "_").replace("-", "_").replace(".", "").replace(",", "")
    )


def graphql_headers():
    return {
        "content-type": "application/json",
        "cookie": f"LEETCODE_SESSION={LEETCODE_SESSION}; csrftoken={LEETCODE_CSRF}",
        "x-csrftoken": LEETCODE_CSRF,
    }


def get_submissions():
    """Fetch all accepted submissions."""
    submissions = []
    offset = 0
    limit = 20

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
                  statusDisplay
                  lang
                }
              }
            }
            """,
            "variables": {"offset": offset, "limit": limit},
        }

        resp = requests.post(
            "https://leetcode.com/graphql/", json=query, headers=graphql_headers()
        )
        data = resp.json()
        subs = data.get("data", {}).get("submissionList", {}).get("submissions", [])
        if not subs:
            break

        for s in subs:
            if s["statusDisplay"] == "Accepted":
                submissions.append(s)

        if not data.get("data", {}).get("submissionList", {}).get("hasNext", False):
            break
        offset += limit

    print(f"[LeetCode Sync] Total accepted submissions found: {len(submissions)}")
    return submissions


def get_submission_info(submission_id):
    """Fetch detailed info for a submission"""
    query = {
        "query": """
        query submissionDetails($submissionId: Int!) {
          submissionDetails(submissionId: $submissionId) {
            code
            runtime
            memory
            runtimePercentile
            memoryPercentile
            question {
              questionId
              titleSlug
            }
          }
        }
        """,
        "variables": {"submissionId": submission_id},
    }

    resp = requests.post(
        "https://leetcode.com/graphql/", json=query, headers=graphql_headers()
    )
    data = resp.json()
    details = data.get("data", {}).get("submissionDetails")
    if not details or not details.get("question"):
        print(f"[LeetCode Sync] Skipping submission {submission_id} (locked or unavailable)")
        return None

    return {
        "code": details["code"],
        "runtime": details["runtime"],
        "memory": details["memory"],
        "runtimePerc": details.get("runtimePercentile"),
        "memoryPerc": details.get("memoryPercentile"),
        "questionId": details["question"]["questionId"],
        "titleSlug": details["question"]["titleSlug"],
    }


def get_question_content(title_slug):
    """Fetch problem description"""
    query = {
        "query": """
        query getQuestionDetail($titleSlug: String!) {
          question(titleSlug: $titleSlug) {
            content
          }
        }
        """,
        "variables": {"titleSlug": title_slug},
    }

    resp = requests.post(
        "https://leetcode.com/graphql/", json=query, headers=graphql_headers()
    )
    data = resp.json()
    content = data.get("data", {}).get("question", {}).get("content")
    if not content:
        print(f"[LeetCode Sync] Skipping locked problem {title_slug}")
        return None
    return content


# ------------------ MAIN SYNC ------------------
def main():
    g = Github(GITHUB_TOKEN)
    repo = g.get_repo(f"{REPO_OWNER}/{REPO_NAME}")

    submissions = get_submissions()
    solution_count = {}

    # Get latest commit SHA & tree SHA
    default_branch = repo.default_branch
    latest_commit = repo.get_branch(default_branch).commit
    base_tree_sha = latest_commit.commit.tree.sha

    for sub in submissions:
        info = get_submission_info(sub["id"])
        if info is None:
            continue

        content = get_question_content(info["titleSlug"])
        if content is None:
            continue

        # Folder: 0009_palindrome_number
        folder_name = f"{pad(info['questionId'])}_{normalize_name(sub['title'])}"

        # Count solutions per problem
        solution_count[folder_name] = solution_count.get(folder_name, 0) + 1
        sol_index = solution_count[folder_name]

        readme_path = f"{DEST_FOLDER}{folder_name}/README.md"
        solution_file = f"{DEST_FOLDER}{folder_name}/solution_{sol_index}.{LANG_TO_EXT.get(sub['lang'], 'txt')}"

        # Prepare tree elements
        elements = [
            InputGitTreeElement(readme_path, "100644", "blob", content),
            InputGitTreeElement(solution_file, "100644", "blob", info["code"]),
        ]

        # Create tree & commit
        new_tree = repo.create_git_tree(elements, base_tree_sha)
        commit_message = f"{COMMIT_MESSAGE_PREFIX} - Runtime: {info['runtime']} ms, Memory: {info['memory']} MB"
        new_commit = repo.create_git_commit(commit_message, new_tree, [latest_commit.commit])
        repo.get_git_ref(f"heads/{default_branch}").edit(new_commit.sha)

        # Update base tree & commit for next iteration
        base_tree_sha = new_tree.sha
        latest_commit = new_commit

        print(f"[LeetCode Sync] ✅ Committed {folder_name}/solution_{sol_index}")


if __name__ == "__main__":
    main()
