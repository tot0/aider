# Persistent Memory

Aider can keep running notes for a project. Notes are stored in a markdown file
and automatically loaded at startup. The contents of this file are prepended to
the initial system prompts so the assistant can remember important details about
your code base.

Use `--memory-file PATH` to choose the location of the file. By default the file
`/.aider/memory.md` is placed in the root of your git repository (or the current
directory if no repo is found).

Within a chat session you can update the notes by appending text or asking the
model to summarize them. Call `Memory.append(text)` to add new information and
`Memory.summarize()` to condense the file using the chat summarizer.
