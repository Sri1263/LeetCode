import os
import math
import requests
from github import Github, InputGitTreeElement

# Env vars from GitHub Action
GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]
LEETCODE_CSRF = os.environ["LEETCODE_CSRF"]
LEETCODE_SESSION = os.environ["LEETCODE_SESSION"]
REPO_OWNER = os.environ["REPO_OWNER"]
REPO_NAME = os.environ["REPO_NAME"]

LANG_EXT = {
    "python": "py",
    "python3": "py",
    "cpp": "cpp",
    "c": "c",
    "java": "java",
    "javascript": "js",
    "csharp": "cs",
    "ruby": "rb",
    "swift": "swift",
    "golang": "go",
    "typescript": "ts",
}

BASE_URL = "https://leetcode.com"

def log(msg):
    print(f"[LeetCode Sync] {msg}")

def normalize(name):
    return name.lower().replace(" ", "_").replace("-", "_")

def get_submissions():
    """Fetch all accepted submissions from LeetCode using GraphQL"""
    headers = {
        "Cookie": f"csrftoken={LEETCODE_CSRF}; LEETCODE_SESSION={LEETCODE_SESSION}",
        "x-csrftoken": LEETCODE_CSRF,
        "origin": BASE_URL,
        "referer": BASE_URL,
        "content-type": "application/json",
    }

    submissions = []
    offset = 0
    limit = 20
    while True:
        query = {
            "query": """query submissionList($offset:Int!, $limit:Int!){
              submissionList(offset:$offset,limit:$limit){
                hasNext
                submissions{
                  id
                  title
                  titleSlug
                  lang
                  runtime
                  memory
                  timestamp
                  statusDisplay
                }
              }
            }""",
            "variables": {"offset": offset, "limit": limit},
        }
        r = requests.post(f"{BASE_URL}/graphql/", json=query, headers=headers)
        r.raise_for_status()
        data = r.json()["data"]["submissionList"]
        for sub in data["submissions"]:
            if sub["statusDisplay"] == "Accepted":
                submissions.append(sub)
        if not data["hasNext"]:
            break
        offset += limit
    log(f"Total accepted submissions found: {len(submissions)}")
    return submissions

def get_submission_code(sub_id):
    headers = {
        "Cookie": f"csrftoken={LEETCODE_CSRF}; LEETCODE_SESSION={LEETCODE_SESSION}",
        "x-csrftoken": LEETCODE_CSRF,
        "origin": BASE_URL,
        "referer": BASE_URL,
        "content-type": "application/json",
    }
    query = {
        "query": """query submissionDetails($id:Int!){
          submissionDetails(submissionId:$id){
            code
          }
        }""",
        "variables": {"id": sub_id},
    }
    r = requests.post(f"{BASE_URL}/graphql/", json=query, headers=headers)
    r.raise_for_status()
    return r.json()["data"]["submissionDetails"]["code"]

def get_problem_content(slug):
    headers = {
        "Cookie": f"csrftoken={LEETCODE_CSRF}; LEETCODE_SESSION={LEETCODE_SESSION}",
        "x-csrftoken": LEETCODE_CSRF,
        "origin": BASE_URL,
        "referer": BASE_URL,
        "content-type": "application/json",
    }
    query = {
        "query": """query getQuestionDetail($slug:String!){
          question(titleSlug:$slug){
            content
          }
        }""",
        "variables": {"slug": slug},
    }
    r = requests.post(f"{BASE_URL}/graphql/", json=query, headers=headers)
    r.raise_for_status()
    return r.json()["data"]["question"]["content"]

def main():
    g = Github(GITHUB_TOKEN)
    repo = g.get_repo(f"{REPO_OWNER}/{REPO_NAME}")
    commits = list(repo.get_commits())
    latest_commit_sha = commits[0].sha
    base_tree = repo.get_git_tree(latest_commit_sha)

    submissions = get_submissions()
    elements = []

    # Track solution counts per problem
    solution_count = {}

    for sub in submissions:
        title = normalize(sub["title"])
        if title not in solution_count:
            solution_count[title] = 1
        else:
            solution_count[title] += 1

        sol_num = solution_count[title]
        folder = f"{title}"
        readme_path = f"{folder}/README.md"
        solution_path = f"{folder}/solution_{sol_num}.{LANG_EXT.get(sub['lang'].lower(), 'txt')}"

        # Fetch problem description & submission code
        try:
            problem_content = get_problem_content(sub["titleSlug"])
            code = get_submission_code(sub["id"])
        except Exception as e:
            log(f"Skipping {sub['title']} due to error: {e}")
            continue

        commit_msg = f"{sub['title']} - Runtime: {sub['runtime']}, Memory: {sub['memory']}"
        
        elements.append(InputGitTreeElement(readme_path, "100644", "blob", problem_content))
        elements.append(InputGitTreeElement(solution_path, "100644", "blob", code))

        # Create commit
        # Get latest commit and tree from default branch
        default_branch = repo.get_branch(repo.default_branch)
        latest_commit = repo.get_git_commit(default_branch.commit.sha)
        base_tree_sha = latest_commit.tree.sha
        
        tree = repo.create_git_tree(elements, base_tree_sha)
        parent = repo.get_git_commit(latest_commit_sha)
        commit = repo.create_git_commit(commit_msg, tree, [parent])
        repo.get_git_ref(f"heads/{repo.default_branch}").edit(commit.sha)
        latest_commit_sha = commit.sha
        elements.clear()  # Clear for next submission

        log(f"✅ Committed {folder}/solution_{sol_num}")

if __name__ == "__main__":
    main()
