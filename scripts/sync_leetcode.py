import os
import json
import requests
import base64
from github import Github, InputGitTreeElement
import math

# ===== CONFIG =====
GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]
LEETCODE_SESSION = os.environ["LEETCODE_SESSION"]
LEETCODE_CSRF = os.environ["LEETCODE_CSRF"]
REPO_OWNER = os.environ["REPO_OWNER"]
REPO_NAME = os.environ["REPO_NAME"]
FILTER_DUPLICATE_SECS = 86400  # 1 day

# ===== HELPERS =====
def graphql_headers():
    return {
        "content-type": "application/json",
        "origin": "https://leetcode.com",
        "referer": "https://leetcode.com",
        "cookie": f"csrftoken={LEETCODE_CSRF}; LEETCODE_SESSION={LEETCODE_SESSION};",
        "x-csrftoken": LEETCODE_CSRF,
    }

def normalize_name(name):
    return name.lower().replace(" ", "_").replace("/", "_")

LANG_EXT = {
    "python3": "py", "python": "py", "cpp": "cpp", "java": "java",
    "c": "c", "csharp": "cs", "javascript": "js", "go": "go",
    "ruby": "rb", "rust": "rs", "swift": "swift", "kotlin": "kt",
}

def fetch_submissions(offset=0):
    query = {
        "query": """
        query ($offset: Int!, $limit: Int!) {
          submissionList(offset: $offset, limit: $limit) {
            hasNext
            submissions {
              id
              statusDisplay
              title
              lang
              runtime
              memory
              timestamp
              titleSlug
            }
          }
        }
        """,
        "variables": {"offset": offset, "limit": 20},
    }
    resp = requests.post("https://leetcode.com/graphql/", headers=graphql_headers(), json=query)
    resp.raise_for_status()
    return resp.json()["data"]["submissionList"]

def fetch_submission_code(sub_id):
    query = {
        "query": """
        query submissionDetails($submissionId: Int!) {
          submissionDetails(submissionId: $submissionId) {
            code
            runtimePercentile
            memoryPercentile
          }
        }
        """,
        "variables": {"submissionId": sub_id},
    }
    resp = requests.post("https://leetcode.com/graphql/", headers=graphql_headers(), json=query)
    resp.raise_for_status()
    data = resp.json()["data"]["submissionDetails"]
    return data["code"], data["runtimePercentile"], data["memoryPercentile"]

def fetch_question_content(slug):
    query = {
        "query": """
        query getQuestionDetail($titleSlug: String!) {
          question(titleSlug: $titleSlug) {
            content
          }
        }
        """,
        "variables": {"titleSlug": slug},
    }
    resp = requests.post("https://leetcode.com/graphql/", headers=graphql_headers(), json=query)
    resp.raise_for_status()
    return resp.json()["data"]["question"]["content"]

# ===== MAIN SYNC =====
def main():
    g = Github(GITHUB_TOKEN)
    repo = g.get_repo(f"{REPO_OWNER}/{REPO_NAME}")
    default_branch = repo.default_branch
    base_tree_sha = repo.get_branch(default_branch).commit.commit.tree.sha
    parent_commit = repo.get_branch(default_branch).commit.sha

    # Keep track of previously committed submissions
    committed = {}
    try:
        content = repo.get_contents("")  # root
        for file in content:
            if file.type == "dir":
                committed[file.name] = set()
    except:
        pass

    offset = 0
    submissions_all = []
    while True:
        subs = fetch_submissions(offset)
        for sub in subs["submissions"]:
            if sub["statusDisplay"] != "Accepted":
                continue
            key = normalize_name(sub["title"]) + "_" + sub["lang"]
            ts = sub["timestamp"]
            # Skip if already committed and recent
            if key in committed and ts <= max(committed[key], default=0):
                continue
            submissions_all.append(sub)
        if not subs["hasNext"]:
            break
        offset += 20

    print(f"Total accepted submissions found: {len(submissions_all)}")

    elements = []
    solution_count = {}

    for sub in submissions_all:
        problem = normalize_name(sub["title"])
        lang = sub["lang"]
        key = problem + "_" + lang

        code, runtime_perc, memory_perc = fetch_submission_code(sub["id"])
        content_md = fetch_question_content(sub["titleSlug"])
        folder_name = problem

        if key not in solution_count:
            solution_count[key] = 1
        else:
            solution_count[key] += 1

        solution_filename = f"solution_{solution_count[key]}.{LANG_EXT.get(lang, 'txt')}"
        readme_path = f"{folder_name}/README.md"
        solution_path = f"{folder_name}/{solution_filename}"

        # Create tree elements
        elements.append(InputGitTreeElement(readme_path, "100644", "blob", content_md))
        elements.append(InputGitTreeElement(solution_path, "100644", "blob", code))

        # Commit message
        msg = f"{sub['title']} - Runtime {sub['runtime']} ({runtime_perc}%), Memory {sub['memory']} ({memory_perc}%)"

        # Create tree & commit
        tree = repo.create_git_tree(elements, base_tree_sha)
        commit = repo.create_git_commit(msg, tree, [repo.get_commit(parent_commit)])
        repo.get_git_ref(f"heads/{default_branch}").edit(commit.sha)

        base_tree_sha = tree.sha
        parent_commit = commit.sha

        print(f"✅ Committed {folder_name}/{solution_filename}")

        if key not in committed:
            committed[key] = set()
        committed[key].add(sub["timestamp"])

if __name__ == "__main__":
    main()
