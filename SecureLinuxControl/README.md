Thought for a second


# Remote-Bot

A lightweight Telegram bot for remote laptop management and “self-destruct” in case of theft.

Features include:

* **/where**: report public IP & geolocation
* **/ssh** & **/sshclose**: open/close reverse-SSH tunnel via Serveo
* **/shred** / **/selfDestruct**: securely shred or fully wipe your target folder
* **/encrypt** / **/decrypt**: wrap an existing folder in gocryptfs, or reverse it
* **/setfolder**: change the folder these commands operate on
* **/upload**: sync (via rclone) to Backblaze B2 or any supported remote

---

## Prerequisites

* Debian/Ubuntu/Parrot Linux
* git
* Internet connection

---

## Installation

```bash
git clone https://github.com/Zzatiz/linuxRemote.git
cd remote-bot
sudo chmod +x install.sh
sudo chmod +x uninstall.sh
sudo ./install.sh
```

The installer will:

1. Install dependencies

   * python3, python3-venv, python3-pip
   * gocryptfs, fuse, rclone
   * optionally openssh-server for `/ssh` and rsync for `/upload`
2. Prompt for:

   * **Telegram BOT\_TOKEN**
   * **Bot PASSWORD**
   * **gocryptfs encryption password**
   * **TARGET** folder (default `~/Videos`)
   * **RCLONE\_REMOTE** (e.g. `myremote:bucket`)
3. Deploy code to `/opt/remote-bot`
4. Write `/etc/default/remote-bot` with your settings
5. Install & enable `remote-bot.service` under systemd

View logs:

```bash
journalctl -u remote-bot -f
```

---

## Configuration

* Edit `/etc/default/remote-bot` to change settings.
* Restart service after changes:

  ```bash
  sudo systemctl restart remote-bot
  ```

---

## rclone Setup (for `/upload`)

1. Run:

   ```bash
   rclone config
   ```

2. Create a new remote (e.g. `myremote`) and choose your storage type.

3. Enter your credentials and set `hard_delete` to `true`.

4. During install, set `RCLONE_REMOTE` in .env to `myremote:your-bucket`.

---

## Usage

Send `/start <password>` to your bot for a full command list:

```
/where <password>
/ssh <password>
/sshclose <password>
/shred <password>
/selfDestruct <password> → /confirmSelfDestruct <password>
/encrypt <password>
/decrypt <password>
/setfolder <password> <new_path>
/upload <password>
```

Example:

```
/where password
```

---

## Uninstallation

```bash
sudo ./uninstall.sh
```

This will:

1. Stop & disable `remote-bot.service`
2. Remove `/etc/default/remote-bot` & service file
3. Delete `/opt/remote-bot`
4. Reload systemd

To purge dependencies:

```bash
sudo apt remove --purge python3-venv python3-pip python3 \
                  gocryptfs fuse rclone openssh-server rsync
```

---

## Security Notes

* Protect your Telegram bot token and PASSWORD.
* Rotate passwords and keys regularly.
* Test commands locally before relying on them.
* Self-destruct operations are irreversible.

---

## License

MIT © Your Name
