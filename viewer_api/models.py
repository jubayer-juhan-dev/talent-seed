"""Response models. They document the API (/api/docs) and generate the frontend's TypeScript types.

Endpoints use response_model_exclude_unset, so a field is only sent when the query returned it. The JSON
is the same as the old server's: dates are ISO strings, lists stay lists.
"""

from pydantic import BaseModel, ConfigDict


class Count(BaseModel):
    k: str
    n: int


class Run(BaseModel):
    run_at: str
    source_snapshot_id: str
    source_snapshot_date: str | None = None
    as_of_activity_date: str | None = None
    row_counts: str | None = None  # JSON text, per-table row counts of the build


class Meta(BaseModel):
    run: Run
    cohorts: list[Count]
    chains: list[Count]
    countries: list[Count]


class GithubOverlay(BaseModel):
    """Set only when the login came from scripts/m5_lookup_github_logins.py."""
    github_login_source: str | None = None  # GITHUB_API_USER_ID_API | GITHUB_API_COMMIT_API (or the build's source)
    github_login_looked_up_at: str | None = None


class PersonRow(GithubOverlay):
    """One row of /api/people."""
    person_id: str
    display_name: str | None = None
    github_login: str | None = None
    github_user_id: int | None = None
    github_confidence: str | None = None  # HIGH | MEDIUM | LOW | NONE
    country: str | None = None
    priority_cohort: str  # P1 | P2 | P3 | HOLD
    priority_cohort_reason: str | None = None
    tenure_segment: str | None = None  # ESTABLISHED | EMERGING | NEWCOMER | UNKNOWN
    activity_segment: str | None = None  # FULL_TIME | PART_TIME | ONE_TIME | UNKNOWN
    exclusivity: str | None = None  # EXCLUSIVE | MULTICHAIN | UNKNOWN
    active_days_in_window: int | None = None
    commit_count: int | None = None
    repository_count: int | None = None
    ecosystem_count: int | None = None
    top_level_ecosystems: list[str] | None = None
    first_commit_date: str | None = None
    last_activity_date: str | None = None
    flag_probable_bot: bool = False
    flag_linked_ids: bool = False
    flag_activity_table_gap: bool = False
    flag_github_conflict: bool = False


class People(BaseModel):
    total: int
    page: int
    page_size: int
    rows: list[PersonRow]


class ChainCount(Count):
    p1: int


class MixCell(BaseModel):
    tenure: str
    activity: str
    n: int


class Overview(BaseModel):
    cohorts: list[Count]
    chains: list[ChainCount]
    mix: list[MixCell]
    countries: list[Count]
    no_country: tuple[int, int]  # (people without a country, all active people)


class EcosystemHit(BaseModel):
    k: str
    level: str  # TOP_LEVEL (a chain) | SUB_ECOSYSTEM (a project)
    n: int


class Ecosystems(BaseModel):
    rows: list[EcosystemHit]


class Person(GithubOverlay):
    """Every column of talent_seed for one person (see docs/talent_seed_tables.md)."""
    model_config = ConfigDict(extra="allow")
    person_id: str
    primary_canonical_developer_id: int | None = None
    canonical_developer_ids: list[int] | None = None
    n_canonical_ids: int | None = None
    display_name: str | None = None
    n_names: int | None = None
    github_user_id: int | None = None
    github_login: str | None = None
    github_resolution_method: str | None = None
    github_corroborated_by_odd_id: bool | None = None
    github_candidate_commit_sha: str | None = None
    github_candidate_repo: str | None = None
    location: str | None = None
    country: str | None = None
    first_commit_date: str | None = None
    first_crypto_commit_date: str | None = None
    last_crypto_activity_date: str | None = None
    last_activity_date: str | None = None
    repository_count: int | None = None
    repository_count_excluding_inherited: int | None = None
    ecosystem_count: int | None = None
    ecosystem_count_excluding_inherited: int | None = None
    sub_ecosystem_count: int | None = None
    top_level_ecosystems: list[str] | None = None
    commit_count: int | None = None
    commit_count_bot: int | None = None
    commit_count_ai_agent: int | None = None
    commit_count_excluding_inherited: int | None = None
    tenure_days: int | None = None
    active_days_in_window: int | None = None
    max_active_days_in_28d: int | None = None
    exclusivity_eco_days: int | None = None
    exclusivity_exclusive_days: int | None = None
    top_level_ecosystems_in_window: list[str] | None = None
    odd_contribution_rank_asof: str | None = None
    flag_probable_bot: bool | None = None
    flag_github_conflict: bool | None = None
    flag_linked_ids: bool | None = None
    flag_activity_table_gap: bool | None = None
    flag_bad_commit_dates: bool | None = None
    github_confidence: str | None = None
    tenure_segment: str | None = None
    activity_segment: str | None = None
    exclusivity: str | None = None
    exclusivity_method: str | None = None
    distinct_top_level_ecosystems_in_window: int | None = None
    priority_cohort: str | None = None
    priority_cohort_rule: int | None = None
    priority_cohort_reason: str | None = None
    priority_cohort_status: str | None = None  # DRAFT_ASSUMPTION until the client confirms the cohort table
    as_of_activity_date: str | None = None
    activity_window_start: str | None = None
    source_snapshot_id: str | None = None
    source_snapshot_date: str | None = None
    source_tables: list[str] | None = None


class Member(BaseModel):
    canonical_developer_id: int
    link_method: str  # SINGLE_ID | SAME_GITHUB_USER_ID
    n_commits: int | None = None


class Contact(BaseModel):
    value: str
    email_status: str  # always UNVERIFIED
    is_github_noreply: bool
    is_placeholder: bool
    shared_by_n_developers: int | None = None
    author_names: list[str] | None = None
    first_seen_at: str | None = None
    last_seen_at: str | None = None
    n_commits: int | None = None


class PersonEcosystem(BaseModel):
    level: str
    ecosystem_name: str
    repo_count: int | None = None
    repo_count_excluding_inherited: int | None = None
    commits: int | None = None
    last_active_date: str | None = None


class Repo(BaseModel):
    repo_name: str
    repo_url: str | None = None
    commits: int | None = None
    active_days: int | None = None
    first_active_date: str | None = None
    last_active_date: str | None = None
    inherited_history: bool | None = None  # fork or copied history
    num_stars: int | None = None


class TopRepo(BaseModel):
    repo_name: str
    repo_url: str | None = None
    commits: int | None = None
    active_days: int | None = None
    first_original_date: str | None = None
    last_original_date: str | None = None
    num_stars: int | None = None


class PersonDetail(BaseModel):
    person: Person
    members: list[Member]
    contacts: list[Contact]
    ecosystems: list[PersonEcosystem]
    repos: list[Repo]  # the 100 most recent
    top_repos: list[TopRepo]  # original work in crypto repos, active-in-window first
    repo_total: int


class Error(BaseModel):
    error: str
