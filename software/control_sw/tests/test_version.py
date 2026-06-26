"""Tests for PEP440 compliant version string generation."""
import re
import unittest


def pep440_from_git_describe(desc: str) -> str:
    """Copy of the function from setup.py for testing."""
    s = desc.strip()
    dirty = s.endswith("-dirty")
    s = s[:-6] if dirty else s
    m = re.fullmatch(r"v?(\d+(?:\.\d+)*)(?:-(\d+)-g([0-9a-f]+))?", s, re.I)
    if m:
        base, n, sha = m.groups()
        if n is None:
            v = base + ("+dirty" if dirty else "")
        else:
            v = f"{base}.post{n}+g{sha}" + (".dirty" if dirty else "")
    else:
        sha = re.sub(r"[^0-9a-f]", "", s.lower())[:8] or "unknown"
        v = f"0.0+g{sha}" + (".dirty" if dirty else "")
    return v


class TestPep440FromGitDescribe(unittest.TestCase):
    """Verify PEP440 compliance of version strings from git describe."""

    def test_exact_tag(self):
        """Exact tag match should return base version."""
        self.assertEqual(pep440_from_git_describe("v7.6.1.0"), "7.6.1.0")

    def test_exact_tag_dirty(self):
        """Exact tag + dirty should use local segment +dirty."""
        self.assertEqual(pep440_from_git_describe("v7.6.1.0-dirty"), "7.6.1.0+dirty")

    def test_post_tag(self):
        """N commits after tag should produce .postN+gHASH."""
        self.assertEqual(
            pep440_from_git_describe("v7.6.1.0-1-g7de82f60"),
            "7.6.1.0.post1+g7de82f60"
        )

    def test_post_tag_dirty(self):
        """N commits after tag + dirty should include .dirty in local."""
        self.assertEqual(
            pep440_from_git_describe("v7.6.1.0-1-g7de82f60-dirty"),
            "7.6.1.0.post1+g7de82f60.dirty"
        )

    def test_no_tag_hash_only(self):
        """No tag, only commit hash."""
        self.assertEqual(
            pep440_from_git_describe("7de82f60"),
            "0.0+g7de82f60"
        )

    def test_no_tag_hash_only_dirty(self):
        """No tag, commit hash + dirty."""
        self.assertEqual(
            pep440_from_git_describe("7de82f60-dirty"),
            "0.0+g7de82f60.dirty"
        )

    def test_simple_tag(self):
        """Simple two-part version tag."""
        self.assertEqual(pep440_from_git_describe("v1.0"), "1.0")

    def test_tag_without_v(self):
        """Tag without leading 'v'."""
        self.assertEqual(pep440_from_git_describe("1.2.3"), "1.2.3")

    def test_multiple_commits_since_tag(self):
        """Multiple commits since tag."""
        self.assertEqual(
            pep440_from_git_describe("v2.0.0-15-gabcdef01"),
            "2.0.0.post15+gabcdef01"
        )

    def test_all_outputs_pep440_compliant(self):
        """All outputs should be parseable as PEP440 versions."""
        try:
            from packaging.version import Version
        except ImportError:
            self.skipTest("packaging not installed")

        test_inputs = [
            "v7.6.1.0",
            "v7.6.1.0-dirty",
            "v7.6.1.0-1-g7de82f60",
            "v7.6.1.0-1-g7de82f60-dirty",
            "7de82f60",
            "7de82f60-dirty",
            "v1.0",
            "1.2.3",
        ]
        for desc in test_inputs:
            v = pep440_from_git_describe(desc)
            try:
                Version(v)
            except Exception as e:
                self.fail(f"Version '{v}' (from '{desc}') is not PEP440: {e}")


if __name__ == '__main__':
    unittest.main()
