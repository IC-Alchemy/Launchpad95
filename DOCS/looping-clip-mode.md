# Technical Specification: Looping Clip Mode Plan

## Overview

A new user mode for Launchpad95, accessed by pressing the **User 1** button 3 times (cycling through instrument → device → looping clip). The mode provides a multi-track visual clip looper using the full 8×8 pad matrix, allowing users to set loop start/end points for up to 4 tracks (16 pads each) with a toggle to 8 tracks (8 pads each).

**Clip support:** Both audio clips and MIDI clips. The mode operates on `clip.loop_start` / `clip.loop_end` / `clip.start_marker` / `clip.end_marker` properties. For MIDI clips, it also repositions notes to stay within the clip loop range when loop endpoints change.

---

## Architecture

### New Files

| File | Purpose |
|------|---------|
| `LoopingClipModeComponent.py` | Top-level `CompoundComponent` — owns the matrix, tracks, OSD, side/top button assignments |

### Modified Files

| File | Change |
|------|--------|
| `Settings.py` | Add `"looping clip"` to `USER_MODES_1` |
| `MainSelectorComponent.py` | Instantiate `LoopingClipModeComponent`, add `_setup_looping_clip_mode()`, add `getSkinName` mapping, update `_setup_sub_mode` |
| `SkinMK2.py` | Add `LoopingClipMode` color class |

---

## Mode Selection

Pressing **User 1** cycles through `USER_MODES_1` sub-modes:

```
press 1 → instrument
press 2 → device  
press 3 → looping clip   ← NEW
press 4 → instrument (wraps)
```

`Settings.USER_MODES_1` becomes:

```python
USER_MODES_1 = [
    "instrument",
    "device",
    "looping clip"
]
```

`MainSelectorComponent._setup_sub_mode` gains a new branch for `"looping clip"`.

`MainSelectorComponent.getSkinName` gains: `"looping clip" → "LoopingClipMode"`.

---

## Matrix Layout

### 4-Track Mode (default)
Full 8×8 grid divided into 4 horizontal lanes of 16 pads each:

```
Row 0-1 → Track 0  (16 pads = columns 0-7 × rows 0-1)
Row 2-3 → Track 1  (16 pads)
Row 4-5 → Track 2  (16 pads)
Row 6-7 → Track 3  (16 pads)
```

Each pad represents `1/16` of the clip's loop length when quantization is set to a 16-step constraint.

### 8-Track Mode (toggled)
Full 8×8 grid divided into 8 horizontal lanes of 8 pads each:

```
Row 0 → Track 0  (8 pads = columns 0-7)
Row 1 → Track 1  (8 pads)
...
Row 7 → Track 7  (8 pads)
```

Each pad represents `1/8` of the clip's loop length when quantization is set to an 8-step constraint.

### Quantization Rule

- **4-track mode:** The clip's `loop_end - loop_start` is constrained to multiples of 16 steps. Setting a loop range snaps endpoints to 1/16 boundaries.
- **8-track mode:** The clip's `loop_end - loop_start` is constrained to multiples of 8 steps. Setting a loop range snaps endpoints to 1/8 boundaries.

The length constraint is enforced when setting loop positions: the loop length `(end - start)` must be evenly divisible by the mode's step count (16 or 8).

---

## Interaction Model

### Setting Loop Start
Press a pad within a track's row(s). The pad's column position maps to a time offset within the clip:

```
4-track:  offset = (column * 2 + sub_row) * (clip_loop_length / 16)
8-track:  offset = column * (clip_loop_length / 8)
```

Pressing a pad stores it as the **pending loop start**. The pad lights up in the "start selected" color.


### Double-Press (Single-Pad Loop)
A double-press (two presses of the **same** pad within 250ms) loops only that pad's segment:

```
4-track: loops 1/16 of the clip (single pad duration)
8-track: loops 1/8 of the clip (single pad duration)
```

The loop range is set to `[pad_offset, pad_offset + segment_length]`.

### Visual States

| State | Color |
|-------|-------|
| Empty track (no clip) | `DefaultButton.Disabled` (off) |
| Pad outside loop range | `LoopingClipMode.PadOff` (dim) |
| Pad inside loop range | `LoopingClipMode.PadInLoop` |
| Pad at loop start boundary | `LoopingClipMode.PadStart` (bright) |
| Pad at loop end boundary | `LoopingClipMode.PadEnd` (bright) |
| Playhead on pad | `LoopingClipMode.Playing` (pulse) |
| Pending start select (held) | `LoopingClipMode.PadSelected` (blink) |

---

## Track Management

### Track Selection
The mode operates on the first N tracks visible in Ableton Live's session, starting from a configurable track offset (using nav buttons to bank).

- **4-track mode:** Shows tracks `offset` through `offset + 3`
- **8-track mode:** Shows tracks `offset` through `offset + 7`

Navigation buttons (top buttons 0/1 or 2/3) scroll the track offset by 4 in 4-track mode, or by 8 in 8-track mode.

### Clip Detection
For each track, if that track has a clip slot at the currently selected scene:
- If the clip exists and is playing, the clip reference is stored and its loop properties are read.
- If no clip exists or the slot is empty, the track row(s) show as disabled.

### Audio vs MIDI
- **Audio clips:** `loop_start` / `loop_end` / `start_marker` / `end_marker` are set directly.
- **MIDI clips:** Same loop properties are set. Additionally, existing MIDI notes that fall outside the new loop range are either trimmed or the clip content is repositioned (stretch/trim behavior TBD — simplest approach: notes outside the new loop range are deleted to prevent orphaned events).

---

## Toggle: 4-Track ↔ 8-Track

A side button toggles the view between 4-track and 8-track configurations.

**Proposed button:** Side button 1 (topmost side button, same position as "Vol" in mixer mode).

- Tap to toggle between 4-track and 8-track.
- The OSD shows the current mode: `"Looper 4-Trk"` or `"Looper 8-Trk"`.
- Toggling resets the track layout and re-renders the grid.
- Loop positions are preserved per track; the visual representation changes but the clip data is not modified.

---

## Side Button Assignments

| Side Button | 4-Track / 8-Track Mode | Function |
|-------------|------------------------|----------|
| 1 (Vol)     | Both                   | Toggle 4-track / 8-track |
| 2 (Pan)     | Both                   | Track bank left / quantization cycle |
| 3 (SndA)    | Both                   | Track bank right |
| 4 (SndB)    | Both                   | Reserved / shift modifier |
| 5 (Stop)    | Both                   | Stop all clips on visible tracks |
| 6 (Trk On)  | Both                   | Mute/unmute current track |
| 7 (Solo)    | Both                   | Solo current track |
| 8 (Arm)     | Both                   | Arm current track for recording |

---

## Top Button Assignments

| Top Button              | Function |
|-------------------------|----------|
| 0 (Up nav)              | Scene up |
| 1 (Down nav)            | Scene down |
| 2 (Left nav)            | Track bank left (scroll by 4 or 8 tracks) |
| 3 (Right nav)           | Track bank right (scroll by 4 or 8 tracks) |
| 4 (Session)             | Return to Session mode |
| 5 (User1)               | Cycle User1 sub-modes |
| 6 (User2)               | Cycle User2 sub-modes |
| 7 (Mixer)               | Enter Mixer mode |

---



### Key Methods

```
__init__(matrix, side_buttons, top_buttons, control_surface)
  → Register self with control surface, initialize listeners

set_enabled(enabled)
  → Enable/disable grid, register/deregister listeners

update()
  → Read clip states for all visible tracks, render grid

_matrix_value(value, x, y, is_momentary)
  → Handle pad press/release in the grid

_set_loop_range(track_index, start_step, end_step)
  → Quantize start/end to mode-appropriate boundaries, apply to clip

_toggle_track_mode()
  → Switch between 4-track and 8-track, re-render

_refresh_track_states()
  → Re-read clip references for current track offset and scene

_render_grid()
  → Write the grid back buffer, flush to hardware, manage LED caching
```

---

## OSD Layout

```
╔══════════════════════════╗
║ Looping Clip Mode        ║   mode name
║ Scale: ---               ║   attr 0
║ Root : ---               ║   attr 1
║ Tracks: 4-track (1-4)    ║   attr 2  (or "8-track (1-8)")
║ Quant : 1/16             ║   attr 3
║                          ║   attr 4-7 unused
║ track : Track Name       ║   info 0
║ clip  : Clip Name        ║   info 1
╚══════════════════════════╝
```

---

## Color Definitions (SkinMK2.py)

```python
class LoopingClipMode:
    PadOff = Rgb.DARK_GREY        # Pad representing time outside loop range
    PadInLoop = Rgb.BLUE_THIRD    # Pad inside loop range (dim)
    PadStart = Rgb.GREEN          # Pad at loop start boundary
    PadEnd = Rgb.RED              # Pad at loop end boundary
    Playing = Rgb.GREEN_PULSE     # Playhead position
    PadSelected = Rgb.AMBER_BLINK # Pending start selection (held)
    TrackEmpty = Rgb.BLACK        # No clip on this track's pads
```

Mode button tint:
```python
class Mode:
    class LoopingClipMode:
        On = Rgb.RED
        Off = Rgb.RED_THIRD
```

---

## Implementation Order

1. **Settings.py** — Add `"looping clip"` to `USER_MODES_1`
2. **SkinMK2.py** — Add `LoopingClipMode` and `Mode.LoopingClipMode` color classes
3. **LoopingClipModeComponent.py** — Create the new component with:
   - Constructor: register matrix listener, side button listeners, initialize track state
   - `set_enabled()`: enable/disable, register/deregister Live listeners
   - `update()`: poll clip states, render grid
   - `_matrix_value()`: handle pad interactions (start/end/double-press)
   - `_toggle_track_mode()`: 4-track ↔ 8-track
   - `_render_grid()`: LED output with caching
   - `_set_clip_loop_range()`: quantized loop position update
   - Track navigation and clip listeners
4. **MainSelectorComponent.py** — Wire the new component:
   - Import `LoopingClipModeComponent`
   - Instantiate in `__init__()`
   - Add `_setup_looping_clip_mode()` setup method
   - Add `"looping clip"` branch in `_setup_sub_mode()`
   - Add `"looping clip" → "LoopingClipMode"` in `getSkinName()`
   - Handle mode button update in `_update_mode_buttons()`
   - Handle channel in `channel_for_current_mode()`

---

## Edge Cases & Constraints

- **No clip on a track:** Track pads show `TrackEmpty`. Pressing a pad on an empty track does nothing.
- **Clip is not playing:** Loop positions can still be edited. Playhead indicator is hidden.
- **MIDI clip with notes outside new loop range:** Notes outside the new `[loop_start, loop_end]` range are deleted from the clip to keep the clip clean. Time values of remaining notes are preserved relative to loop_start.
- **Double-press timing:** Uses a 250ms window (same as existing `LoopSelectorComponent`).
- **Track banking boundaries:** Cannot scroll past `len(song().tracks)`. Nav button LEDs reflect scrollability.
- **Component cleanup on mode exit:** `set_enabled(False)` deregisters all Live listeners and turns off all LEDs.
