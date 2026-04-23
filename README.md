# Firewalla MSP for Home Assistant

> **Early stage / proof of concept**
> This integration is in active early development. Features, configuration, entity names, and behaviour are likely to change dramatically and frequently. Breaking changes between versions should be expected. Use at your own risk and do not rely on it for anything critical.

A Home Assistant custom integration for [Firewalla](https://firewalla.com/) Gold, Gold Plus, and Gold SE boxes managed via the Firewalla MSP API.

---

## What you get

One config entry per box. Each entry creates the following:

### Box-level entities
| Entity | Type | Description |
|--------|------|-------------|
| Online | Binary sensor | Whether the box is reachable via the MSP API |
| Devices | Sensor | Total number of network devices seen by the box |
| Rules | Sensor | Total number of firewall rules on the box |
| Alarms | Sensor | Total number of active alarms |
| Public IP | Sensor | The box's current public IP address |

### Per network device
| Entity | Type | Description |
|--------|------|-------------|
| Device tracker | Device tracker | Online/offline, IP address, MAC, group membership |
| Internet access | Switch | Toggle internet access for that device. Creates a managed block rule on first use (tagged `[HA-PAUSE]` in its notes) and reuses it on subsequent toggles. |

### Per firewall rule
| Entity | Type | Description |
|--------|------|-------------|
| Rule switch | Switch | Toggle a rule between active (ON) and paused (OFF) |

### Per device group
| Entity | Type | Description |
|--------|------|-------------|
| Group pause | Switch | Pause or resume internet access for every device in the group |

### Services
| Service | Description |
|---------|-------------|
| `firewalla.pause_device` | Block internet access for one or more device switches for a given duration, then auto-resume |
| `firewalla.pause_group` | Same as above but for a group switch |

---

## Requirements

- A Firewalla MSP account (MSP Lite is sufficient)
- A personal access token — generate one in **MSP → Account Settings → Create New Token**
- Home Assistant 2025.1 or newer

---

## Installation

### HACS (recommended)

1. In HACS, go to **Integrations → Custom repositories**
2. Add `https://github.com/petergCA/ha-firewalla` with category **Integration**
3. Install **Firewalla MSP** and restart Home Assistant

### Manual

1. Copy `custom_components/firewalla/` into your HA config directory under `custom_components/`
2. Restart Home Assistant

---

## Configuration

Go to **Settings → Devices & Services → Add Integration → Firewalla MSP**.

You will be prompted for:

1. **MSP domain** — the hostname of your MSP portal, e.g. `acme.firewalla.net`
2. **Personal access token** — from MSP Account Settings
3. **Box** — select which Firewalla box this entry manages

To manage multiple boxes, run the setup again and pick a different box each time.

### Options

After setup, click **Configure** on the integration entry to adjust:

| Option | Default | Description |
|--------|---------|-------------|
| Polling interval | 60 s | How often HA polls the MSP API (min 15 s, max 900 s) |
| Nest devices under box | On | When enabled, network devices appear as sub-devices of the box in the device registry |

---

## How managed pause rules work

When you turn off an Internet access switch (device or group), the integration creates a Firewalla block rule whose `notes` field starts with `[HA-PAUSE]`. On subsequent toggles it reuses the same rule rather than creating new ones. These rules persist in Firewalla and survive HA restarts. To fully remove them, delete them from the Firewalla app or MSP UI.

---

## Known limitations

- **No people/user support** — the MSP API does not expose a users endpoint at this time
- **No alarms detail** — alarm count is reported but individual alarms are not surfaced as entities
- **No timed rule activation** — only timed device/group pause via the service calls
- **No box diagnostics** — CPU, memory, and uptime are not available from the MSP API

---

## Troubleshooting

- **"Invalid auth" during setup** — the token was deleted or belongs to a different MSP domain
- **Config flow 500 error** — check your HA logs; usually a connectivity issue to the MSP domain
- **Entities unavailable after setup** — the box may be offline or the token may have expired; check HA logs for details
- **Group pause not working** — open an issue with your HA log output; the rule scope for groups is inferred from the API and may need adjustment for your setup

---

## Contributing / Issues

This is a personal proof-of-concept project at a very early stage. Issues and PRs are welcome but responses may be slow.

[Open an issue](https://github.com/petergCA/ha-firewalla/issues)
