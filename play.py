import subprocess
import sys
import sqlite3
import os
import urllib.parse
import click
import random
from pathlib import Path

DB = "music.db"
MUSIC_DIR = Path("songs")

#def send_to_mpv(command): Not yet implemented, I'll do it later with the "Socket Update"
#   if not os.path.exists(SOCKET_PATH):
#        subprocess.Popen([
#            "xfce4-terminal",
#            "--title=mpvplayer",
#            "--command",
#            f"bash -c 'mpv --idle --input-ipc-server=/tmp/{SOCKET_PATH}'"
#        ])
#
#    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
#        s.connect(SOCKET_PATH)
#        s.send((json.dumps(command) + "\n").encode())


def search_and_get_info(query):
    cmd = [
        "yt-dlp",
        f"ytsearch1:{query}",
        "--print", "%(title)s\n%(webpage_url)s"
    ]
    print("Searching...")
    result = subprocess.run(cmd, stdout=subprocess.PIPE, text=True)
    output = result.stdout.strip().split("\n")
    if len(output) < 2:
        return None, None
    return output[0], output[1]  # title, url

@click.command()
@click.option("--url", help="Download .mp3 from this URL")
@click.option("--name", help="Search by name", multiple=True)
def download(url, name):
    """Download a song from a URL or search by name — choose one only."""
    if bool(url) == bool(name):  # Both given or both missing
        raise click.UsageError("You must specify exactly one of --url or --name.")
        return
    download_url = url
    if bool(name):
        title, download_url = search_and_get_info(" ".join(name))
        if input(f"Found: {title}\tThis song will be downloaded, Do you wish to continue? [Y/n]").lower() != "y":
            print("Download cancelled.")
            return
        
    title = input("Title: ")
    author = input("Author: ")
    tags = [tag.strip() for tag in input("Tags (comma separated): ").split(",")]

    safe_title = ("".join(c for c in title if c.isalnum() or c in " _-").rstrip().replace(" ", "-")).lower()
    out_path = MUSIC_DIR / f"{safe_title}.mp3"
    
    cmd = [
        "yt-dlp",
        "-x",
        "--audio-format", "mp3",
        "-o", str(out_path),
        download_url
    ]
    subprocess.run(cmd)
    
    #If the download is successful then it adds the new song to the database

    conn = sqlite3.connect("music.db")
    c = conn.cursor()

    c.execute("""
    INSERT INTO songs (title, author, filepath, tags) VALUES (?, ?, ?, ?)
    """, (title, author, str(out_path), ", ".join(tags)))

    conn.commit()
    conn.close()

@click.command()
@click.option("--author", help="Filter by author name")
@click.option("--tags", multiple=True, help="Filter by tag(s)")
def ls(author, tags):
    """Search songs in the database by author and/or tags."""
    conn = connect_db(DB)
    cursor = conn.cursor()

    query = "SELECT * FROM songs WHERE 1=1"
    params = []

    if author:
        query += " AND author = ?"
        params.append(author)
    if tags:
        for tag in tags:
            query += " AND tags LIKE ?"
            params.append(f"%{tag}%")

    cursor.execute(query, params)
    results = cursor.fetchall()

    if results:
        for row in results:
            click.echo(f"{row}")
    else:
        click.echo("No matching songs found.")

    conn.close()

@click.command()
@click.argument("id", required=False)
@click.option("-r", "--random", "random_flag", is_flag=True, help="Play a random song")
@click.option("-s", "--search", multiple=True, help="Search and play directly from YouTube")
@click.option("-q", "--queue", multiple=True, type=int, help="Queue multiple songs by ID")
def play(id, random_flag, search, queue):
    """Play music from the database or YouTube."""
    
    if search:
        # Play from YouTube using search
        title, url = search_and_get_info(" ".join(search))
        if url:
            subprocess.Popen(["mpv", url])
        else:
            click.echo("No matching video found.")
        return

    conn = sqlite3.connect(DB)
    c = conn.cursor()

    song_list = []

    if random_flag:
        c.execute("SELECT filepath FROM songs")
        results = c.fetchall()
        if not results:
            click.echo("No songs found in the database.")
            return
        song_list.append(random.choice(results)[0])

    elif queue:
        # Queue of song IDs
        for song_id in queue:
            c.execute("SELECT filepath FROM songs WHERE id = ?", (song_id,))
            result = c.fetchone()
            if result:
                song_list.append(result[0])
            else:
                click.echo(f"ID {song_id} not found.")

    elif id:
        c.execute("SELECT filepath FROM songs WHERE id = ?", (id,))
        result = c.fetchone()
        if result:
            song_list.append(result[0])
        else:
            click.echo("No song found with the specified ID.")

    conn.close()

    for path in song_list:
        # Non-blocking playback — allows other terminal interaction
        subprocess.Popen(["mpv", path])

@click.group()
def cli():
    MUSIC_DIR.mkdir(exist_ok=True)
    conn = sqlite3.connect("music.db")
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS songs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT,
        author TEXT,
        filepath TEXT,
        tags TEXT
    )
    """)
    print()
    conn.commit()
    conn.close()

cli.add_command(download)
cli.add_command(ls)
cli.add_command(play)

if __name__ == "__main__":
    cli()