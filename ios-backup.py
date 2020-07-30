#!/usr/bin/env python

import shutil
import sqlite3
from collections import namedtuple
import pathlib
import os
from itertools import groupby
from datetime import datetime
import re
import sys
import plistlib

BACKUPS = os.path.expanduser('~/Library/Application Support/MobileSync/Backup')
WHICH_BACKUP = None
MANIFEST = None

WHATSAPP_DB = None

# relative
OUTPUT_DIR = 'out'
WHATSAPP_DIR = os.path.join(OUTPUT_DIR, 'whatsapp')
WHATSAPP_MEDIA_DIR = os.path.join(WHATSAPP_DIR, 'media')
VOICE_MEMOS_DIR = os.path.join(OUTPUT_DIR, 'voicememos')

WHATSAPP_CACHE = {}


def extract_whatsapp():

  conn = sqlite3.connect(MANIFEST)
  conn.row_factory = sqlite3.Row
  c = conn.cursor()
  res = c.execute('''
    select fileID, relativePath from Files where relativePath like '%ChatStorage.sqlite';
  ''').fetchone()
  file = res['fileID']
  global WHATSAPP_DB
  WHATSAPP_DB =  '/tmp/ChatStorage.sqlite'
  shutil.copy(os.path.join(WHICH_BACKUP, file[:2], file), WHATSAPP_DB)

  for r in c.execute('''
    select fileID, relativePath from Files where relativePath like 'Message/Media/%';
  '''):
    WHATSAPP_CACHE[r['relativePath']] = r['fileID']

  conn.close()


def timestamp_to_apple(x):
  # https://medium.com/@1522933668924/extracting-whatsapp-messages-from-backups-with-code-examples-49186de94ab4
  return (datetime.fromtimestamp(x) + (datetime(2001,1,1) - datetime(1970, 1, 1)))


def mkdirp(path):
  pathlib.Path(path).mkdir(parents=True, exist_ok=True)


def ls(d):
  return [f for f in os.listdir(d) if os.path.isdir(os.path.join(d, f))]


def escape_filename(f):
  f = re.sub(r'"', '', f)
  return re.sub(r'[/:]', '-', f)

def whatsapp():
  extract_whatsapp()
  conn = sqlite3.connect(WHATSAPP_DB)
  conn.row_factory = sqlite3.Row
  c = conn.cursor()
  res = c.execute('''
  select
    m.ZISFROMME as me,
    m.ZMESSAGEDATE as date,
    s.ZPARTNERNAME as group_or_contact,
    prof.ZPUSHNAME as sender,
    m.ZTEXT as text,
    med.ZMEDIALOCALPATH as media
  from ZWAMESSAGE m
  inner join ZWACHATSESSION s on m.ZCHATSESSION = s.Z_PK
  left join ZWAMEDIAITEM med on med.Z_PK = m.ZMEDIAITEM
  left join ZWAGROUPMEMBER g on g.Z_PK = m.ZGROUPMEMBER
  left join ZWAPROFILEPUSHNAME prof on prof.ZJID = g.ZMEMBERJID
  order by s.ZPARTNERNAME, m.ZMESSAGEDATE;
  ''')

  mkdirp(WHATSAPP_MEDIA_DIR)

  media_number = 0
  group_count = 0
  message_count = 0

  # handle individual messages
  for k, g in groupby(res, lambda r: r['group_or_contact']):
    group_count += 1
    k = escape_filename(k)
    md_file = os.path.join(WHATSAPP_DIR, f'{k}.md')
    html_file = os.path.join(WHATSAPP_DIR, f'{k}.html')
    with open(md_file, 'w') as f:
      shutil.copy('pandoc.css', WHATSAPP_DIR)

      for day, g in groupby(g, lambda m: timestamp_to_apple(m['date']).date()):
        first_of_day = True
        for m in g:
          date = timestamp_to_apple(m["date"])
          if first_of_day:
            f.write(f'\n# {date.strftime("%d %B %Y")}\n\n')
            first_of_day = False
          if m['me'] == 1:
            person = 'me'
          elif m['sender']:
            person = m['sender']
          else:
            person = k

          if m['media']:
            key = f'Message/{m["media"]}'
            if key in WHATSAPP_CACHE:
              _, ext = os.path.splitext(key)
              rel_path = os.path.join('media', f'{media_number}{ext}')
              path = os.path.join(WHATSAPP_MEDIA_DIR, f'{media_number}{ext}')
              media_hash = WHATSAPP_CACHE[key]
              shutil.copy(os.path.join(WHICH_BACKUP, media_hash[:2], media_hash), path)
              media_number += 1
              if ext == '.jpg' or ext == '.png' or ext == '.webp':
                content = f'![could not load image]({rel_path})'
              elif ext == '.aac' or ext == '.mp3' or ext == '.m4a' or ext == 'opus':
                content = f'<audio controls><source src={rel_path} /></audio>'
              elif ext == '.mp4':
                content = f'<video controls><source src={rel_path} /></video>'
              else:
                content = f'[document]({rel_path})'
            else:
              content = f'`could not load media {m["media"]}`'
              print('no file found for media:', m['media'])
          elif m['text']:
            text = re.sub(r'(https?://[^ ]+)', r'<\1>', m['text'])
            if '\n' in text:
              # "Block content in list items" in pandoc manual. Replaces blank lines first for a tight list.
              paras = re.sub(r'\n\n+', '\n', text).split('\n')
              content = '\n  '.join(paras)
            else:
              content = text
          else:
            content = '`voice call/E2E encryption notice/deleted message`'

          f.write(f'- `{date.strftime("%I:%M %p")}` **{person}**: {content}\n')
          message_count += 1

    os.system(f'pandoc -s --css pandoc.css --metadata title="{k}" -f markdown-tex_math_dollars -t html "{md_file}" -o "{html_file}"')
    # print(k)

  conn.close()
  print(f'WhatsApp: exported {message_count} messages over {group_count} groups')


def voice_memos():
  conn = sqlite3.connect(MANIFEST)
  conn.row_factory = sqlite3.Row
  c = conn.cursor()

  mkdirp(VOICE_MEMOS_DIR)
  count = 0

  for vm in c.execute('''
    select fileID, relativePath from Files where relativePath like 'Media/Recordings/%.m4a';
  '''):

    shutil.copy(
      os.path.join(WHICH_BACKUP, vm['fileID'][:2], vm['fileID']), os.path.join(VOICE_MEMOS_DIR, os.path.basename(vm['relativePath'])))
    # print(vm['relativePath'])
    count += 1

  conn.close()
  print(f'Voice Memos: exported {count} files')


def main():
  if len(sys.argv) == 1:
    for d in ls(BACKUPS):
      # read backup time for each one
      with open(os.path.join(BACKUPS, d, 'Info.plist'), 'rb') as f:
        info = plistlib.load(f, fmt=plistlib.FMT_XML)
      print(f'{d}, created {info["Last Backup Date"]}')
    return

  global WHICH_BACKUP, MANIFEST
  WHICH_BACKUP = os.path.join(BACKUPS, sys.argv[1])
  MANIFEST = os.path.join(WHICH_BACKUP, 'Manifest.db')

  whatsapp()
  voice_memos()

  print('ok')


if __name__ == "__main__":
  main()
