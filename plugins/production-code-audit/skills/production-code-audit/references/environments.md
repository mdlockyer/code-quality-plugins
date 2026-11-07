# Where things run

Before phase 0, work out the topology, because it is often not one machine. In Cowork the skill and its script live in a Linux sandbox, a folder added to the session is a synced copy of the working tree (usually without `.git` and never with the project's toolchain), and a host-shell connector such as traversal-workspace reaches the real repository on the person's machine. In Claude Code everything is one tree. Other hosts fall somewhere between.

Figure out three things and write them at the top of `recon.md`: where the repository's files can be read, where its `.git` history and build toolchain can be executed, and where you can write freely. Then use each environment for what it has:

- Read and grep files wherever they already are; the synced copy is fine for that.
- Run `git log`, the build, the tests, and the linters where the toolchain is, and bring back only their text output. On a host shell, that means running the command there and writing the output into the ledger, not running it in the sandbox against a copy that can't build.
- If `inventory.py` can't reach the repo, write the script to the host as a text file and run it there, or skip it and build the inventory by hand; the script is a convenience, not a gate.
- Keep the ledger wherever you can write most freely; a host-side sibling directory beside the repo is a good default.
- If a step needs something no reachable environment has (no `.git` anywhere, no toolchain), record that in `recon.md` as a coverage gap and move on.

**Move text, not trees.** Never archive a repository (`git bundle`, `tar`, `zip`) to transfer it between environments, and never try to upload one through a file bridge. Those bridges are built for documents and refuse or truncate archives, and even when they work you end up auditing a stale copy. Every phase below works on read access plus the text output of commands.
