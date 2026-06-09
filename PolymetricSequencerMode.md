# Polymetric Sequencer Mode

## Overview

Polymetric Sequencer is a clip-based melodic sequencer for Launchpad95. It writes standard MIDI notes into the selected Ableton Live MIDI clip, but each musical lane can run at its own cycle length:

- Gate
- Pitch
- Octave
- Velocity
- Note Length

Because each lane can loop independently, the pattern evolves over time even when the clip loop stays fixed.

This mode is based on the melodic step sequencer, so clip following, scale handling, quantization, and lock behavior stay familiar.

## What Makes It Polymetric

Each visible step on the timeline reads data from five separate lane cycles:

- Gate decides whether the step plays.
- Pitch decides which scale degree or chord tone is used.
- Octave decides the octave.
- Velocity decides how hard the note is played.
- Length decides the note duration.

If all five lanes are set to the same length, the sequencer behaves like a normal step sequencer. If the lengths differ, the lanes drift against each other.

Example:

- Gate length = 5
- Pitch length = 7
- Octave length = 3

The clip still advances step-by-step, but each lane wraps at its own length.

## Entering The Mode

1. Press `User 2` until the OSD shows `POLYMETRIC SEQUENCER MODE`.
2. Select a MIDI track and MIDI clip in Live.
3. If no clip exists in the highlighted slot, pressing the grid creates one automatically.

This mode only works with MIDI clips.

## Grid Layout

### Parameter Pages

Most of the time, the 8x8 grid works like this:

- Columns `1-8`: timeline steps for the current page
- Rows `1-7`: values for the selected lane
- Bottom row: page markers and playhead feedback

What the top 7 rows mean depends on the selected lane:

- `Gate`: on/off trigger per step
- `Pitch`: scale degrees, with multiple notes allowed in poly mode
- `Octave`: octave value
- `Velocity`: velocity fader
- `Length`: note length fader

When a lane is shorter than the visible page, values repeat across the page. That repetition is expected and is the main visual sign that the lane is cycling independently.

### Lane Length Page

Long-press any lane button to edit that lane's cycle length.

In lane length view:

- The full 8x8 grid becomes a length picker
- Steps `1-64` are shown on the first page
- Use page navigation to reach steps `65-128`
- The selected pad is the exact lane length
- Lit pads below it show the active range

Maximum lane length is `128` steps.

## Side Button Functions

In polymetric mode, the side buttons are remapped as follows:

| Side button | Function |
| --- | --- |
| 1 | Scale edit |
| 2 | Lock / track-lock |
| 3 | Quantization / duplicate clip |
| 4 | Gate page |
| 5 | Length page |
| 6 | Octave page |
| 7 | Velocity page |
| 8 | Pitch page / mono-poly toggle |

### Tap vs Long-Press

- Tap a lane button to open that lane's edit page.
- Long-press a lane button to edit that lane's cycle length.

Lane buttons:

- `Gate`
- `Length`
- `Octave`
- `Velocity`
- `Pitch`

## Editing Notes

### Gate

Open the `Gate` page and tap a column to toggle the trigger on or off.

### Pitch

Open the `Pitch` page and tap notes in the column.

- In `Poly` mode, multiple notes can be enabled in the same step.
- In `Mono` mode, only one pitch can be active per step.
- Enabling a pitch also turns that step's gate on.

### Octave

Open the `Octave` page and tap the row you want.

### Velocity

Open the `Velocity` page and tap the row you want. Higher rows give higher velocity.

### Note Length

Open the `Length` page and tap the row you want.

The available note lengths are the inherited melodic-step values:

- `1/4 step`
- `1/2 step`
- `3/4 step`
- `1 step`
- `2 steps`
- `4 steps`
- `8 steps`

The exact musical time depends on the current quantization.

## Mono And Poly Pitch Modes

Double-tap the `Pitch` side button to switch between:

- `Poly`: chord notes allowed on each step
- `Mono`: one pitch per step

In mono mode, existing extra pitches on a step are pruned automatically.

The OSD shows the current state as `Mono` or `Poly`.

## Quantization

Tap the `Quantization` button to cycle through:

- `1/4`
- `1/8`
- `1/16`
- `1/32`

Quantization affects:

- Step spacing on the timeline
- New clip length when a clip is created from the grid
- Musical duration of the note length lane

Hold the `Quantization` button to duplicate the current clip.

## Scale Editing

Hold the `Scale` button to enter the standard Launchpad95 scale editor. Release it to return to the polymetric sequencer.

Pitch rows always follow the currently selected scale and root note.

## Locking

The `Lock` button keeps the sequencer attached to the current target.

- Tap to lock or unlock the current clip.
- Long-press to toggle track-lock mode.

When locked to track, the sequencer follows the selected track's current clip slot instead of a single fixed clip.

## Playback And Visual Feedback

- The playhead is shown on the bottom row of parameter pages.
- The playhead follows the currently active lane's cycle, not just the clip page.
- This makes it easier to see the true polymetric motion of the selected lane.

## Clip Storage And Metadata

The sequencer stores its state in two places:

- MIDI notes in the clip
- A small metadata token in the clip name for lane lengths

The clip name token looks like this:

```text
[poly:g8,p7,o5,v8,l3]
```

Meaning:

- `g` = gate length
- `p` = pitch length
- `o` = octave length
- `v` = velocity length
- `l` = note length

If a clip has no polymetric token, all lane lengths default to the current clip loop length when the clip is loaded.

If you rename the clip manually, keep the `[poly:...]` token if you want the lane lengths to survive.

## Practical Workflow

1. Enter `Polymetric Sequencer Mode`.
2. Select or create a MIDI clip.
3. Program a basic rhythm on the `Gate` page.
4. Program notes on the `Pitch` page.
5. Set octave, velocity, and note length.
6. Long-press lane buttons to give each lane a different cycle length.
7. Let the pattern run and adjust lengths until the interaction feels right.

## Tips

- Start with all lane lengths equal, then change one lane at a time.
- Short gate cycles against longer pitch cycles produce the clearest polymetric effect.
- Because the clip contains ordinary MIDI notes, you can still inspect and edit the result in Ableton's piano roll.
