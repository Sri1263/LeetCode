import os
import time
import json
import requests
from datetime import datetime
from github import Github, InputGitTreeElement

# ---------------- CONFIG ----------------
LANG_TO_EXTENSION = {
    "bash": "sh", "c": "c", "cpp": "cpp", "csharp": "cs",
    "dart": "dart", "elixir": "ex", "erlang": "erl", "golang": "go",
    "java": "java", "javascript": "js", "kotlin": "kt",
    "mssql": "sql", "mysql": "sql", "oraclesql": "sql",
    "php": "php", "python": "py", "python3": "py", "pythondata": "py",
    "postgresql": "sql", "racket": "rkt", "ruby": "rb", "rust": "rs",
    "scala": "scala", "swift": "swift", "typescript": "ts",
}
LEETCODE_GRAPHQL = "https://leetcode.com/graphql/"
BASE_URL = "https://leetcode.com"
FILTER_DUPLICATE_SECS = int(os.getenv("FILTER_DUPLICATE_SECS", "86400"))

# ---------------- HELPERS ----------------
def log(msg):
    print(f"[{datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}] {msg}")

def graphql_headers(session, csrf):
    return {
        "Content-Type": "application/json",
        "Origin": BASE_URL,
        "Referer": BASE_URL,
        "Cookie": f"LEETCODE_SESSION={session}; csrftoken={csrf};",
        "x-csrftoken": csrf,
    }

def normalize_name(name):
    return "".join(c if c.isalnum() or c in "-_" else "-" for c in name.lower().replace(" ", "-"))

def pad(n):
    return n.zfill(4) if len(n) <= 4 else n

# ---------------- LEETCODE FETCH ----------------
def fetch_submissions(session, csrf, last_ts):
    submissions = []
    submissions_dict = {}
    offset = 0
    while True:
        query = {
            "query": """query ($offset: Int!, $limit: Int!, $slug: String) {
                submissionList(offset: $offset, limit: $limit, questionSlug: $slug) {
                    hasNext
                    submissions {
                        id
                        lang
                        timestamp
                        statusDisplay
                        runtime
                        title
                        memory
                        titleSlug
                    }
                }
            }""",
            "variables": {"offset": offset, "limit": 20, "slug": None},
        }
        for retry in range(5):
            try:
                resp = requests.post(LEETCODE_GRAPHQL, headers=graphql_headers(session, csrf), json=query)
                resp.raise_for_status()
                break
            except Exception as e:
                log(f"Error fetching submissions, retry {retry+1}/5: {e}")
                time.sleep(3 ** retry)
        else:
            raise RuntimeError("Failed fetching submissions after retries")

        data = resp.json()["data"]["submissionList"]
        for s in data["submissions"]:
            ts = int(s["timestamp"])
            if ts <= last_ts or s["statusDisplay"] != "Accepted":
                continue
            lang = s["lang"]
            name = normalize_name(s["title"])
            if name not in submissions_dict:
                submissions_dict[name] = {}
            if lang not in submissions_dict[name]:
                submissions_dict[name][lang] = []
            # Filter duplicates within FILTER_DUPLICATE_SECS
            if submissions_dict[name][lang] and ts - submissions_dict[name][lang][-1] < FILTER_DUPLICATE_SECS:
                continue
            submissions_dict[name][lang].append(ts)
            submissions.append(s)
        if not data["hasNext"]:
            break
        offset += 20
    log(f"Total accepted submissions found: {len(submissions)}")
    return submissions[::-1], submissions_dict  # oldest first

def fetch_submission_code(sub_id, session, csrf):
    query = {
        "query": """query submissionDetails($submissionId: Int!) {
            submissionDetails(submissionId: $submissionId) {
                runtimePercentile
                memoryPercentile
                code
                question { questionId }
            }
        }""",
        "variables": {"submissionId": int(sub_id)},
    }
    for retry in range(5):
        try:
            resp = requests.post(LEETCODE_GRAPHQL, headers=graphql_headers(session, csrf), json=query)
            if resp.status_code == 403:
                log(f"Skipping locked problem {sub_id}")
                return None
            resp.raise_for_status()
            return resp.json()["data"]["submissionDetails"]
        except Exception as e:
            log(f"Retry fetching code for {sub_id}: {e}")
            time.sleep(3 ** retry)
    log(f"⚠️ Skipping submission {sub_id} after retries")
    return None

def fetch_question_content(slug, session, csrf):
    query = {
        "query": """query getQuestionDetail($titleSlug: String!) {
            question(titleSlug: $titleSlug) { content }
        }""",
        "variables": {"titleSlug": slug},
    }
    try:
        resp = requests.post(LEETCODE_GRAPHQL, headers=graphql_headers(session, csrf), json=query)
        resp.raise_for_status()
        return resp.json()["data"]["question"]["content"]
    except:
        log(f"⚠️ Cannot fetch question {slug}")
        return "Unable to fetch the Problem statement."

# ---------------- GITHUB COMMIT ----------------
def commit_solution(repo, submission, question_content, commit_info, solution_index):
    name = normalize_name(submission["title"])
    qid = pad(str(submission["question"]["questionId"])) + "-" if "question" in submission else ""
    folder = f"{qid}{name}"
    os.makedirs(folder, exist_ok=True)

    ext = LANG_TO_EXTENSION.get(submission["lang"], "txt")
    solution_filename = f"solution_{solution_index}.{ext}"
    solution_path = f"{folder}/{solution_filename}"
    readme_path = f"{folder}/README.md"

    # Write README.md if not exists
    if not os.path.exists(readme_path):
        with open(readme_path, "w", encoding="utf-8") as f:
            f.write(question_content + "\n")

    # Write solution file
    with open(solution_path, "w", encoding="utf-8") as f:
        f.write(submission["code"] + "\n")

    runtime = submission.get("runtime", "N/A")
    mem = submission.get("memory", "N/A")
    runtimePerc = submission.get("runtimePercentile", "N/A")
    memoryPerc = submission.get("memoryPercentile", "N/A")
    message = f"Time: {runtime} ({runtimePerc}), Space: {mem} ({memoryPerc})"

    # Commit via GitHub API
    element = [
        InputGitTreeElement(solution_path, "100644", submission["code"] + "\n"),
        InputGitTreeElement(readme_path, "100644", question_content + "\n")
    ]
    base_tree = repo.get_branch(repo.default_branch).commit.commit.tree.sha
    new_tree = repo.create_git_tree(element, base_tree)
    commit = repo.create_git_commit(message, new_tree, [repo.get_branch(repo.default_branch).commit.commit.sha], author=commit_info)
    repo.get_git_ref(f"heads/{repo.default_branch}").edit(commit.sha, force=True)
    log(f"Committed {solution_filename} for {folder}")

# ---------------- MAIN ----------------
def main():
    github_token = os.environ["GITHUB_TOKEN"]
    lc_session = os.environ["LEETCODE_SESSION"]
    lc_csrf = os.environ["LEETCODE_CSRF_TOKEN"]

    g = Github(github_token)
    repo_name = os.environ.get("GITHUB_REPO", os.environ.get("GITHUB_REPOSITORY"))
    repo = g.get_repo(repo_name)

    # last synced timestamp
    commits = repo.get_commits()
    last_ts = 0
    commit_info = None
    for c in commits:
        msg = c.commit.message
        if msg.startswith("Time:"):
            commit_info = c.commit.author
            last_ts = int(datetime.strptime(c.commit.committer.date.isoformat(), "%Y-%m-%dT%H:%M:%S%z").timestamp())
            break
    if commit_info is None:
        commit_info = repo.get_commits()[0].commit.author

    submissions, subs_dict = fetch_submissions(lc_session, lc_csrf, last_ts)
    solution_count = {}
    for sub in submissions:
        code_data = fetch_submission_code(sub["id"], lc_session, lc_csrf)
        if code_data is None:
            continue
        sub.update(code_data)
        question_content = fetch_question_content(sub["titleSlug"], lc_session, lc_csrf)
        key = normalize_name(sub["title"])
        solution_count[key] = solution_count.get(key, 0) + 1
        commit_solution(repo, sub, question_content, commit_info, solution_count[key])

if __name__ == "__main__":
    main()
