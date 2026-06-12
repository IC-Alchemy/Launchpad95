# Looping Clip Mode Current Progress

## Overview

Looping Clip Mode is the third `User 1` sub-mode in this fork:

`instrument -> device -> looping clip`

It turns the Launchpad 8x8 grid into a clip-loop view for the currently selected Ableton Live scene. Each visible track gets a lane on the grid, and each pad represents one equal slice of the clip between `start_marker` and `end_marker`.

The current implementation works with both audio and MIDI clips, but it only edits the clip loop brace:

- Reads `clip.loop_start`
- Reads `clip.loop_end`
- Reads `clip.start_marker`
- Reads `clip.end_marker`
- Writes `clip.loop_start`
- Writes `clip.loop_end`

It does **not** currently move, trim, or delete MIDI notes.

## What The Code Actually Does

### Track layouts

Two layouts are implemented:

- `4-track mode` is the default. Each track gets 2 rows, so each lane has 16 pads.
- `8-track mode` gives each track 1 row, so each lane has 8 pads.

Grid mapping in `LoopingClipModeComponent`:

```text
4-track mode
Rows 0-1 -> visible track 0
Rows 2-3 -> visible track 1
Rows 4-5 -> visible track 2
Rows 6-7 -> visible track 3

8-track mode
Row 0 -> visible track 0
Row 1 -> visible track 1
...
Row 7 -> visible track 7
```

### Time slicing

The mode divides the clip marker range evenly:

- In `4-track mode`, the range from `start_marker` to `end_marker` is split into 16 equal slices.
- In `8-track mode`, the same range is split into 8 equal slices.

That means quantization is tied to the current layout mode, not to the current loop length.

Formula used by the component:

```text
slice_size = (end_marker - start_marker) / 16   # 4-track mode
slice_size = (end_marker - start_marker) / 8    # 8-track mode
```

The last pad in a lane is special: when you loop to that final slice, the component sets the loop end to the clip's `end_marker`, not to a synthetic subdivision just before it.

### Clip selection

For each visible lane, the component looks up:

- the track at `track_offset + lane_index`
- the clip slot at the current `selected_scene_index`

If that clip slot has a clip, the lane becomes active. If not, the lane is rendered as empty.

### Scene following

The component follows Live's selected scene through `on_selected_scene_changed()`. When the selected scene changes, it drops old listeners, resolves new clip slots, and redraws the grid.

### Playback display

The playhead light is shown only when both of these are true:

- the clip itself is playing
- the Live song transport is playing

Otherwise the loop is still editable, but there is no moving playhead indicator.

## Current Pad Interaction

### Implemented behavior

The present pad handler is simplest to think of as a "pick a slice, then commit on release" interaction:

1. Press a pad.
2. That pad becomes the pending start step.
3. Release the pad.
4. The component sets a one-slice loop for that step.

So today, the reliably implemented gesture is a single-slice loop selection.

### Range-selection scaffolding

The codebase already contains the machinery for multi-step ranges:

- `pending_start_step`
- `pending_end_step`
- `_set_clip_loop_range(state, start_step, end_step)`

That means the component internals can represent larger loop spans, but the current `_matrix_value()` gesture flow does not yet provide a polished "hold one pad, choose another pad, commit full range" user interaction.

### Double-tap state

The component records:

- `last_pad_time`
- `last_pad_index`

but the current release logic applies the same result in both branches. In other words, there is no distinct double-tap behavior yet even though timing state is already being tracked.

## Buttons And Controls

### Implemented side-button bindings

Only two side-button hooks are owned by `LoopingClipModeComponent` right now:

- `side_buttons[0]`: toggles `4-track` / `8-track`
- `side_buttons[2]`: registered as a quantization button, but the handler is currently a no-op

The quantization button does not cycle values. Its LED is simply set to the default on/off skin values and then turned off.

### Navigation and banking

The component contains:

- `_track_offset`
- `_nudge_track_offset(delta)`

but no top-button or side-button banking control is wired inside this component at the moment.

So in the current implementation:

- scene following is active
- manual track banking is not exposed through button bindings here

If track banking is added later, the helper method already exists.

## Visual States

These are the colors written by `_render_grid()`:

| Grid state | Skin key |
|---|---|
| Empty visible lane | `LoopingClipMode.TrackEmpty` |
| Pad outside current loop | `LoopingClipMode.PadOff` |
| Pad inside current loop | `LoopingClipMode.PadInLoop` |
| Loop start pad | `LoopingClipMode.PadStart` |
| Loop end pad | `LoopingClipMode.PadEnd` |
| Playhead pad | `LoopingClipMode.Playing` |
| Pending start pad | `LoopingClipMode.PadSelected` |

When the mode is disabled, `_clear_grid()` sets the whole matrix to `DefaultButton.Disabled`.

## OSD

The current on-screen display is intentionally minimal:

- Mode name: `Looper 4-Trk` or `Looper 8-Trk`
- Attribute 0 name: `Tracks`
- Attribute 0 value: visible track range such as `1-4` or `1-8`

All other OSD attribute and info slots are blanked.

## Component Structure

`LoopingClipModeComponent` keeps one `TrackLoopState` per possible visible lane. Each state holds:

- `track`
- `clip`
- `clip_slot`
- `loop_start`
- `loop_end`
- `clip_start`
- `clip_end`
- `playhead`
- `pending_start_step`
- `pending_end_step`
- `last_pad_time`
- `last_pad_index`

This makes each lane behave like a self-contained "track strip" on the grid.

## Integration Notes

The mode is wired into the rest of the script in these places:

- [Settings.py](/z:/Codezzz/MusicCode/Launchpad95PolyMetric/Settings.py) adds `"looping clip"` to `USER_MODES_1`
- [MainSelectorComponent.py](/z:/Codezzz/MusicCode/Launchpad95PolyMetric/MainSelectorComponent.py) instantiates `LoopingClipModeComponent`, enables it from the `User 1` sub-mode selector, and maps it to the `LoopingClipMode` skin
- [SkinMK2.py](/z:/Codezzz/MusicCode/Launchpad95PolyMetric/SkinMK2.py) defines the pad colors and mode-button colors

In `MainSelectorComponent.channel_for_current_mode()`, Looping Clip Mode uses MIDI channel `10` internally, which corresponds to channel `11` in the usual 1-based MIDI numbering.

## Current Limitations

These are important if you are reading the code and expecting more than what is shipped today:

- Multi-pad range selection is only partially scaffolded.
- Double-tap timing is tracked, but there is no distinct double-tap action yet.
- The quantization button is a placeholder.
- Manual track banking is not currently bound to buttons in this component.
- MIDI note content is untouched; only the loop brace changes.

## Color Reference

From `SkinMK2.py`:

```python
class LoopingClipMode:
    PadOff = Rgb.DARK_GREY
    PadInLoop = Rgb.BLUE_THIRD
    PadStart = Rgb.GREEN
    PadEnd = Rgb.RED
    Playing = Rgb.GREEN_PULSE
    PadSelected = Rgb.AMBER_BLINK
    TrackEmpty = Rgb.BLACK

    class Toggle:
        On = Rgb.LIGHT_BLUE
        Off = Rgb.LIGHT_BLUE_THIRD
```

Mode button colors:

```python
class Mode:
    class LoopingClipMode:
        On = Rgb.RED
        Off = Rgb.RED_THIRD
```
