import os
import requests
from github import Github, Auth
from datetime import datetime
import time

# ---------------- CONFIG ----------------
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
LEETCODE_CSRF = os.environ.get("LEETCODE_CSRF_TOKEN")
LEETCODE_SESSION = os.environ.get("LEETCODE_SESSION")
REPO_OWNER = os.environ.get("REPO_OWNER")
REPO_NAME = os.environ.get("REPO_NAME")
FILTER_DUPLICATE_SECS = 86400  # 1 day
# ---------------------------------------

HEADERS = {
    "content-type": "application/json",
    "origin": "https://leetcode.com",
    "referer": "https://leetcode.com",
    "cookie": f"csrftoken={LEETCODE_CSRF}; LEETCODE_SESSION={LEETCODE_SESSION};",
    "x-csrftoken": LEETCODE_CSRF,
}

LANG_EXT = {
    "python": "py",
    "python3": "py",
    "cpp": "cpp",
    "c": "c",
    "java": "java",
    "javascript": "js",
    "csharp": "cs",
    "ruby": "rb",
    "golang": "go",
    "kotlin": "kt",
}

def normalize_name(title):
    return "".join(c if c.isalnum() else "-" for c in title.lower())

def get_all_submissions():
    offset = 0
    submissions = []
    while True:
        query = {
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
            }""",
            "variables": {"offset": offset, "limit": 20},
        }
        r = requests.post("https://leetcode.com/graphql/", json=query, headers=HEADERS)
        r.raise_for_status()
        data = r.json()["data"]["submissionList"]
        subs = [s for s in data["submissions"] if s["statusDisplay"] == "Accepted"]
        submissions.extend(subs)
        if not data["hasNext"]:
            break
        offset += 20
        time.sleep(1)  # avoid rate limits
    return submissions

def get_submission_code(sub_id):
    query = {
        "query": """
        query submissionDetails($id: Int!) {
            submissionDetails(submissionId: $id) {
                code
            }
        }""",
        "variables": {"id": sub_id},
    }
    r = requests.post("https://leetcode.com/graphql/", json=query, headers=HEADERS)
    r.raise_for_status()
    return r.json()["data"]["submissionDetails"]["code"]

def get_problem_content(slug):
    query = {
        "query": """
        query getQuestionDetail($titleSlug: String!) {
            question(titleSlug: $titleSlug) { content }
        }""",
        "variables": {"titleSlug": slug},
    }
    r = requests.post("https://leetcode.com/graphql/", json=query, headers=HEADERS)
    r.raise_for_status()
    return r.json()["data"]["question"]["content"]

# ------------------ MAIN ------------------
def main():
    g = Github(auth=Auth.Token(GITHUB_TOKEN))
    repo = g.get_repo(f"{REPO_OWNER}/{REPO_NAME}")

    submissions = get_all_submissions()
    print(f"Total accepted submissions found: {len(submissions)}")

    # Fetch last commit time to avoid duplicates
    commits = list(repo.get_commits())
    last_commit_time = datetime.min
    if commits:
        last_commit_time = commits[0].commit.committer.date

    problem_counter = {}

    for sub in reversed(submissions):  # oldest first
        ts = datetime.fromtimestamp(sub["timestamp"])
        if ts <= last_commit_time:
            continue

        name = normalize_name(sub["title"])
        if name not in problem_counter:
            problem_counter[name] = 0
        problem_counter[name] += 1
        sol_count = problem_counter[name]

        folder = f"{name}"
        readme_path = f"{folder}/README.md"
        solution_file = f"{folder}/solution_{sol_count}.{LANG_EXT.get(sub['lang'], 'txt')}"

        code = get_submission_code(sub["id"])
        try:
            content = get_problem_content(sub["titleSlug"])
        except:
            content = "Problem content unavailable"

        tree_elements = [
            {"path": readme_path, "mode": "100644", "content": content},
            {"path": solution_file, "mode": "100644", "content": code},
        ]

        # Commit message with time & space
        msg = f"Time: {sub['runtime']} ({sub.get('runtime', 'N/A')}), Space: {sub['memory']} ({sub.get('memory', 'N/A')})"

        # Create tree
        base_tree = repo.get_git_tree(repo.get_commits()[0].commit.tree.sha)
        new_tree = repo.create_git_tree(tree_elements, base_tree=base_tree)

        # Commit
        commit = repo.create_git_commit(
            message=msg,
            tree=new_tree,
            parents=[repo.get_commits()[0].sha],
            author=repo.get_commits()[0].commit.author,
            committer=repo.get_commits()[0].commit.committer,
        )

        # Update branch
        repo.get_git_ref(f"heads/{repo.default_branch}").edit(commit.sha, force=True)
        print(f"Committed {solution_file}")

if __name__ == "__main__":
    main()
