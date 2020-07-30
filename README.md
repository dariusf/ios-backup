
Scripts for extracting data from iOS backups.

Assumes Catalina and iOS 13. pandoc is required on the PATH.

# Usage

1. Give your terminal `System Preferences > Security & Privacy > Privacy > Full Disk Access`
1. Create a local backup of your phone using Finder
1. `./ios-backup.py` will print a list of backups
1. `./ios-backup.py <hash>` will export files from the given backup to the current directory

## Apps

- .m4a files from Voice Memos will be copied out.
- WhatsApp chat history will be reconstructed in Markdown and HTML

# Related work

- [Adventures in WhatsApp DB — extracting messages from backups](https://medium.com/@1522933668924/extracting-whatsapp-messages-from-backups-with-code-examples-49186de94ab4)
- [pixel3rr0r/whatsapp_chat_dump](https://github.com/pixel3rr0r/whatsapp_chat_dump)

This script goes further than both of these, working with groups and all kinds of media.
