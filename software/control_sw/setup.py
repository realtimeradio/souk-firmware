from distutils.core import setup
import glob
import os
import re
import subprocess

def pep440_from_git_describe(desc: str) -> str:
    s = desc.strip()
    dirty = s.endswith("-dirty")
    s = s[:-6] if dirty else s  # keep compatible (no removesuffix)
    m = re.fullmatch(r"v?(\d+(?:\.\d+)*)(?:-(\d+)-g([0-9a-f]+))?", s, re.I)
    # RE matching:
    #   v?            optional leading 'v' in tag
    #   (\d+(?:\.\d+)*)  version number like 7.4.2 or 7.4.2.0
    #   (?:-(\d+)-g([0-9a-f]+))?
    #       optional "-N-gHASH" meaning:
    #         N     = number of commits since the tag
    #         HASH  = abbreviated git commit hash
    if m:
        base, n, sha = m.groups()
        v = base if n is None else f"{base}.post{n}+g{sha}"
    else:
        sha = re.sub(r"[^0-9a-f]", "", s.lower())[:8] or "unknown"
        v = f"0.0+g{sha}"

    return v + (".dirty" if dirty else "")

def get_version(default="0.1") -> str:
    try:
        desc = subprocess.check_output(
            ["git", "describe", "--abbrev=8", "--always", "--dirty", "--tags"],
            stderr=subprocess.DEVNULL,
        ).decode().strip()
        v = pep440_from_git_describe(desc)
        print("Version is: %s (from git: %s)" % (v, desc))
        return v
    except Exception:
        print("Couldn't get version from git. Defaulting to %s" % default)
        return default

ver = get_version()

# Generate a __version__.py file with this version in it
here = os.path.abspath(os.path.dirname(__file__))
with open(os.path.join(here, 'src', '__version__.py'), 'w') as fh:
    fh.write('__version__ = "%s"' % ver)

setup(name='souk_mkid_readout',
      version='%s' % ver,
      description='Python libraries and scripts to control the SOUK Firmware',
      author='Jack Hickish',
      author_email='jack@realtimeradio.co.uk',
      url='https://github.com/realtimeradio/souk-firmware',
      provides=['souk_mkid_readout'],
      packages=['souk_mkid_readout', 'souk_mkid_readout.blocks'],
      package_dir={'souk_mkid_readout' : 'src'},
      scripts=glob.glob('scripts/*.py'),
      )

if ver.endswith("dirty"):
    print("***************************************************")
    print("* You are installing from a dirty git repository. *")
    print("*          One day you will regret this.          *")
    print("*                                                 *")
    print("*      Consider cleaning up and reinstalling.     *")
    print("***************************************************")
