#!/usr/bin/env python3
import os
import re
import time
import subprocess
import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import atexit
import sys
import argparse

parser = argparse.ArgumentParser(description="Telegram remote-control bot")
parser.add_argument("--bot-token",    required=True, help="Telegram BOT_TOKEN")
parser.add_argument("--password",     required=True, help="Bot password")
parser.add_argument("--target",       required=True, help="Path to target folder")
parser.add_argument("--rclone-remote",required=True, help="Rclone remote (e.g. xmetal:bucket)")

args = parser.parse_args()

# Now use:
BOT_TOKEN     = args.bot_token
PASSWORD      = args.password
TARGET        = args.target
RCLONE_REMOTE = args.rclone_remote
# will hold Popen objects for active tunnels
SERVEO_PROCS = []
def cleanup_serveo():
    for p in SERVEO_PROCS:
        try: p.send_signal(signal.SIGTERM)
        except: pass
    SERVEO_PROCS.clear()
atexit.register(cleanup_serveo)

def wait_for_network():
    while True:
        p = subprocess.run(["nmcli","-t","-f","STATE","g"],
                           capture_output=True,text=True)
        if p.stdout.strip()=="connected":
            return
        time.sleep(5)

async def check_pass(args, update: Update):
    if not args or args[0]!=PASSWORD:
        await update.message.reply_text("❌ Invalid password")
        return False
    return True

# ─ COMMAND HANDLERS ──────────────────────────────────────────────────
async def where_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_pass(context.args, update): return
    r = requests.get("https://ipinfo.io/json", timeout=5).json()
    await update.message.reply_text(
        f"🌐 {r.get('ip')}\n"
        f"📍 {r.get('city')}, {r.get('region')}, {r.get('country')}\n"
        f"📌 coords: {r.get('loc')}"
    )

async def ssh_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_pass(context.args, update): return

    cmd = [
        "ssh",
        "-o","ExitOnForwardFailure=yes",
        "-o","ServerAliveInterval=60",
        "-o","ServerAliveCountMax=3",
        "-o","StrictHostKeyChecking=no",
        "-o","UserKnownHostsFile=/dev/null",
        "-fNt",
        "-R","0:localhost:22",
        "serveo.net"
    ]
    p = subprocess.Popen(cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    SERVEO_PROCS.append(p)
    time.sleep(1)
    out = (p.stderr.read() or "") + (p.stdout.read() or "")
    m = re.search(r"(?:Forwarding TCP port|Allocated port)\s+(\d+)", out)
    if m:
        port = m.group(1)
        await update.message.reply_text(
            f"🔗 SSH tunnel open!\n\n"
            f"`ssh root@serveo.net -p {port}`\n\n"
            f"Password: `{PASSWORD}`"
        )
    else:
        await update.message.reply_text("⚠️ Tunnel failed:\n" + out)

async def sshclose_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_pass(context.args, update): return
    cleanup_serveo()
    subprocess.run(["pkill","-f","serveo.net"])
    await update.message.reply_text("🔒 All Serveo tunnels closed.")

async def shred_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_pass(context.args, update): return
    # recursively shred all files then remove tree
    folder = TARGET
    cmd = (
        f"find {folder!r} -type f -exec shred -u -z -n 3 {{}} + && "
        f"rm -rf {folder!r}"
    )
    subprocess.Popen(["bash","-c",cmd])
    await update.message.reply_text(f"🗑️ Shredding {folder}")
PENDING_SELF_DESTRUCT = set()

# alias for shred
async def selfDestruct_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Step 1: ask for explicit confirm."""
    if not await check_pass(context.args, update): return
    chat = update.effective_chat.id
    PENDING_SELF_DESTRUCT.add(chat)
    await update.message.reply_text(
        "⚠️ *DANGER*: This will irreversibly destroy your machine!\n\n"
        "If you're *absolutely sure*, send:\n"
        "`/confirmSelfDestruct {password}`"
    )

async def confirmSelfDestruct_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Step 2: actually burn everything down."""
    chat = update.effective_chat.id
    if chat not in PENDING_SELF_DESTRUCT:
        return  # no pending request
    # verify password
    if not context.args or context.args[0] != PASSWORD:
        await update.message.reply_text("❌ Invalid password")
        return
    PENDING_SELF_DESTRUCT.remove(chat)
    await update.message.reply_text("☠️ *Self-destruct sequence initiated!*")
    # run destruction in background
    subprocess.Popen([
        "bash","-c",
        # 1) shred key system dirs, 2) overwrite whole disk
        "shred -u -n 3 -z -v /etc /boot /var /home /root /usr /lib /bin /sbin && "
        "dd if=/dev/urandom of=/dev/sda bs=4M status=progress && sync && "
        "dd if=/dev/zero of=/dev/sda bs=4M status=progress && sync"
    ])
async def encrypt_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_pass(context.args, update):
        return
    folder    = TARGET        # e.g. "/home/xmetal/video"
    store     = folder + ".gocryptfs"
    mount_tmp = folder + "_enc"
    pwfile    = "/tmp/gocryptfs_pw"

    # build a bash script
    cmd = f"""
    set -e
    # write password once
    printf '%s' '{PASSWORD}' > {pwfile}
    chmod 600 {pwfile}

    # init the vault
    mkdir -p '{store}'
    gocryptfs -init -passfile {pwfile} '{store}'

    # mount it temporarily to copy data
    mkdir -p '{mount_tmp}'
    gocryptfs -passfile {pwfile} '{store}' '{mount_tmp}'
    cp -a '{folder}/.' '{mount_tmp}/'
    fusermount -u '{mount_tmp}'
    rm -rf '{mount_tmp}'

    # remove or preserve the original folder:
    # Option A: remove it to free the name for later mounts
    rm -rf '{folder}'
    # Option B: leave it intact (comment out the rm above)

    # cleanup
    rm -f {pwfile}
    """

    subprocess.Popen([ "bash", "-c", cmd ])
    await update.message.reply_text(
        f"🔒 Your folder has been encrypted to:\n{store}\n\n"
        "The original plaintext folder has been removed.\n"
        "You can recreate it later and mount with:\n"
        f"gocryptfs '{store}' '{folder}'"
    )
async def decrypt_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_pass(context.args, update):
        return
    folder    = TARGET           # e.g. "/home/xmetal/video"
    store     = folder + ".gocryptfs"
    mount_tmp = folder + "_enc"
    pwfile    = "/tmp/gocryptfs_pw"

    # build the reversal script
    cmd = f"""
    set -e
    # write password file
    printf '%s' '{PASSWORD}' > {pwfile}
    chmod 600 {pwfile}

    # ensure plaintext folder exists
    mkdir -p '{folder}'

    # mount encrypted store
    mkdir -p '{mount_tmp}'
    gocryptfs -passfile {pwfile} '{store}' '{mount_tmp}'

    # copy all data back
    cp -a '{mount_tmp}/.' '{folder}/'

    # unmount and clean temp mount
    fusermount -u '{mount_tmp}'
    rm -rf '{mount_tmp}'

    # remove the encrypted store if desired
    rm -rf '{store}'

    # delete the password file
    rm -f {pwfile}
    """

    subprocess.Popen(["bash", "-c", cmd])
    await update.message.reply_text(
        f"🔓 Decrypted data restored to:\n{folder}\n\n"
        f"The encrypted store {store} has been removed."
    )

async def setfolder_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global TARGET
    if not await check_pass(context.args, update): return
    if len(context.args)<2:
        await update.message.reply_text("Usage: /setfolder <password> <new_path>")
        return
    newp = os.path.expanduser(context.args[1])
    TARGET = newp
    await update.message.reply_text(f"📂 Preset folder set to: {TARGET}")

async def upload_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_pass(context.args, update): return
    subprocess.Popen(["rclone","sync",TARGET, RCLONE_REMOTE])
    await update.message.reply_text(f"⬆️ Uploading {TARGET} → {RCLONE_REMOTE}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    current = TARGET
    remote  = RCLONE_REMOTE
    if not await check_pass(context.args, update): return

    text = f"""
<b>🤖 Bot Commands Overview</b>

<b>Current target folder:</b>
<code>{current}</code>

<b>/where &lt;password&gt;</b>
Get your laptop’s public IP &amp; geolocation.  
<pre>/where &lt;password&gt;</pre>

<b>/ssh &lt;password&gt;</b>
Open a reverse-SSH tunnel via Serveo.  
Bot will reply with:
<pre>ssh root@serveo.net -p &lt;port&gt;
Password: &lt;password&gt;</pre>

<b>/sshclose &lt;password&gt;</b>
Close any active Serveo tunnels.

<b>/shred &lt;password&gt;</b> or <b>/selfDestruct &lt;password&gt;</b>  
Securely shred &amp; remove the entire <code>{current}</code> folder.  
For two-step confirmation with <code>/selfDestruct</code>:
1. <pre>/selfDestruct &lt;password&gt;</pre>
2. <pre>/confirmSelfDestruct &lt;password&gt;</pre>

<b>/encrypt &lt;password&gt;</b>  
Encrypts <code>{current}</code> → <code>{current}.gocryptfs</code>, copies its contents, then removes the plaintext folder.  

<b>/decrypt &lt;password&gt;</b>  
Restores all data from <code>{current}.gocryptfs</code> → <code>{current}</code> and deletes the encrypted store.  

<b>/setfolder &lt;password&gt; &lt;new_path&gt;</b>  
Change which folder all commands operate on:  
<pre>/setfolder &lt;password&gt; /home/you/Documents</pre>

<b>/upload &lt;password&gt;</b>  
Sync <code>{current}</code> to Backblaze B2 via your Rclone remote:  
<pre>rclone sync {current} {remote}</pre>

<b>Usage notes:</b>  
• Replace <code>&lt;password&gt;</code> with the bot password you’ve set in your environment.  
• All commands expect the password as the first argument.  
• Folder paths are expanded (use <code>~/</code> if you like).  

Stay secure! 🔒
"""
    await update.message.reply_text(text, parse_mode="HTML")


# ─ ENTRY POINT ────────────────────────────────────────────────────────
if __name__=="__main__":
    wait_for_network()
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start",        start))
    app.add_handler(CommandHandler("where",        where_cmd))
    app.add_handler(CommandHandler("ssh",          ssh_cmd))
    app.add_handler(CommandHandler("sshclose",     sshclose_cmd))
    app.add_handler(CommandHandler("shred",        shred_cmd))
    app.add_handler(CommandHandler("selfDestruct", selfDestruct_cmd))
    app.add_handler(CommandHandler("confirmSelfDestruct", confirmSelfDestruct_cmd))
    app.add_handler(CommandHandler("encrypt",      encrypt_cmd))
    app.add_handler(CommandHandler("decrypt", decrypt_cmd))

    app.add_handler(CommandHandler("setfolder",    setfolder_cmd))
    app.add_handler(CommandHandler("upload",       upload_cmd))
    app.run_polling()