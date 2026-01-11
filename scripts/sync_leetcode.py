import os
import time
import requests
from github import Github, InputGitTreeElement

LEETCODE_SESSION = os.environ.get("LEETCODE_SESSION")
LEETCODE_CSRF = os.environ.get("LEETCODE_CSRF_TOKEN")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")

REPO_FULL = os.environ.get("GITHUB_REPOSITORY")  # owner/repo
REPO_OWNER, REPO_NAME = REPO_FULL.split("/")

GRAPHQL_URL = "https://leetcode.com/graphql/"

HEADERS = {
    "Content-Type": "application/json",
    "x-csrftoken": LEETCODE_CSRF,
    "cookie": f"LEETCODE_SESSION={LEETCODE_SESSION}; csrftoken={LEETCODE_CSRF};",
    "referer": "https://leetcode.com",
}

LANG_TO_EXT = {
    "python3": "py",
    "python": "py",
    "cpp": "cpp",
    "java": "java",
    "c": "c",
    "csharp": "cs",
    "javascript": "js",
    "ruby": "rb",
    "golang": "go",
    "kotlin": "kt",
    "swift": "swift",
    "typescript": "ts",
}

def normalize_name(name):
    return name.lower().replace(" ", "_").replace("-", "_")

def fetch_submissions(offset=0, limit=20):
    query = {
        "query": """
            query submissionList($offset: Int!, $limit: Int!) {
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
        "variables": {"offset": offset, "limit": limit},
    }
    r = requests.post(GRAPHQL_URL, json=query, headers=HEADERS)
    r.raise_for_status()
    return r.json()["data"]["submissionList"]

def fetch_submission_code(submission_id):
    query = {
        "query": """
            query submissionDetails($id: Int!) {
                submissionDetails(submissionId: $id) {
                    code
                    runtimePercentile
                    memoryPercentile
                }
            }
        """,
        "variables": {"id": submission_id},
    }
    r = requests.post(GRAPHQL_URL, json=query, headers=HEADERS)
    r.raise_for_status()
    data = r.json()["data"]["submissionDetails"]
    return data["code"], data.get("runtimePercentile"), data.get("memoryPercentile")

def main():
    g = Github(GITHUB_TOKEN)
    repo = g.get_repo(f"{REPO_OWNER}/{REPO_NAME}")

    offset = 0
    all_submissions = []
    while True:
        submissions_data = fetch_submissions(offset)
        all_submissions.extend(submissions_data["submissions"])
        if not submissions_data["hasNext"]:
            break
        offset += 20
        time.sleep(1)

    accepted = [s for s in all_submissions if s["statusDisplay"] == "Accepted"]

    solution_count = {}

    for sub in sorted(accepted, key=lambda x: x["timestamp"]):
        problem = normalize_name(sub["title"])
        solution_count[problem] = solution_count.get(problem, 0) + 1
        code, runtimePerc, memoryPerc = fetch_submission_code(sub["id"])

        folder_path = problem
        file_name = f"solution_{solution_count[problem]}.{LANG_TO_EXT.get(sub['lang'], 'txt')}"

        # Build tree elements
        elements = []

        # README.md
        readme_path = f"{folder_path}/README.md"
        elements.append(
            InputGitTreeElement(
                path=readme_path,
                mode="100644",
                type="blob",
                content=f"# {sub['title']}\nProblem slug: {sub['titleSlug']}"
            )
        )

        # Solution file
        solution_path = f"{folder_path}/{file_name}"
        elements.append(
            InputGitTreeElement(
                path=solution_path,
                mode="100644",
                type="blob",
                content=code
            )
        )

        # Create tree and commit
        base_tree = repo.get_branch(repo.default_branch).commit.commit.tree
        new_tree = repo.create_git_tree(elements, base_tree)
        commit_message = f"Time: {sub['runtime']} ({runtimePerc}%), Space: {sub['memory']} ({memoryPerc}%)"
        parent = repo.get_branch(repo.default_branch).commit.sha
        commit = repo.create_git_commit(commit_message, new_tree, [parent])
        repo.get_git_ref(f"heads/{repo.default_branch}").edit(commit.sha)

        print(f"Committed {file_name} for {sub['title']}")

if __name__ == "__main__":
    main()
