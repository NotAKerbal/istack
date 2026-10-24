# Linux Computer Use

A local MCP server and Codex plugin for controlling native Linux applications. On this Ubuntu 24.04 GNOME Wayland machine, a trusted **per-user desktop service** uses GNOME's native Mutter interface, PipeWire, GStreamer, and AT-SPI. It starts desktop control on demand without the portal sharing picker and keeps the session available across agent connections. The original XDG portal backend remains available as a portable fallback.

This plugin is part of the [istack](../../README.md) collection at `plugins/linux-computer-use`. Run the commands below from this folder, or run the same script names from the istack root, which forwards them here. The plugin keeps its own `package.json`, `package-lock.json`, and `node_modules`, so this folder is self-contained when Codex or the service installer copies it.

This is an independent implementation with a Codex-style observe → act → verify workflow. It controls the live primary monitor in native mode (the selected monitor in portal mode) and the focused application's keyboard. It operates with the signed-in user's privileges. A locked desktop must be unlocked by the user; administrator operations still require their usual authorization. Background app isolation and browser DOM automation are separate capabilities. GNOME's native D-Bus API is private and can change between versions; this backend has been exercised on GNOME 46. Other portal-capable desktops need their own integration testing.

## Seamless desktop service

```bash
npm ci
npm run doctor
npm run setup:service
npm run setup:codex
npm run verify:service
```

`setup:service` installs `linux-computer-use.service` into the current user's systemd configuration, enables it with the graphical session, copies its runtime into `~/.local/share/linux-computer-use/runtime`, and selects it in `~/.config/linux-computer-use/config.json`. No root service or TCP/RDP endpoint is created. Node and distribution Python must remain installed at the configured paths.

Each MCP process connects to a private Unix socket under `$XDG_RUNTIME_DIR/linux-computer-use/`. The directory is mode `0700`; the socket is `0600`. Only this account (and the machine's existing administrator) can connect. Idle MCP disconnects release ownership while retaining the native session; disconnecting during an operation cancels it. A control lease prevents simultaneous GUI input from agents. An idle owner can be replaced after 60 seconds.

The service starts capture/input lazily on the first GUI call, reuses it for subsequent calls, and reconnects after session closure when the desktop is available. It can be started again by the MCP client if the user service is stopped. It does not unlock GNOME, disable the screen lock, grant sudo, or cross user accounts. It remains an independent local service; an agent must still be running or invoked to issue actions.

```bash
systemctl --user status linux-computer-use.service
systemctl --user restart linux-computer-use.service
systemctl --user disable --now linux-computer-use.service
```

To return to portal-only operation, set `transport` to `direct` in `~/.config/linux-computer-use/config.json` and reload the MCP process. `LINUX_CUA_TRANSPORT=direct` overrides that setting for one process. `LINUX_CUA_BACKEND=mutter` selects native GNOME for a direct helper when testing without the service.

## Run

Requires Node 20+ and the distribution's Python 3. On this machine the runtime dependencies are present.

```bash
npm ci
npm run doctor
npm test
npm start                      # stdio MCP server; connect with a client
```

For a fresh Ubuntu GNOME installation:

```bash
sudo apt install python3-dbus python3-gi python3-pil gir1.2-gstreamer-1.0 \
  gir1.2-atspi-2.0 gir1.2-gtk-3.0 gstreamer1.0-pipewire \
  gstreamer1.0-plugins-base gstreamer1.0-plugins-good \
  xdg-desktop-portal xdg-desktop-portal-gnome libxkbcommon0
```

Run from the signed-in graphical session so the helper inherits its session bus, `XDG_RUNTIME_DIR`, and display environment. `LINUX_CUA_PYTHON` can override `/usr/bin/python3`; it must have the system GI, D-Bus, and Pillow modules. No root privileges are needed at runtime.

## Install in Codex

```bash
npm run setup:codex
npm run verify:codex
```

This registers the istack repository root (its `.agents/plugins/marketplace.json`, not this plugin folder) as the local `linux-desktop-local` marketplace and installs `linux-computer-use@linux-desktop-local` using the Codex CLI. If a marketplace with that name is already registered from a different path, such as an earlier checkout, setup replaces that registration; a matching registration is left as is. Codex copies this whole plugin folder, including `node_modules`, into its plugin cache, so run `npm ci` first. Setup warns if a local `artifacts/` folder exists, because that would be copied too. Reload the Codex/T3 provider process once after upgrading if it has cached old plugin tools. The server follows the local transport configuration above. Native service mode starts or resumes without the sharing picker. In portal-only mode, `computer_start` opens GNOME's **Remote Desktop** dialog: select one monitor and enable **Allow Remote Interaction**, then approve Share. The dialog may be behind the current app; use Alt+Tab. It has a three-minute timeout.

`starting: true` means setup is still running; use `computer_status` shortly afterward. Start failures appear as `lastStartError`. `desktopLocked` identifies a GNOME screen lock that can inhibit control.

The package includes portable `plugin.json`/`mcp.json` and Codex compatibility `.codex-plugin/plugin.json`/`.mcp.json`. The compatibility launch uses `./src/server.mjs` relative to Codex's installed-plugin working directory: this CLI build left `${CLAUDE_PLUGIN_ROOT}` unexpanded in arguments. The portable configuration keeps the standard `${PLUGIN_ROOT}` placeholder. The compatibility configuration explicitly forwards desktop session variables. When a client strips them, the helper can recover this user's standard `/run/user/UID/bus` and a unique Wayland socket; it never borrows another user's session. To pick among multiple sessions, pass the intended session variables explicitly.

For a client without plugin support, register this MCP command using **absolute paths**:

```json
{
  "mcpServers": {
    "linux-computer-use": {
      "command": "/absolute/path/to/node",
      "args": ["/absolute/path/to/istack/plugins/linux-computer-use/src/server.mjs"]
    }
  }
}
```

For Codex CLI MCP-only installation, run `codex mcp add linux-computer-use -- /absolute/path/to/node /absolute/path/to/istack/plugins/linux-computer-use/src/server.mjs`. Use either the plugin or MCP-only registration, so tools aren't duplicated.

## Tools

| Tool | Purpose |
| --- | --- |
| `computer_status` | Inspect dependencies, backend, lock/stop state, session, service and owner |
| `computer_start` | Start/reuse native control, resume after stop, or request portal consent |
| `computer_screenshot` | PNG plus frame ID, timestamp, pixel/logical dimensions, crop, generation |
| `computer_input` | Typed batches: click/double-click, move, drag, scroll, key chord, text, wait |
| `computer_accessibility` | Bounded AT-SPI application/element tree with ephemeral references |
| `computer_element_action` | Exact accessible action, focus, or set editable text |
| `computer_clipboard_set` | UTF-8 clipboard write when granted; useful with Ctrl+V |
| `computer_stop` | Cancel queued/in-flight operations and close the session immediately |

Start with status → screenshot in native service mode; use `computer_start` after an explicit stop or for portal mode. Then send image coordinates and the returned `frameId`:

```json
{
  "actions": [
    { "type": "click", "frameId": "FROM_SCREENSHOT", "x": 420, "y": 260 },
    { "type": "key", "keys": ["CTRL", "a"] },
    { "type": "type", "text": "Hello Linux" }
  ],
  "screenshot": true
}
```

Pointer coordinates always refer to the **returned image**, including resizing/cropping. Crops are requested in original capture pixels. The helper converts image pixels to stream-relative logical coordinates without adding the monitor origin. Frames expire after 120 seconds, sessions have distinct generations, and detected buffer-size changes close the session for a fresh selection. Re-observe after UI changes; frame IDs cannot prove that a button hasn't moved since capture. Logical-only display layout changes may not be detected; restart after changing display settings.

Key chords use XKB names and aliases (`CTRL`, `ALT`, `SHIFT`, `SUPER`, `Return`, `Tab`, `Escape`). Text emits literal keysyms; Unicode support varies by application/compositor. For long Unicode text, set the clipboard and send Ctrl+V. Native mode enables clipboard access by default; portal mode needs `clipboard: true` at start. Explicit `clipboard: false` keeps it disabled. Setting it replaces clipboard contents and does not restore them. Scroll deltas are logical pixels; positive `dy` scrolls down. Batches allow at most 30 actions with a 15-second estimated action budget, validate before execution, release keys/buttons in `finally`, and report `completed`/`failedIndex` on partial execution failure. Never blindly retry a partially completed batch.

AT-SPI support varies by application. Chromium/Electron applications may need accessibility enabled by their own settings. Snapshots are bounded by nodes, depth, per-call timeouts, and a traversal time budget; unavailable elements are skipped. References expire after 60 seconds or a new snapshot. Text/value interfaces are not extracted. Names may still contain sensitive application content. Semantic actions require an active desktop session but are desktop-wide: monitor selection does not sandbox AT-SPI or keyboard focus.

## Stop and recovery

Use `computer_stop` to cancel input/capture and suspend automatic service control until a subsequent explicit `computer_start`. The background service stays installed. GNOME's desktop indicator closes its current remote session; in native mode a later GUI request can create another one. Use `computer_stop` or the persistent emergency flag to pause automatic control:

```bash
npm run stop                   # Persistent emergency-stop flag
npm run resume                 # Clear flag; allow control to be opened again
```

The flag lives at `${XDG_STATE_HOME:-~/.local/state}/linux-computer-use/STOP`. Active helpers check it every 250 ms while idle and between input steps. A blocking capture/accessibility call can delay that check; revoke control or use `computer_stop` for immediate cancellation. The MCP stop tool terminates the helper and escalates after one second, releasing its D-Bus session. A per-user runtime lock prevents multiple helpers from controlling the desktop simultaneously, and service leases coordinate agents. These mechanisms do not coordinate unrelated automation tools.

No TCP/network listener is opened. Screenshots are returned in MCP responses and not saved by the service. Input text and clipboard values are not intentionally logged. Errors go to stderr; MCP clients may retain tool arguments/results. Explicit verification scripts save local reports and the desktop smoke test saves a screenshot under this plugin's ignored `artifacts/` folder. Delete it before `setup:codex` if you don't want it copied into the Codex plugin cache.

## Verification

Validated on this Ubuntu GNOME Wayland host with both portal and direct native backends: real 1280×800 capture, a screenshot-coordinate click delivered to the GTK fixture, keyboard typing, AT-SPI discovery, and Unicode clipboard paste (`✓ café 😊`). The native backend completed those actions without a sharing picker. The desktop smoke test closes its session and fixture afterward. The automated suite covers coordinate transforms, portal response handling, cancellation, helper crashes, input cleanup, private socket permissions, lease ownership, and handoff.

```bash
npm test                       # Real MCP handshake + controller invariants; no GUI actions
npm run verify:codex            # Launch Codex's resolved installed MCP config and query status
npm run test:desktop            # Click/type in a disposable GTK window using the selected backend
npm run verify:service          # Check desktop session survival across separate MCP processes
```

The desktop test clicks its own colored button using screenshot coordinates, types into its own entry, checks the actual GTK events, inspects AT-SPI, and tests Unicode clipboard paste when enabled. It saves `artifacts/desktop-smoke.png` and `.json`, then stops control and closes the fixture. In portal mode select the monitor containing that test window; native mode uses the primary monitor. This test replaces the clipboard with test text.

In portal mode GNOME's **Allow Remote Interaction** checkbox must be enabled to grant both pointer and keyboard access. Sharing only the monitor returns no input devices, which the plugin reports explicitly. Portal restore tokens are not implemented; native service mode uses GNOME's user-session interface instead.

Implementation: Node's official MCP SDK owns protocol and validation; the local service coordinates MCP connections and a long-lived Python GLib helper owns D-Bus, PipeWire, native input, and accessibility objects. `native/mutter.py` uses GNOME's private RemoteDesktop/ScreenCast interface; `native/portal.py` uses the public XDG portals. libei/EIS, recording, OCR, multi-monitor switching, and an isolated virtual desktop are future extensions.

References: [GNOME RemoteDesktop](https://gitlab.gnome.org/GNOME/mutter/-/blob/gnome-46/data/dbus-interfaces/org.gnome.Mutter.RemoteDesktop.xml), [GNOME ScreenCast](https://gitlab.gnome.org/GNOME/mutter/-/blob/gnome-46/data/dbus-interfaces/org.gnome.Mutter.ScreenCast.xml), [XDG RemoteDesktop](https://flatpak.github.io/xdg-desktop-portal/docs/doc-org.freedesktop.portal.RemoteDesktop.html), [ScreenCast](https://flatpak.github.io/xdg-desktop-portal/docs/doc-org.freedesktop.portal.ScreenCast.html), [Clipboard](https://flatpak.github.io/xdg-desktop-portal/docs/doc-org.freedesktop.portal.Clipboard.html), [OpenAI plugin packaging](https://developers.openai.com/plugins/build/plugins).
