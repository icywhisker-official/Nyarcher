#!/usr/bin/env python3
import os
import sys
import json
import subprocess
import pwd
import shutil
import tarfile
from datetime import datetime

RED = "\033[0;31m"
NC = "\033[0m"

# Base packages that are *not* guaranteed to be present on Debian 13 KDE Plasma
# but are required for this script / intended UX.
BASE_DEPENDENCIES = [
    "curl",
    "wget",
    "tar",
    "flatpak",
    "plasma-discover-backend-flatpak",
]
LATEST_TAG_VERSION: str | None = None
RELEASE_LINK: str | None = None
TAG_PATH: str | None = None
PLASMOID_ID = "luisbocanegra.kde-material-you-colors"
REPO_URL = "https://github.com/luisbocanegra/kde-material-you-colors.git"

# ───────────────────────── basics / env ─────────────────────────
def _get_real_home() -> str:
    """Return the 'real' home dir (sudo caller if present, else current)."""
    sudo_user = os.environ.get("SUDO_USER")
    if sudo_user:
        try:
            return pwd.getpwnam(sudo_user).pw_dir
        except KeyError:
            pass
    return os.path.expanduser("~")


REAL_HOME = _get_real_home()
os.environ["HOME"] = REAL_HOME  # make shell commands respect the sudo user's home

# Per-user cache root for all downloads/extractions
CACHE_ROOT = os.path.join(REAL_HOME, ".cache", "nyarch-kde")
os.makedirs(CACHE_ROOT, exist_ok=True)


def sh(cmd: str, cwd: str | None = None) -> int:
    """
    Run a shell command without exiting on failure, return exit code.

    Only use this for *static* commands that do not include data from
    remote sources or user input.
    """
    env = os.environ.copy()
    env["HOME"] = REAL_HOME
    result = subprocess.run(cmd, shell=True, cwd=cwd, env=env)
    return result.returncode


def run(args: list[str], cwd: str | None = None) -> int:
    """
    Safer subprocess helper: no shell, argument list only.

    Use this whenever the command includes data derived from remote
    resources (e.g. URLs containing GitHub tag names).
    """
    env = os.environ.copy()
    env["HOME"] = REAL_HOME
    result = subprocess.run(args, cwd=cwd, env=env)
    return result.returncode


def _ensure_cache_subdir(name: str) -> str:
    """
    Ensure a cache subdir under CACHE_ROOT/<name> exists and return its path.
    """
    cache_dir = os.path.join(CACHE_ROOT, name)
    os.makedirs(cache_dir, exist_ok=True)
    return cache_dir


def apt_install(packages: list[str]) -> int:
    """
    Install the given APT packages non-interactively (-y).
    Returns the shell command exit code.
    """
    if not packages:
        return 0
    pkg_str = " ".join(sorted(set(packages)))
    cmd = (
        "sudo apt-get update -qq && "
        f"sudo apt-get install -y {pkg_str}"
    )
    return sh(cmd)


def copy_tree_skip_missing(src_dir: str, dest_dir: str) -> None:
    """
    Recursively copy src_dir → dest_dir, creating directories as needed and
    skipping any missing/broken files instead of erroring out.
    """
    for root, dirs, files in os.walk(src_dir):
        rel_root = os.path.relpath(root, src_dir)
        dest_root = dest_dir if rel_root == "." else os.path.join(dest_dir, rel_root)

        os.makedirs(dest_root, exist_ok=True)

        for name in files:
            src_path = os.path.join(root, name)
            if not os.path.exists(src_path):
                continue
            dest_path = os.path.join(dest_root, name)
            shutil.copy2(src_path, dest_path)


def _append_shell_snippet_safely(
    file_path: str,
    marker_comment: str,
    snippet_body: str,
    conflict_hint: str | None = None,
) -> bool:
    """
    Idempotently append a shell snippet to file_path.

    - If marker_comment or snippet_body is already present → no-op, return True.
    - If conflict_hint is present but marker is not → assume user has their own
      logic → print warning, do NOT modify, return False.
    - Otherwise, append:

        <optional newline>
        <marker_comment>
        <snippet_body>
        <newline>

      and return True.

    Never does sed/replace. Best-effort, conservative behavior.
    """
    try:
        if os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
        else:
            content = ""
    except OSError as exc:
        print(f"Warning: could not read {file_path}: {exc}")
        return False

    snippet_body_stripped = snippet_body.strip()

    # Already present?
    if marker_comment in content or snippet_body_stripped in content:
        print(f"Snippet already present in {file_path}; skipping.")
        return True

    # Heuristic conflict detection
    if conflict_hint and conflict_hint in content:
        print(
            f"Potential conflicting configuration in {file_path} "
            f"(found '{conflict_hint}'). Not modifying this file."
        )
        return False

    # Append snippet
    try:
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, "a", encoding="utf-8") as f:
            if content and not content.endswith("\n"):
                f.write("\n")
            f.write(marker_comment.rstrip() + "\n")
            f.write(snippet_body.rstrip() + "\n")
        print(f"Appended Nyarch snippet to {file_path}.")
        return True
    except OSError as exc:
        print(f"Warning: could not update {file_path}: {exc}")
        return False


def ensure_local_bin_on_path() -> None:
    """
    Make sure ~/.local/bin exists and is on PATH for this process and future logins.
    """
    local_bin = os.path.join(REAL_HOME, ".local", "bin")
    os.makedirs(local_bin, exist_ok=True)

    # Update PATH for *this* process / child processes
    current_path = os.environ.get("PATH", "")
    paths = current_path.split(":") if current_path else []
    if local_bin not in paths:
        os.environ["PATH"] = f"{local_bin}:{current_path}" if current_path else local_bin
        print(f"Temporarily added {local_bin} to PATH for this session.")

    profile = os.path.join(REAL_HOME, ".profile")
    marker = "# Nyarch KDE installer: ensure ~/.local/bin is on PATH"
    snippet = 'export PATH="$HOME/.local/bin:$PATH"'

    ok = _append_shell_snippet_safely(
        file_path=profile,
        marker_comment=marker,
        snippet_body=snippet,
        conflict_hint=".local/bin",
    )
    if not ok:
        print(
            "Did not modify ~/.profile due to potential PATH conflicts. "
            "Please review your PATH settings manually if ~/.local/bin "
            "is not available in new shells."
        )


def get_latest_tag() -> str:
    """Return the latest NyarchLinux release tag from GitHub (cached)."""
    global LATEST_TAG_VERSION

    if LATEST_TAG_VERSION:
        return LATEST_TAG_VERSION

    try:
        out = subprocess.check_output(
            [
                "curl",
                "-s",
                "https://api.github.com/repos/NyarchLinux/NyarchLinux/releases/latest",
            ],
            text=True,
        )
        data = json.loads(out)
        tag = data.get("tag_name")
        if not tag:
            raise ValueError("tag_name not found in GitHub API response")
        LATEST_TAG_VERSION = str(tag)
        return LATEST_TAG_VERSION
    except Exception as e:
        print(f"Failed to get latest Nyarch tag: {e}")
        sys.exit(1)


def ensure_release_info() -> None:
    """
    Ensure RELEASE_LINK and TAG_PATH are initialised based on the latest tag.
    """
    global RELEASE_LINK, TAG_PATH
    tag = get_latest_tag()

    if RELEASE_LINK is None:
        RELEASE_LINK = (
            f"https://github.com/NyarchLinux/NyarchLinux/releases/download/{tag}/"
        )

    if TAG_PATH is None:
        TAG_PATH = (
            "https://raw.githubusercontent.com/NyarchLinux/NyarchLinux/refs/tags/"
            f"{tag}/Gnome/"
        )


def get_tarball() -> None:
    """
    Download and extract the main NyarchLinux tarball into CACHE_ROOT if not
    already present.
    """
    ensure_release_info()

    file_path = os.path.join(CACHE_ROOT, "NyarchLinux.tar.gz")
    url = f"{RELEASE_LINK}NyarchLinux.tar.gz"  # type: ignore[operator]

    if not os.path.exists(file_path):
        print(f"Downloading Nyarch tarball from {url}")
        rc = run(["wget", "-q", "-O", file_path, url])
        if rc != 0:
            print("Failed to download Nyarch tarball; check your network and try again.")
            return

        rc = run(["tar", "-xvf", file_path], cwd=CACHE_ROOT)
        if rc != 0:
            print("Warning: failed to extract Nyarch tarball.")
    else:
        print(f"Using cached Nyarch tarball at {file_path}")
        # Ensure extraction exists
        if not any(
            os.path.isdir(os.path.join(CACHE_ROOT, d))
            for d in ("NyarchLinuxComp", "NyarchLinux")
        ):
            rc = run(["tar", "-xvf", file_path], cwd=CACHE_ROOT)
            if rc != 0:
                print("Warning: failed to extract Nyarch tarball.")


def _get_nyarch_skel_root() -> str | None:
    """
    Return the base Nyarch skel directory under CACHE_ROOT, or None if not found.
    """
    candidates = [
        os.path.join(CACHE_ROOT, "NyarchLinuxComp", "Gnome", "etc", "skel"),
        os.path.join(CACHE_ROOT, "NyarchLinux", "Gnome", "etc", "skel"),
    ]

    for path in candidates:
        if os.path.isdir(path):
            return path

    # Try extracting the tarball if nothing has been found yet
    get_tarball()

    for path in candidates:
        if os.path.isdir(path):
            return path

    print(
        "Nyarch skel directory not found under cache.\n"
        f"Checked under {CACHE_ROOT} for:\n"
        "  - NyarchLinuxComp/Gnome/etc/skel\n"
        "  - NyarchLinux/Gnome/etc/skel\n"
        "Make sure the Nyarch tarball was downloaded and extracted correctly."
    )
    return None


def detect_plasma_major_version() -> int:
    """
    Try to detect the KDE Plasma major version via 'plasmashell --version'.
    """
    try:
        out = subprocess.check_output(
            ["plasmashell", "--version"],
            text=True,
            stderr=subprocess.STDOUT,
        )
    except Exception:
        return 0

    for token in out.split():
        if token and token[0].isdigit():
            try:
                return int(token.split(".", 1)[0])
            except ValueError:
                return 0
    return 0


def describe_os() -> str:
    """
    Best-effort human readable OS description from /etc/os-release.
    """
    try:
        data: dict[str, str] = {}
        with open("/etc/os-release", "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                data[k] = v.strip().strip('"')
        pretty = data.get("PRETTY_NAME") or data.get("NAME") or "Unknown"
        codename = data.get("VERSION_CODENAME") or ""
        if codename:
            return f"{pretty} ({codename})"
        return pretty
    except OSError:
        return "Unknown"


def install_base_dependencies() -> None:
    """
    Install base runtime dependencies not guaranteed in a stock Debian 13 KDE setup.
    """
    print(
        "Installing base dependencies with apt:\n  "
        + " ".join(BASE_DEPENDENCIES)
    )
    rc = apt_install(BASE_DEPENDENCIES)
    if rc != 0:
        print("Failed to install base dependencies. Please check apt output.")
        sys.exit(1)


def show_banner() -> None:
    sh(
        "curl https://raw.githubusercontent.com/NyarchLinux/NyarchLinux/main/"
        "Gnome/etc/skel/.config/neofetch/ascii70"
    )
    print(f"{RED}\n\nWelcome to Nyarch Linux KDE customization installer! {NC}")


def _plasmoid_paths() -> list[str]:
    """Possible install locations for the KDE Material You Colors plasmoid."""
    return [
        os.path.join(REAL_HOME, ".local", "share", "plasma", "plasmoids", PLASMOID_ID),
        os.path.join("/usr", "share", "plasma", "plasmoids", PLASMOID_ID),
    ]


def is_kde_material_you_plasmoid_installed() -> bool:
    """Return True if the KDE Material You Colors plasmoid appears to be installed."""
    return any(os.path.isdir(p) for p in _plasmoid_paths())


def _print_manual_plasmoid_instructions() -> None:
    """
    Fallback instructions if automatic plasmoid install fails.
    """
    print(
        "\nAutomatic install of the 'KDE Material You Colors' widget failed.\n"
        "You can still install it manually:\n"
        "  1) Right-click your panel → Add Widgets\n"
        "  2) Get New Widgets → Download New Plasma Widgets\n"
        "  3) Search for \"KDE Material You Colors\" and install it\n"
        "  4) Add the widget to your panel/desktop and link it to your wallpaper\n"
    )


def _install_plasmoid_impl(*, skip_if_present: bool) -> bool:
    """
    Shared installer for the KDE Material You Colors plasmoid.
    """
    if skip_if_present and is_kde_material_you_plasmoid_installed():
        print("KDE Material You Colors plasmoid already installed – skipping.")
        return True

    rc = apt_install(["git", "kpackagetool6"])
    if rc != 0:
        print("Failed to install git/kpackagetool6 via apt.")
        _print_manual_plasmoid_instructions()
        return False

    repo_dir = os.path.join(CACHE_ROOT, "kde-material-you-colors")
    if os.path.exists(repo_dir):
        # Symlink safety: never rmtree a symlink target
        if os.path.islink(repo_dir):
            print(
                f"Refusing to operate on symlinked plasmoid dir: {repo_dir}. "
                "Please remove it manually."
            )
            return False
        try:
            shutil.rmtree(repo_dir)
        except OSError as exc:
            print(f"Failed to remove existing plasmoid directory {repo_dir}: {exc}")
            return False

    if run(["git", "clone", REPO_URL, repo_dir]) != 0:
        print("Failed to clone kde-material-you-colors repository.")
        _print_manual_plasmoid_instructions()
        return False

    package_dir = os.path.join(repo_dir, "src", "plasmoid", "package")
    if not os.path.isdir(package_dir):
        print(f"Plasmoid package directory not found: {package_dir}")
        _print_manual_plasmoid_instructions()
        return False

    cmd = f'kpackagetool6 --type Plasma/Applet --install "{package_dir}"'
    rc = sh(cmd)
    if rc != 0:
        cmd_up = f'kpackagetool6 --type Plasma/Applet --upgrade "{package_dir}"'
        rc = sh(cmd_up)
        if rc != 0:
            print("kpackagetool6 could not install/upgrade the plasmoid package.")
            _print_manual_plasmoid_instructions()
            return False

    print("KDE Material You Colors plasmoid installed/upgraded.")
    return True


def ensure_kde_material_you_plasmoid() -> bool:
    """
    Normal behavior: only install if widget is missing.
    """
    return _install_plasmoid_impl(skip_if_present=True)


def install_nyarch_wallpapers() -> None:
    """
    Install Nyarch wallpapers into a KDE-friendly location:
      ~/.local/share/wallpapers/nyarch
    """
    skel_root = _get_nyarch_skel_root()
    if skel_root is None:
        return

    src_dir = os.path.join(skel_root, ".local", "share", "backgrounds")

    if not os.path.isdir(src_dir):
        print(f"Backgrounds folder not found in Nyarch skel: {src_dir}")
        return

    dest_dir = os.path.join(REAL_HOME, ".local", "share", "wallpapers", "nyarch")
    os.makedirs(dest_dir, exist_ok=True)

    exts = (".jpg", ".jpeg", ".png", ".webp")
    copied = 0

    for name in os.listdir(src_dir):
        lower = name.lower()
        if lower.endswith(exts):
            src_path = os.path.join(src_dir, name)
            if os.path.isfile(src_path):
                shutil.copy2(src_path, dest_dir)
                copied += 1

    print(f"Wallpapers installed into {dest_dir} (copied {copied} images)")


def install_nyarch_icon_theme() -> None:
    """
    Install the Nyarch Tela-circle-MaterialYou icon theme as a user icon theme.
    """
    skel_root = _get_nyarch_skel_root()
    if skel_root is None:
        return

    src_dir = os.path.join(
        skel_root, ".local", "share", "icons", "Tela-circle-MaterialYou"
    )

    if not os.path.isdir(src_dir):
        print(f"Icons folder not found in Nyarch skel: {src_dir}")
        return

    dest_dir = os.path.join(
        REAL_HOME, ".local", "share", "icons", "Tela-circle-MaterialYou"
    )
    copy_tree_skip_missing(src_dir, dest_dir)

    print(f"Icons installed into {dest_dir}")


def install_gtk_themes_for_kde() -> None:
    """
    Install Nyarch GTK themes + GTK 3/4 configs for use under KDE.
    """
    skel_root = _get_nyarch_skel_root()
    if skel_root is None:
        return

    src_themes = os.path.join(skel_root, ".local", "share", "themes")
    src_gtk3 = os.path.join(skel_root, ".config", "gtk-3.0")
    src_gtk4 = os.path.join(skel_root, ".config", "gtk-4.0")

    if not os.path.isdir(src_themes):
        print(f"GTK themes folder not found in Nyarch skel: {src_themes}")
    if not os.path.isdir(src_gtk3) and not os.path.isdir(src_gtk4):
        print("No gtk-3.0 / gtk-4.0 configs found in Nyarch skel.")

    themes_dest = os.path.join(REAL_HOME, ".local", "share", "themes")
    gtk3_dest = os.path.join(REAL_HOME, ".config", "gtk-3.0")
    gtk4_dest = os.path.join(REAL_HOME, ".config", "gtk-4.0")

    os.makedirs(os.path.dirname(themes_dest), exist_ok=True)
    os.makedirs(os.path.dirname(gtk3_dest), exist_ok=True)

    # 1) Copy themes
    if os.path.isdir(src_themes):
        if os.path.isdir(themes_dest):
            print("Backing up existing themes to ~/.local/share/themes-backup")
            backup_dir = os.path.join(REAL_HOME, ".local", "share", "themes-backup")
            if not os.path.isdir(backup_dir):
                os.rename(themes_dest, backup_dir)

        print(f"Copying Nyarch GTK themes into {themes_dest} ...")
        if os.path.isdir(themes_dest):
            for entry in os.listdir(src_themes):
                src_entry = os.path.join(src_themes, entry)
                dest_entry = os.path.join(themes_dest, entry)
                if os.path.isdir(src_entry):
                    shutil.copytree(src_entry, dest_entry, dirs_exist_ok=True)
                else:
                    shutil.copy2(src_entry, dest_entry)
        else:
            shutil.copytree(src_themes, themes_dest, dirs_exist_ok=True)

    # 2) GTK 3 config
    if os.path.isdir(src_gtk3):
        if os.path.isdir(gtk3_dest):
            print("Backing up existing gtk-3.0 to ~/.config/gtk-3.0-backup")
            backup3 = os.path.join(REAL_HOME, ".config", "gtk-3.0-backup")
            if not os.path.exists(backup3):
                os.rename(gtk3_dest, backup3)
        print(f"Copying Nyarch gtk-3.0 config into {gtk3_dest} ...")
        shutil.copytree(src_gtk3, gtk3_dest, dirs_exist_ok=True)

    # 3) GTK 4 config
    if os.path.isdir(src_gtk4):
        if os.path.isdir(gtk4_dest):
            print("Backing up existing gtk-4.0 to ~/.config/gtk-4.0-backup")
            backup4 = os.path.join(REAL_HOME, ".config", "gtk-4.0-backup")
            if not os.path.exists(backup4):
                os.rename(gtk4_dest, backup4)
        print(f"Copying Nyarch gtk-4.0 config into {gtk4_dest} ...")
        shutil.copytree(src_gtk4, gtk4_dest, dirs_exist_ok=True)

    print("Nyarch GTK themes and configs installed for KDE (GTK apps).")


def install_nyarch_fetch_tools() -> None:
    """
    Install Nekofetch and Nyaofetch into /usr/bin (system-wide).
    """
    ensure_release_info()

    if TAG_PATH is None:
        print("TAG_PATH is not initialised; cannot install fetch tools.")
        return

    urls = [
        ("nekofetch", f"{TAG_PATH}usr/local/bin/nekofetch"),
        ("nyaofetch", f"{TAG_PATH}usr/local/bin/nyaofetch"),
    ]

    for name, url in urls:
        rc = run(["sudo", "wget", "-q", "-O", name, url], cwd="/usr/bin")
        if rc != 0:
            print(f"Failed to download {name} from {url}")
            return

    run(["sudo", "chmod", "+x", "nekofetch"], cwd="/usr/bin")
    run(["sudo", "chmod", "+x", "nyaofetch"], cwd="/usr/bin")


def configure_fastfetch_theme() -> None:
    """
    Configure fastfetch/nyarch fetch config under the user's ~/.config/fastfetch.
    """
    skel_root = _get_nyarch_skel_root()
    if skel_root is None:
        return

    src_fast = os.path.join(skel_root, ".config", "fastfetch")
    dest_fast = os.path.join(REAL_HOME, ".config", "fastfetch")

    if not os.path.isdir(src_fast):
        print(f"Nyarch fastfetch config not found at {src_fast}")
        return

    # Backup existing config, if any
    if os.path.isdir(dest_fast):
        backups_root = os.path.join(REAL_HOME, ".config", "fastfetch-backup")
        os.makedirs(backups_root, exist_ok=True)

        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        archive_path = os.path.join(backups_root, f"fastfetch-{ts}.tar.gz")

        try:
            with tarfile.open(archive_path, "w:gz") as tar:
                tar.add(dest_fast, arcname="fastfetch")
            shutil.rmtree(dest_fast)
            print(f"Existing fastfetch config archived to {archive_path}")
        except Exception as exc:
            print(f"Warning: could not archive existing fastfetch config: {exc}")
            # Don't delete the existing config if backup failed

    copy_tree_skip_missing(src_fast, dest_fast)
    print(f"Fastfetch config installed in {dest_fast}")


def configure_kitty_theme() -> None:
    """
    Ensure kitty is installed, then configure it using Nyarch's kitty.conf.
    """
    if shutil.which("kitty") is None:
        print("kitty is not installed. Installing via apt...")
        rc = apt_install(["kitty"])
        if rc != 0:
            print("Failed to install kitty via apt.")
            return

    kitty_dir = os.path.join(REAL_HOME, ".config", "kitty")
    os.makedirs(kitty_dir, exist_ok=True)

    kitty_conf = os.path.join(kitty_dir, "kitty.conf")
    if os.path.exists(kitty_conf):
        sh("cd ~/.config/kitty && mv kitty.conf kitty-backup.conf")

    ensure_release_info()
    if TAG_PATH is None:
        print("TAG_PATH is not initialised; cannot configure kitty.")
        return

    kitty_url = f"{TAG_PATH}etc/skel/.config/kitty/kitty.conf"
    rc = run(["wget", "-q", "-O", "kitty.conf", kitty_url], cwd=kitty_dir)
    if rc != 0:
        print(f"Failed to download kitty.conf from {kitty_url}")
        return

    print("Kitty theme configured.")


def configure_pywal_shell() -> None:
    """
    Idempotently append a Pywal sequences hook to ~/.bashrc for the real user.
    """
    bashrc = os.path.join(REAL_HOME, ".bashrc")
    marker = "# Nyarch KDE installer: pywal color sequences"
    snippet = (
        'if [[ -f "$HOME/.cache/wal/sequences" ]]; then\n'
        '    (cat "$HOME/.cache/wal/sequences")\n'
        'fi'
    )

    ok = _append_shell_snippet_safely(
        file_path=bashrc,
        marker_comment=marker,
        snippet_body=snippet,
        conflict_hint="wal/sequences",
    )
    if not ok:
        print(
            "Did not modify ~/.bashrc due to existing wal/sequences logic. "
            "Please integrate the Pywal hook manually if needed."
        )


def configure_flatpak_gtk_overrides() -> None:
    """
    Configure Flatpak to allow GTK config access so themes apply to Flatpak apps.
    """
    sh("sudo flatpak override --filesystem=xdg-config/gtk-3.0")
    sh("sudo flatpak override --filesystem=xdg-config/gtk-4.0")
    print("Flatpak GTK overrides configured.")


def _download_flatpak_and_install(name: str, url: str) -> None:
    """
    Helper for downloading a .flatpak into the cache and installing it.
    """
    cache_dir = _ensure_cache_subdir("flatpaks")
    target = os.path.join(cache_dir, name)

    # Download quietly into cache
    rc = run(["wget", "-q", "-O", target, url])
    if rc != 0:
        print(f"Failed to download {name} from {url}")
        return

    # Install from cached file (flatpak will still ask for confirmation)
    rc = run(["flatpak", "install", target])
    if rc != 0:
        print(f"Flatpak install failed for {name}")
    else:
        print(f"{name} installed (or queued).")


def install_suggested_flatpaks() -> None:
    """
    Install suggested Nyarch Flatpaks (weebflow / general QoL apps).
    """
    sh(
        "flatpak remote-add --if-not-exists flathub "
        "https://flathub.org/repo/flathub.flatpakrepo"
    )

    sh(
        "flatpak install flathub "
        "org.gtk.Gtk3theme.adw-gtk3 "
        "org.gtk.Gtk3theme.adw-gtk3-dark "
        "info.febvre.Komikku "
        "com.github.tchx84.Flatseal "
        "de.haeckerfelix.Shortwave "
        "org.gnome.Lollypop "
        "de.haeckerfelix.Fragments "
        "com.mattjakeman.ExtensionManager "
        "it.mijorus.gearlever"
    )

    print("Suggested Flatpaks installed (or queued).")


def install_nyarch_exclusive_flatpaks() -> None:
    """
    Install Nyarch's "weeb" Flatpak bundle:

      - CatgirlDownloader
      - WaifuDownloader
      - NyarchAssistant (Waifu AI assistant)
    """
    apps = [
        (
            "catgirldownloader.flatpak",
            "https://github.com/nyarchlinux/catgirldownloader/releases/latest/download/catgirldownloader.flatpak",
        ),
        (
            "waifudownloader.flatpak",
            "https://github.com/nyarchlinux/waifudownloader/releases/latest/download/waifudownloader.flatpak",
        ),
        (
            "nyarchassistant.flatpak",
            "https://github.com/nyarchlinux/nyarchassistant/releases/latest/download/nyarchassistant.flatpak",
        ),
    ]

    for name, url in apps:
        _download_flatpak_and_install(name, url)

    print("Nyarch weeb Flatpak bundle installed (or queued).")


def install_kde_material_you_backend() -> bool:
    """
    Install KDE Material You Colors backend + deps for Plasma 6 on Debian 13.
    """
    print("Installing KDE Material You Colors backend via pipx...")

    deps = [
        "pipx",
        "build-essential",
        "python3-dev",
        "pkg-config",
        "python-dbus-dev",
        "libglib2.0-dev",
        "qml6-module-qt-labs-settings",
    ]
    rc = apt_install(deps)
    if rc != 0:
        print("Failed to install system dependencies for KDE Material You Colors.")
        return False

    pipx_path = shutil.which("pipx")
    if not pipx_path:
        print("pipx is not on PATH after install; aborting backend setup.")
        return False

    def _pipx(args: str) -> int:
        return sh(f'"{pipx_path}" {args}')

    print("Installing 'kde-material-you-colors' via pipx...")
    rc = _pipx("install kde-material-you-colors")
    if rc != 0:
        print("Failed to install 'kde-material-you-colors' via pipx.")
        print("Check pipx logs in ~/.local/state/pipx/log/ for details.")
        return False

    _pipx("inject kde-material-you-colors pywal16 || true")
    _pipx("ensurepath || true")

    ensure_local_bin_on_path()

    if shutil.which("kde-material-you-colors"):
        sh("kde-material-you-colors -c || true")
        sh("kde-material-you-colors -a || true")
    else:
        print(
            "Warning: 'kde-material-you-colors' not found on PATH even after pipx. "
            "You may need to open a new session or check pipx logs."
        )

    print("\nKDE Material You Colors backend installed and configured.\n")
    ensure_kde_material_you_plasmoid()
    print("\nKDE Material You Colors widget installed and configured.\n")

    return True


def run_user_customizations() -> bool:
    """
    Run the full Nyarch KDE user customization pipeline in one go.
    """
    install_nyarch_wallpapers()
    install_kde_material_you_backend()
    install_nyarch_icon_theme()
    install_gtk_themes_for_kde()
    configure_pywal_shell()
    configure_flatpak_gtk_overrides()
    print("Nyarch KDE user customizations applied.")
    return True


def confirm_dependencies() -> None:
    os_desc = describe_os()
    plasma_major = detect_plasma_major_version()

    print(f"Detected OS: {os_desc}")
    if plasma_major >= 6:
        print("Detected KDE Plasma 6 (OK).")
    elif plasma_major > 0:
        print(
            f"Detected KDE Plasma major version {plasma_major}. "
            "This script is designed for Plasma 6; continue at your own risk."
        )
    else:
        print(
            "Could not detect KDE Plasma from 'plasmashell --version'. "
            "This script is intended for KDE Plasma 6 on Debian 13."
        )

    base_str = " ".join(BASE_DEPENDENCIES)
    response = input(
        "\nThis script will use apt to install the following base packages:\n"
        f"  {base_str}\n"
        "Proceed? (Y/n): "
    ).strip()

    if response and response.lower() not in ("y", "yes"):
        print("Aborting at user request; no changes made.")
        sys.exit(0)

    install_base_dependencies()
    print("Base dependencies installed. Continuing...\n")


def main() -> None:
    show_banner()
    confirm_dependencies()

    options = [
        (
            "[USER] Run full Nyarch KDE user theming (wallpapers, Material You backend + plasmoid, icons, GTK themes, Pywal hook, Flatpak GTK overrides)?",
            run_user_customizations,
            "Nyarch KDE user theming applied!",
        ),
        (
            "[SYSTEM] Install Kitty && Customizations: Apply Nyarch customizations to kitty terminal?",
            configure_kitty_theme,
            "Kitty configured!",
        ),
        (
            "[SYSTEM] Install Nekofetch and Nyaofetch + configure fastfetch?",
            lambda: (install_nyarch_fetch_tools(), configure_fastfetch_theme()),
            "Nyarch fetch tools configured!",
        ),
        (
            "[SYSTEM] Install Nyarch Suggested applications (Nyarch Flatpak apps)?",
            install_suggested_flatpaks,
            "Nyarch Flatpak apps installed!",
        ),
        (
            "[SYSTEM] Install Nyarch Apps (Catgirl / Waifu / Assistant)?",
            install_nyarch_exclusive_flatpaks,
            "Nyarch Apps installed!",
        ),
    ]

    print("\nWhat do you want to install/configure?")
    for idx, (desc, _, _) in enumerate(options, start=1):
        print(f"  [{idx}] {desc}")
    print("  [0] Do nothing / skip everything")

    choice_str = input(
        "Enter numbers to install, separated by spaces (e.g. '1 3 5'), or press Enter to skip: "
    ).strip()

    selected: set[int] = set()
    if choice_str:
        for part in choice_str.split():
            if part.isdigit():
                num = int(part)
                if 1 <= num <= len(options):
                    selected.add(num)

    for idx, (_, func, done_msg) in enumerate(options, start=1):
        if idx in selected:
            result = func()
            if result is None:
                result = True
            if result and done_msg:
                print(done_msg)

    print(f"{RED}You may need to restart Plasma or log out and back in to see all changes.{NC}")


if __name__ == "__main__":
    main()
