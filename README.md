# Nyarcher

Nyarcher **started life as a shell script** to install  
[Nyarch Linux](https://github.com/NyarchLinux/NyarchLinux) customizations on various distros.

Icy is now converting it to **Python**, fixing bugs, and making it play nicely with  
**Debian 13 + KDE Plasma 6** — *without* trying to cosplay as a full Nyarch install.

---

> <span style="color:#ff3333; font-weight:900; font-size:130%">STOP</span> before you go wild with this script…

- I **strongly** recommend installing **Timeshift** and taking a snapshot that  
  **includes your home directory**.
  - If you don't like the changes, you can yeet everything and go back to a clean state in a few minutes.

- If you ever decide you want the **original dev’s full Nyarch experience**, you can:
  - install **GNOME** as a desktop environment
  - then run the **original upstream Nyarcher script** on top of that.

- I tested their script too — it works, but there are bugs/quirks.
  After reverse-engineering it, I ended up with this version instead:
  a **“best of both worlds”** setup where:
  - you keep **KDE**
  - you still get a bunch of **Nyarch goodies**
  - you **don’t** have to swap OS/DE just to enjoy the aesthetic.

If you eventually want the *full* Nyarch experience, you’d just install their OS anyway.  
This script is intentionally more minimal than going full GNOME.

---

## Icy's Disclaimer

I work with **generative AI** and do my best to vet everything that lands in this repo.  
Still: **treat all code here with scrutiny** unless I explicitly mark it as reviewed and blessed in this codebase.

> **Status:** `In-Dev` — **UNAPPROVED BY ICY** for general use. Expect rough edges.

---

## What this script *tries* to do

- Give you a **Nyarch-flavored KDE setup** on **Debian 13**:
  - Nyarch wallpapers
  - Nyarch icon theme (Tela-circle-MaterialYou)
  - GTK themes + configs wired into KDE
  - Pywal hook for terminal theming
  - Flatpak overrides so GTK themes apply to Flatpak apps
  - Optional:
    - kitty + Nyarch kitty config (**[SYSTEM]**)
    - Nekofetch / Nyaofetch in `/usr/bin` + fastfetch config (**[SYSTEM]**)
    - Nyarch “suggested” Flatpaks (**[SYSTEM]**)
    - Nyarch “weeb bundle”: CatgirlDownloader / WaifuDownloader / NyarchAssistant (**[SYSTEM]**)
    - KDE Material You Colors backend + plasmoid via `pipx` + `kpackagetool6`

- Avoid touching system files **unless** a menu entry is explicitly tagged as **`[SYSTEM]`**.  
  Those options:
  - install packages with `apt`
  - drop binaries into `/usr/bin`
  - tweak global Flatpak behavior

Everything else is scoped to **your user config** under `$HOME`.

---

## Requirements / Scope

This port is **aimed at**:

- **Debian 13 (Trixie)**  
- **KDE Plasma 6** as the desktop environment  
- A normal `sudo` setup and working `apt`  

The script will install its own base deps (`curl`, `wget`, `flatpak`, etc.) after you confirm.

> GNOME 47 is **not required** here — that line from upstream docs does **not** apply to this KDE port.

---

## How to run

```bash
git clone https://github.com/Icywhisker-Official/Nyarcher.git
cd Nyarcher
chmod +x debianyarcher.py
./debianyarcher.py
