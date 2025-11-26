#!/usr/bin/env python3
import os
import sys
import json
import subprocess
import pwd  # <-- added

RED = "\033[0;31m"
NC = "\033[0m"


def _get_real_home() -> str:
    """Return the 'real' home dir (sudo caller if present, else current)."""
    sudo_user = os.environ.get("SUDO_USER")
    if sudo_user:
        try:
            return pwd.getpwnam(sudo_user).pw_dir
        except KeyError:
            # Fallback if sudo user lookup fails
            pass
    return os.path.expanduser("~")


REAL_HOME = _get_real_home()
# Make sure anything using ~ / $HOME in Python or shell sees the sudo user's home
os.environ["HOME"] = REAL_HOME


def sh(cmd: str, cwd: str | None = None) -> int:
    """Run a shell command without exiting on failure, return exit code."""
    env = os.environ.copy()
    env["HOME"] = REAL_HOME  # ensure ~ and $HOME expand to the sudo user's home
    result = subprocess.run(cmd, shell=True, cwd=cwd, env=env)
    return result.returncode


def get_latest_tag() -> str:
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
        return tag
    except Exception as e:
        print(f"Failed to get latest Nyarch tag: {e}")
        sys.exit(1)


LATEST_TAG_VERSION = get_latest_tag()
RELEASE_LINK = f"https://github.com/NyarchLinux/NyarchLinux/releases/download/{LATEST_TAG_VERSION}/"
TAG_PATH = f"https://raw.githubusercontent.com/NyarchLinux/NyarchLinux/refs/tags/{LATEST_TAG_VERSION}/Gnome/"


def show_banner() -> None:
    sh(
        "curl https://raw.githubusercontent.com/NyarchLinux/NyarchLinux/main/Gnome/etc/skel/.config/neofetch/ascii70"
    )
    print(f"{RED}\n\nWelcome to Nyarch Linux customization installer! {NC}")


def check_gnome_version() -> None:
    try:
        out = subprocess.check_output(
            ["gnome-session", "--version"], text=True
        ).strip()
    except Exception:
        print("Unable to detect Gnome version (gnome-session --version failed).")
        sys.exit(1)

    gnome_version = out
    gnome_version_number = gnome_version.split()[-1]
    gnome_version_major = gnome_version_number.split(".")[0]

    try:
        major_int = int(gnome_version_major)
    except ValueError:
        print(f"Unable to parse Gnome version from: {gnome_version}")
        sys.exit(1)

    if major_int < 47:
        print("You need Gnome version 47 or above.")
        sys.exit(0)


def check_gnome_is_running() -> None:
    current_env = os.environ.get("XDG_CURRENT_DESKTOP", "").lower()
    if "gnome" not in current_env:
        print("Gnome isn't running, please launch gnome environment first")
        sys.exit(0)


def get_tarball() -> None:
    file_path = "/tmp/NyarchLinux.tar.gz"
    url = f"{RELEASE_LINK}NyarchLinux.tar.gz"

    if not os.path.exists(file_path):
        print(f"Downloading Nyarch tarball from {url}")
        sh(f"wget -q -O {file_path} {url}")
        sh("tar -xvf /tmp/NyarchLinux.tar.gz", cwd="/tmp")
    else:
        print("Using cached Nyarch tarball")


def install_extensions() -> None:
    print("check_gnome_version()")
    print("check_gnome_is_running()")

    sh(
        'echo "Backup old extensions to extensions-backup..." && '
        "cd ~/.local/share/gnome-shell && mv extensions extensions-backup"
    )

    get_tarball()
    sh(
        "cp -rf /tmp/NyarchLinuxComp/Gnome/etc/skel/.local/share/gnome-shell/extensions "
        "~/.local/share/gnome-shell"
    )

    # Install material you
    sh("cd /tmp && git clone https://github.com/FrancescoCaracciolo/material-you-colors.git")
    sh("cd /tmp/material-you-colors && make build && make install")
    sh(
        'npm install --prefix "$HOME/.local/share/gnome-shell/extensions/material-you-colors@francescocaracciolo.github.io"'
    )
    sh(
        'cd "$HOME/.local/share/gnome-shell/extensions/material-you-colors@francescocaracciolo.github.io" '
        "&& git clone https://github.com/francescocaracciolo/adwaita-material-you"
    )
    adw_dir = os.path.expanduser(
        "~/.local/share/gnome-shell/extensions/material-you-colors@francescocaracciolo.github.io/adwaita-material-you"
    )
    sh("bash local-install.sh", cwd=adw_dir)
    sh("chmod -R 755 extensions/*", cwd=adw_dir)

    # Install material you icons
    get_tarball()
    sh("cp -rf /tmp/NyarchLinuxComp/Gnome/etc/skel/.config/nyarch ~/.config")
    sh("cd ~/.config/nyarch && git clone https://github.com/vinceliuice/Tela-circle-icon-theme")


def install_nyaofetch() -> None:
    sh(
        f"cd /usr/bin && "
        f"sudo wget {TAG_PATH}usr/local/bin/nekofetch && "
        f"sudo wget {TAG_PATH}usr/local/bin/nyaofetch && "
        "sudo chmod +x nekofetch && sudo chmod +x nyaofetch"
    )


def configure_neofetch() -> None:
    get_tarball()
    sh("mv ~/.config/fastfetch ~/.config/fastfetch-backup")
    sh("cp -rf /tmp/NyarchLinuxComp/Gnome/etc/skel/.config/fastfetch ~/.config")


def download_wallpapers() -> None:
    sh(f"cd /tmp && wget {RELEASE_LINK}wallpaper.tar.gz && tar -xvf wallpaper.tar.gz")
    sh("bash install.sh", cwd="/tmp/wallpaper")


def download_icons() -> None:
    sh(f"cd /tmp && wget {RELEASE_LINK}icons.tar.gz && tar -xvf icons.tar.gz")
    sh("cp -rf /tmp/Tela-circle-MaterialYou ~/.local/share/icons/Tela-circle-MaterialYou")


def set_themes() -> None:
    sh("cd ~/.local/share && mv themes themes-backup")
    get_tarball()
    sh(
        "cp -rf /tmp/NyarchLinuxComp/Gnome/etc/skel/.local/share/themes ~/.local/share"
    )
    sh("cd ~/.config && mv gtk-3.0 gtk-3.0-backup && mv gtk-4.0 gtk-4.0-backup")
    sh("cp -rf /tmp/NyarchLinuxComp/Gnome/etc/skel/.config/gtk-3.0 ~/.config")
    sh("cp -rf /tmp/NyarchLinuxComp/Gnome/etc/skel/.config/gtk-4.0 ~/.config")


def configure_kitty() -> None:
    sh("mkdir ~/.config/kitty")
    sh("cd ~/.config/kitty && mv kitty.conf kitty-backup.conf")
    sh(f"cd ~/.config/kitty && wget {TAG_PATH}etc/skel/.config/kitty/kitty.conf")


def flatpak_overrides() -> None:
    sh("sudo flatpak override --filesystem=xdg-config/gtk-3.0")
    sh("sudo flatpak override --filesystem=xdg-config/gtk-4.0")


def install_flatpaks() -> None:
    sh("flatpak remote-add --if-not-exists flathub https://flathub.org/repo/flathub.flatpakrepo")
    sh("flatpak install org.gtk.Gtk3theme.adw-gtk3 org.gtk.Gtk3theme.adw-gtk3-dark")
    sh("flatpak install flathub info.febvre.Komikku")
    sh("flatpak install flathub com.github.tchx84.Flatseal")
    sh("flatpak install flathub de.haeckerfelix.Shortwave")
    sh("flatpak install flathub org.gnome.Lollypop")
    sh("flatpak install flathub de.haeckerfelix.Fragments")
    sh("flatpak install flathub com.github.tchx84.Flatseal")
    sh("flatpak install flathub com.mattjakeman.ExtensionManager")
    sh("flatpak install flathub it.mijorus.gearlever")


def install_nyarch_apps() -> None:
    sh(
        "cd /tmp && "
        "wget https://github.com/nyarchlinux/catgirldownloader/releases/latest/download/catgirldownloader.flatpak "
        "&& flatpak install catgirldownloader.flatpak"
    )
    sh(
        "cd /tmp && "
        "wget https://github.com/nyarchlinux/nyarchwizard/releases/latest/download/wizard.flatpak "
        "&& flatpak install wizard.flatpak"
    )
    sh(
        "cd /tmp && "
        "wget https://github.com/nyarchlinux/nyarchtour/releases/latest/download/nyarchtour.flatpak "
        "&& flatpak install nyarchtour.flatpak"
    )
    sh(
        "cd /tmp && "
        "wget https://github.com/nyarchlinux/nyarchcustomize/releases/latest/download/nyarchcustomize.flatpak "
        "&& flatpak install nyarchcustomize.flatpak"
    )
    sh(
        "cd /tmp && "
        "wget https://github.com/nyarchlinux/nyarchscript/releases/latest/download/nyarchscript.flatpak "
        "&& flatpak install nyarchscript.flatpak"
    )
    sh(
        "cd /tmp && "
        "wget https://github.com/nyarchlinux/waifu-downloader/releases/latest/download/waifudownloader.flatpak "
        "&& flatpak install waifudownloader.flatpak"
    )


def install_nyarch_assistant() -> None:
    sh(
        "cd /tmp && "
        "wget https://github.com/nyarchlinux/nyarchassistant/releases/latest/download/nyarchassistant.flatpak "
        "&& flatpak install nyarchassistant.flatpak"
    )


def install_nyarch_updater() -> None:
    sh(
        "cd /tmp && "
        "wget https://github.com/nyarchlinux/nyarchupdater/releases/latest/download/nyarchupdater.flatpak "
        "&& flatpak install nyarchupdater.flatpak"
    )
    sh("sudo bash -c 'echo 241104 > /version'")


def configure_gsettings() -> None:
    #check_gnome_version()
    #check_gnome_is_running()
    sh("dconf dump / > ~/dconf-backup.txt")
    get_tarball()
    dconf_dir = "/tmp/NyarchLinuxComp/Gnome/etc/dconf/db/local.d"
    sh("dconf load / < 06-extensions", cwd=dconf_dir)
    sh("dconf load / < 02-interface", cwd=dconf_dir)
    sh("dconf load / < 04-wmpreferences", cwd=dconf_dir)
    sh("dconf load / < 03-background", cwd=dconf_dir)


def add_pywal() -> None:
    bashrc = os.path.expanduser("~/.bashrc")
    with open(bashrc, "a", encoding="utf-8") as f:
        f.write('if [[ -f "$HOME/.cache/wal/sequences" ]]; then\n')
        f.write('    (cat $HOME/.cache/wal/sequences)\n')
        f.write("fi\n")


def confirm_dependencies() -> None:
    response = input(
        "Have you installed all the dependecies listed in the github page of this script? (Y/n): "
    ).strip()
    # original script only treats explicit y/yes as "yes" – empty is NOT yes
    if response.lower() not in ("y", "yes"):
        print(
            "You need to have already installed the dependencies listed on github before running this script!"
        )
        sys.exit(0)
    print("Cool! We can go ahead")


def main() -> None:
    show_banner()
    #check_gnome_version()
    #check_gnome_is_running()
    confirm_dependencies()

    # Menu mapping 1:1 to the original Y/n blocks, same order & messages
    options = [
        (
            "Install our Gnome extensions, they are important for the overall desktop customization?",
            install_extensions,
            "Gnome extensions installed!",
        ),
        (
            "[SYSTEM] Install Nekofetch and Nyaofetch and configure neofetch, to tell everyone that you use nyarch btw?",
            lambda: (install_nyaofetch(), configure_neofetch()),
            "Nyaofetch and Neofetch installed!",
        ),
        (
            "Download Nyarch wallpapers?",
            download_wallpapers,
            "Wallpapers downloaded!",
        ),
        (
            "Download our icons?",
            download_icons,
            "Icons downloaded!",
        ),
        (
            "Download our themes?",
            set_themes,
            "Themes downloaded!",
        ),
        (
            "Apply our customizations to kitty terminal?",
            configure_kitty,
            "Kitty configured!",
        ),
        (
            "Add pywal theming to your ~/.bashrc (for other shells you have to do it manually)?",
            add_pywal,
            "pywal configured!",
        ),
        (
            "Apply your GTK themes to flatpak apps?",
            flatpak_overrides,
            "Flatpak themes configured!",
        ),
        (
            "Install suggested flatpaks to enhance your weebflow (You will be able to not download only some of them)?",
            install_flatpaks,
            "Suggested apps installed!",
        ),
        (
            "[SYSTEM] Install Nyarch Exclusive applications?",
            install_nyarch_apps,
            "Nyarch apps installed!",
        ),
        (
            "[SYSTEM] Install Nyarch Assistant, our Waifu AI Assistant?",
            install_nyarch_assistant,
            "Nyarch Assistant installed!",
        ),
        (
            "[SYSTEM] Install Nyarch Updater? It's going to have some issues outside of Nyarch and Arch in general",
            install_nyarch_updater,
            "Nyarch Updater installed!",
        ),
        (
            "Edit your Gnome settings? Note that if you have not installed something before, you may experience some bugs at the start",
            configure_gsettings,
            "Nyarch apps installed!",
        ),
    ]

    print("\nWhat do you want to install?")
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

    # Execute in the same order as the original script’s Y/n sequence
    for idx, (_, func, done_msg) in enumerate(options, start=1):
        if idx in selected:
            func()
            print(done_msg)

    print(f"{RED} Log out and login to see the results! {NC}")


if __name__ == "__main__":
    main()
