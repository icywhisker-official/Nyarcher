# How `debianyarcher.py` Works

This file explains what the **Debian + KDE** port of Nyarcher (`debianyarcher.py`) actually does.

It is **not** the original `nyarcher.sh` GNOME script. This version is:

- written in **Python 3**
- targeted at **Debian 13 (Trixie)**
- designed for **KDE Plasma 6**
- focused on **user-level theming**, with a few clearly marked **[SYSTEM]** options

If you want the full upstream GNOME experience, use the original Nyarcher script on a GNOME-based system instead.

---

## Requirements

To run `debianyarcher.py` successfully, you should have:

- A working **Debian 13 (Trixie)** install
- **KDE Plasma 6** as your desktop environment
- A normal `sudo` setup (your user can run `sudo`)
- An internet connection (for downloading Nyarch assets / Flatpaks)

The script will attempt to install its own base dependencies via `apt` after you confirm.

### Base dependencies it installs automatically

These are handled by the script itself (you will be prompted first):

- `curl`
- `wget`
- `tar`
- `flatpak`
- `plasma-discover-backend-flatpak`

Other packages such as `git`, `kpackagetool6`, `pipx`, and build dependencies are installed **only when needed** by specific features (for example: the KDE Material You backend or the plasmoid installer).

---

## High-level behavior

When you run:

    ./debianyarcher.py

the script will:

1. Show a Nyarch banner in your terminal.
2. Detect your OS and Plasma version.
3. Ask for confirmation before installing base dependencies with `apt`.
4. Present an **interactive menu** with several options, grouped as:
   - one big **[USER]** customization bundle
   - several independent **[SYSTEM]** options

You can choose multiple options (e.g. `1 3 5`) or nothing at all.

---

## User vs System changes

The script clearly differentiates between:

- **User-level changes** (configs in your home directory)
- **System-level changes** (binaries in `/usr/bin`, system packages, Flatpak behavior)

System-level items are tagged as **[SYSTEM]** in the menu. Those are the only ones that touch:

- `apt` packages
- `/usr/bin/*`
- global Flatpak overrides

Everything else stays inside your home directory (`$HOME`).

If you create a new user account, that new user will not inherit the user-level customizations, but will still see system-level bits like fetch tools in `/usr/bin` or Flatpak overrides.

---

## Nyarch GitHub assets and cache

The script pulls most of its assets from the upstream Nyarch repo:

- GitHub: `NyarchLinux/NyarchLinux`

It uses the GitHub API to find the **latest release tag**, then:

- downloads `NyarchLinux.tar.gz` for that tag
- extracts it under a cache directory:

  - `~/.cache/nyarch-kde`

From that tarball, the script reads the original Nyarch skel files such as:

- wallpapers
- icons
- GTK themes
- fastfetch configs
- kitty configuration

The cache is reused between runs so you are not redownloading the tarball every time.

---

## User bundle: what the big [USER] option does

The main option in the menu is a **single long-running [USER] pipeline** that applies the full Nyarch KDE theming to your user account.

When you choose the [USER] option, the script runs all of these, in order:

1. **Install Nyarch wallpapers**  
   Copies Nyarch wallpapers from the skel tree into:

   - `~/.local/share/wallpapers/nyarch`

2. **Install KDE Material You Colors backend + plasmoid**  
   - Installs dependencies (via `apt`) needed for the KDE Material You backend and QML module.
   - Installs `kde-material-you-colors` via `pipx` and injects `pywal16` into it.
   - Ensures `~/.local/bin` is on your `PATH` for future sessions.
   - Runs `kde-material-you-colors` to generate its config and enable autostart.
   - Clones and installs/updates the **KDE Material You Colors plasmoid** (`luisbocanegra.kde-material-you-colors`) using `kpackagetool6`.

3. **Install Nyarch icon theme (Tela-circle-MaterialYou)**  
   - Copies the Nyarch icon theme into:

     - `~/.local/share/icons/Tela-circle-MaterialYou`

4. **Install GTK themes + configs for KDE**  
   - Copies GTK themes into:

     - `~/.local/share/themes`

   - Copies GTK 3 and GTK 4 configs into:

     - `~/.config/gtk-3.0`
     - `~/.config/gtk-4.0`

   - Backs up any existing themes/configs by renaming them to `*-backup` directories first.

5. **Add a Pywal hook to your Bash configuration**  
   - Appends a small, idempotent snippet to:

     - `~/.bashrc`

   - The snippet loads color sequences from `~/.cache/wal/sequences` if they exist.

6. **Configure Flatpak GTK overrides**  
   - Adds Flatpak overrides so Flatpak apps can read your GTK configs:

     - `xdg-config/gtk-3.0`
     - `xdg-config/gtk-4.0`

   - This makes Flatpak GTK apps follow the same theme you set via the GTK configs installed above.

After all of these steps, you end up with a Nyarch-flavored KDE setup for **your user only**. No system files are directly changed by the [USER] pipeline.

---

## System options: what the [SYSTEM] items do

The menu also offers several **[SYSTEM]** options. These are independent of the [USER] bundle and can be run in any order.

Each of these will write outside your home directory or globally change behavior, so they are clearly marked.

### [SYSTEM] Kitty + Nyarch Kitty config

This option:

1. Ensures `kitty` is installed via `apt` (if not already present).
2. Backs up your existing kitty config:

   - `~/.config/kitty/kitty.conf` → `kitty-backup.conf`

3. Downloads the Nyarch kitty config from the upstream repo and writes it as:

   - `~/.config/kitty/kitty.conf`

This affects **your user’s kitty configuration** but not other users.

### [SYSTEM] Nekofetch / Nyaofetch + fastfetch config

This option does two things:

1. **System-wide binaries**  
   - Downloads `nekofetch` and `nyaofetch` from the Nyarch release’s skel and installs them into:

     - `/usr/bin/nekofetch`
     - `/usr/bin/nyaofetch`

   - Marks them as executable.

2. **Per-user fastfetch configuration**  
   - Backs up any existing fastfetch config under:

     - `~/.config/fastfetch`

   - Archives old config to `~/.config/fastfetch-backup/fastfetch-<timestamp>.tar.gz`
   - Copies Nyarch fastfetch configs into:

     - `~/.config/fastfetch`

The binaries are global, but the fastfetch configs are user-specific.

### [SYSTEM] Nyarch “suggested” Flatpaks

This option:

1. Ensures the **Flathub** remote exists.
2. Installs a bundle of Nyarch-recommended Flatpaks in one shot, including:
   - GTK themes:

     - `org.gtk.Gtk3theme.adw-gtk3`
     - `org.gtk.Gtk3theme.adw-gtk3-dark`

   - Apps:

     - `info.febvre.Komikku`
     - `com.github.tchx84.Flatseal`
     - `de.haeckerfelix.Shortwave`
     - `org.gnome.Lollypop`
     - `de.haeckerfelix.Fragments`
     - `com.mattjakeman.ExtensionManager`
     - `it.mijorus.gearlever`

Flatpak will still ask for confirmation the first time you install each app.

### [SYSTEM] Nyarch “weeb” Flatpak bundle

This option installs Nyarch’s weeb-centric apps from their latest Flatpak bundles:

- CatgirlDownloader
- WaifuDownloader
- NyarchAssistant (AI assistant)

The script:

1. Downloads each `.flatpak` bundle into a cache directory under `~/.cache/nyarch-kde/flatpaks`.
2. Installs them via `flatpak install <bundle>`.

Again, Flatpak may prompt you to confirm the installation the first time.

---

## What this script does *not* do

Compared to the original `nyarcher.sh` GNOME script and the official Nyarch Linux distro, this Python KDE port **does not**:

- Install or configure GNOME Shell extensions or GNOME-specific themes.
- Use `dconf` or `gsettings` to bulk-load GNOME settings.
- Install or manage the Nyarch live ISO, Calamares installer, or boot splash (Plymouth).
- Turn Debian into a drop-in replacement for the official Nyarch OS.
- Provide a fully integrated Nyarch updater or tour experience on KDE.

It is a **theming and QoL layer** on top of **Debian 13 + KDE**, not a rebase or OS conversion.

---

## Recovery and safety tips

This script tries to be conservative:

- It backs up many existing configs before overwriting them (e.g. themes, GTK configs, fastfetch, kitty).
- User-level changes live in your home directory and are easy to remove manually.

If you want extra safety, use a snapshot tool like **Timeshift** and include your home directory so you can roll back everything in a few minutes if you don’t like the result.
