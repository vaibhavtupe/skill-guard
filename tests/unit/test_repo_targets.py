from __future__ import annotations

from pathlib import Path

import skill_guard.engine.repo_targets as repo_targets


def test_collect_skill_roots_finds_unique_parents(tmp_path: Path) -> None:
    skill_dir = tmp_path / "skills" / "alpha"
    (skill_dir / "references").mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: alpha\ndescription: Use when resolving alpha tasks.\n---\n",
        encoding="utf-8",
    )

    roots = repo_targets.collect_skill_roots(
        [skill_dir / "SKILL.md", skill_dir / "references" / "guide.md"]
    )

    assert roots == [skill_dir.resolve()]


def test_resolve_changed_skill_selection_collects_modified_renamed_and_deleted(
    tmp_path: Path, monkeypatch
) -> None:
    repo_root = tmp_path / "repo"
    skills_root = repo_root / "skills"
    modified = skills_root / "alpha"
    renamed = skills_root / "beta-renamed"
    modified.mkdir(parents=True)
    renamed.mkdir(parents=True)
    (modified / "SKILL.md").write_text(
        "---\nname: alpha\ndescription: Use when resolving alpha tasks.\n---\n",
        encoding="utf-8",
    )
    (renamed / "SKILL.md").write_text(
        "---\nname: beta\ndescription: Use when resolving beta tasks.\n---\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(repo_targets, "_git_repo_root", lambda path: repo_root)
    monkeypatch.setattr(repo_targets, "_default_base_ref", lambda repo, head: "base-sha")
    monkeypatch.setattr(
        repo_targets,
        "_git_diff_name_status",
        lambda repo, base, head: [
            repo_targets.ChangedPath(
                status="M", old_path=None, new_path=Path("skills/alpha/SKILL.md")
            ),
            repo_targets.ChangedPath(
                status="R100",
                old_path=Path("skills/beta/SKILL.md"),
                new_path=Path("skills/beta-renamed/SKILL.md"),
            ),
            repo_targets.ChangedPath(
                status="D", old_path=Path("skills/gamma/SKILL.md"), new_path=None
            ),
        ],
    )

    selection = repo_targets.resolve_changed_skill_selection(skills_root)

    assert selection.base_ref == "base-sha"
    assert [target.status for target in selection.targets] == ["modified", "renamed"]
    assert selection.targets[0].root == modified.resolve()
    assert selection.targets[1].root == renamed.resolve()
    assert selection.targets[1].previous_root == (skills_root / "beta").resolve()
    assert selection.deleted_roots == ((skills_root / "gamma").resolve(),)
