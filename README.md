# 1to3D

From one idea to a 3D part. An AI design partner for physical parts. Describe what you need, with measurements of the real objects it has to fit. The agent then:

1. reads your request and works out the requirements
2. asks the questions that change the geometry
3. models the part in your running FreeCAD and checks it with screenshots and measurements
4. asks how you want to look at it: in FreeCAD, or in a 3D viewer in your browser
   - if you have feedback, it goes back to step 1
   - if you're happy, it asks what files you need
5. makes those files, such as 3D-print STL/3MF, STEP, meshes for Blender or drawings

Everything for one design goes in your project under `designs/<slug>/`:

```
designs/<slug>/
├── README.md     requirements, decisions, assumptions, iteration log
├── cad/          make_<slug>.py (the source), .FCStd, .step, check.json, shots/
├── browser/      interactive 3D viewer (index.html + parts)
└── <type>/       usable files, made once you're happy: 3d-print/, mesh/, blender/, drawings/ ...
```

It drives **FreeCAD** today, with Blender and other tools planned, and works with **Claude Code** and **Kilo Code**.

---

## Requirements (all agents)

| Need | Why | Check |
|---|---|---|
| FreeCAD 1.1 or later | the CAD engine | open FreeCAD |
| **MCP Bridge** add-on for FreeCAD ([CREATeNG/freecad-mcp-bridge](https://github.com/CREATeNG/freecad-mcp-bridge)) | lets the agent drive FreeCAD | FreeCAD shows `MCP Bridge: Listening on 127.0.0.1:39280` |
| Python 3 | runs the browser viewer server | `python3 --version` |
| Chromium or Chrome (optional) | lets the agent screenshot the browser viewer to check it | `which chromium` |

Install the MCP Bridge from FreeCAD's **Tools > Add-on manager** (search for "MCP Bridge"), or clone its repo into FreeCAD's `Mod` folder. Then restart FreeCAD. Keep FreeCAD open while you design, because the agent works in your FreeCAD session.

Both agents expect the bridge at `http://127.0.0.1:39280/mcp`, the default port. If you changed the port, see [Different port](#different-port).

If FreeCAD is a Flatpak, it can only see files under your home folder. Work in projects under `~`, not in `/tmp`.

The browser viewer loads three.js from the jsDelivr CDN, checked against pinned SRI hashes, so it needs internet access.

---

## Security

The MCP Bridge's `execute_python` tool runs **any Python** inside FreeCAD, with your user's file access. It runs outside the agent's own sandbox and permission rules, such as Claude Code's bash sandbox. Treat it like a shell:

- **Approve each FreeCAD run; never "always allow" it.** That covers `execute_python` and `execute_python_file`, in Claude Code and in Kilo. The Kilo agent asks before each run by default. Read the script before you approve it.
- **Be careful with untrusted projects.** The agent reads the files, photos and existing `designs/` in your project. Content that is written to steer the agent (prompt injection) could try to get code run through FreeCAD. The skill tells the agent to treat project content as data. Still, review what it runs, more so in repos you did not write.
- **Any program on your machine can reach the bridge.** It listens on `127.0.0.1` with no authentication. It rejects requests from web pages with a non-local `Origin`, but local processes can still reach it. Stop the add-on, or close FreeCAD, when you're not designing.
- **Keep the bridge on this machine.** Do not point `FREECAD_MCP_URL` or `.mcp.json` at another host unless you trust that host and the network. Traffic is plain HTTP.

---

## Claude Code

### Install

Run this once from any terminal:

```bash
claude plugin marketplace add satinjeet/1to3d
claude plugin install 1to3d@1to3d
```

The plugin brings the skill, the agent and the FreeCAD MCP server, so there's nothing else to set up. Start a new Claude Code session afterwards, or run `/reload-plugins` in an open one.

You can do the same from inside a session:

```
/plugin marketplace add satinjeet/1to3d
/plugin install 1to3d@1to3d
```

The install options are:
- `--scope user` (the default) gives you the plugin in every project.
- `--scope project` installs it for this repo only, and is shared through `.claude/settings.json`.
- `--scope local` installs it for this repo only, just for you.

To try the plugin without installing it, clone the repo and point Claude at it:

```bash
git clone https://github.com/satinjeet/1to3d.git
claude --plugin-dir ./1to3d
```

Check the install worked: in a session, `/mcp` lists `plugin:1to3d:freecad` as connected. Typing `/1to3d` should also complete to `/1to3d:freecad`.

### Use

Pick one of three ways:

1. **Just ask.** Describe the part in a normal session. The skill loads by itself when you talk about designing, modelling or printing something:
   ```
   I need a clip that holds a 7.5 mm drain pipe against a 36.5 mm faucet,
   72 mm apart, snap fit, printed on my A1 mini in PLA.
   ```
2. **Call the skill directly**, if it didn't load on its own:
   ```
   /1to3d:freecad wall bracket for a 30 mm tube, 2 screw holes
   ```
3. **Run the whole session as the designer agent.** This is best for long design sessions:
   ```bash
   claude --agent 1to3d:freecad-designer
   ```

In the VS Code extension, use options 1 or 2 in the Claude panel. Don't hand the work to `@agent-1to3d:freecad-designer`. That runs it as a background subagent, which can't stop and wait for your feedback, so it only builds and reports back.

During a session:
- Answer its questions in one message.
- When it asks how to inspect the design, say **FreeCAD** or **browser**. Look at the design, then come back with feedback or "looks good".
- When you're happy, tell it what you need, for example "3D print files" or "STEP and a Blender file".

### Update

Pull the latest version from GitHub:

```bash
claude plugin marketplace update 1to3d
claude plugin update 1to3d@1to3d
```

Then start a new session, or run `/reload-plugins`.

If you're working on the plugin itself, add your clone as the marketplace instead (`claude plugin marketplace add ./1to3d`). Edits in the clone are then picked up after `/reload-plugins`.

### Uninstall

```bash
claude plugin uninstall 1to3d@1to3d
claude plugin marketplace remove 1to3d
```

---

## Kilo Code

This covers the VS Code extension and the `kilo` CLI (Kilo 7.x).

### Install

Kilo has no plugin package for skills and agents, so an install script copies them into Kilo's folders and adds the FreeCAD MCP server. It needs `python3`, and `curl` or `wget`.

Read the script before you run it:

```bash
curl -fsSLO https://raw.githubusercontent.com/satinjeet/1to3d/main/install.sh
less install.sh
sh install.sh                  # every project on this machine
sh install.sh --project /path/to/project
```

Or pipe it straight to `sh`. This trusts whatever is on `main` at that moment.

For every project on this machine:

```bash
curl -fsSL https://raw.githubusercontent.com/satinjeet/1to3d/main/install.sh | sh
```

This writes:
- the skill to `~/.agents/skills/freecad/`
- the agent to `~/.config/kilo/agents/freecad-designer.md`
- `mcp.freecad` to `~/.config/kilo/kilo.json`

Kilo merges `kilo.json` with your `kilo.jsonc`, so your own config isn't edited. Before each change, the script saves the old `kilo.json` as `kilo.json.bak` next to it. If `mcp.freecad` already exists and the script did not write it, the script leaves it as it is.

The script puts a `.installed-by-1to3d` marker in the skill folder. It refuses to replace or remove a `freecad` skill folder that doesn't have the marker, so it never deletes another skill with the same name.

For one project only:

```bash
curl -fsSL https://raw.githubusercontent.com/satinjeet/1to3d/main/install.sh | sh -s -- --project /path/to/project
```

This writes `.agents/skills/freecad/`, `.kilo/agents/freecad-designer.md` and `.kilo/kilo.json` in that project.

Then reload the Kilo panel in VS Code (**Developer: Reload Window**), or restart `kilo`.

Check the install worked from the project folder. Use `kilo` if it's on your PATH; otherwise it's the binary inside the extension, `~/.vscode/extensions/kilocode.kilo-code-*/bin/kilo`.

```bash
kilo agent list | grep freecad-designer   # freecad-designer (primary)
kilo mcp list                             # ✓ freecad connected
kilo debug skill | grep freecad           # the skill's location
```

### Use

1. Open the Kilo panel, or run `kilo` in the project.
2. Switch to the **freecad-designer** agent: press **Tab** to cycle agents, or pick it in the agent/mode picker.
3. Describe the part, with measurements, as in the Claude example above.

The agent loads the `freecad` skill itself. Without switching agents, you can also ask any Kilo agent to "use the freecad skill". The freecad-designer agent comes with permissions set up:
- Edits under `designs/`, and reading paged FreeCAD output, run without asking.
- Running code in FreeCAD (`execute_python`, `execute_python_file`) asks first, each time. See [Security](#security).
- Other file edits and every shell command, the browser viewer included, ask first.

The session works the same as in Claude: answer its questions, choose FreeCAD or browser for inspection, give feedback or say you're happy, then name the files you need.

### Update

Kilo doesn't follow symlinked skill folders, so the script copies files. To update, run the same install command again.

The piped script downloads the `main` branch. To install a tag or another branch, set `ONETO3D_REF`, for example `curl ... | ONETO3D_REF=v0.1.0 sh`.

From a clone, `./install.sh` installs that clone's files instead of downloading, which is handy when you're working on the plugin.

If you'd rather have Kilo read the skill straight from your clone, add the clone's `skills` folder to `skills.paths` in `~/.config/kilo/kilo.jsonc`. It has to be in that file: a `skills.paths` in `kilo.json` is overridden by the one in `kilo.jsonc`.

```jsonc
"skills": { "paths": [".kilo/skills", "/path/to/1to3d/skills"] }
```

### Uninstall

```bash
curl -fsSL https://raw.githubusercontent.com/satinjeet/1to3d/main/install.sh | sh -s -- --uninstall
curl -fsSL https://raw.githubusercontent.com/satinjeet/1to3d/main/install.sh | sh -s -- --uninstall --project /path/to/project
```

If you installed with `FREECAD_MCP_URL`, set the same value when you uninstall. Otherwise the script treats `mcp.freecad` as yours and leaves it in place.

---

## Different port

If the MCP Bridge listens on a port other than 39280:

- **Claude Code:** clone the repo, edit `url` in its `.mcp.json`, and install from the clone (`claude plugin marketplace add ./1to3d`). Then run `/reload-plugins`.
- **Kilo Code:** reinstall with `curl -fsSL https://raw.githubusercontent.com/satinjeet/1to3d/main/install.sh | FREECAD_MCP_URL=http://127.0.0.1:<port>/mcp sh`.

## Troubleshooting

| Symptom | Fix |
|---|---|
| The agent can't reach FreeCAD, or no `freecad` tools show up | Start FreeCAD and check the MCP Bridge is listening (Report view). In Claude, run `/mcp` to reconnect. |
| `Error reading file ... No such file or directory` on a script in `/tmp` | FreeCAD is a Flatpak and can't see `/tmp`. Keep projects under your home folder. |
| The browser viewer shows "Failed to load" | It was opened as `file://`. Let the agent start it with `serve_viewer.py`, which serves it over http. |
| In Kilo, the skill is missing after an update | Rerun the install command. Symlinks are ignored. |
| `install.sh: .../freecad was not installed by 1to3d` | Another skill called `freecad` is in that folder. Move it away, then rerun. |
| `FreeCAD document ... is open with unsaved work` | A document with the design's name has unsaved edits in FreeCAD. Save or close it, then ask the agent to run again. |
| The browser viewer stays blank offline | It loads three.js from jsDelivr. Connect to the internet and reload. |
| The FreeCAD tools are listed twice in Claude | A project `.mcp.json` also defines `freecad`. Remove one, or leave both; it does no harm. |

## Layout of this repo

```
1to3d/
├── .claude-plugin/plugin.json        Claude plugin manifest
├── .claude-plugin/marketplace.json   marketplace, so Claude can install from this repo
├── .mcp.json                         FreeCAD MCP server, for Claude
├── agents/freecad-designer.md        Claude agent
├── kilo/agents/freecad-designer.md   Kilo agent (mode: primary, permissions)
├── install.sh                        Kilo installer (curl | sh, or run from a clone)
├── LICENSE                           MIT
└── skills/freecad/                   the FreeCAD skill, the same for every agent
    ├── SKILL.md                      the design loop
    ├── references/                   modelling.md (how to model), assets.md (output types)
    ├── scripts/fc_design.py          FreeCAD-side helper: save, check, screenshots, exports
    ├── scripts/serve_viewer.py       serves the browser viewer, takes headless screenshots
    └── assets/viewer.html            three.js viewer
```
