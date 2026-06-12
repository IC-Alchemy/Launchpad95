Original LaunchPad95 manual/ website https://motscousus.com/stuff/2011-07_Novation_Launchpad_Ableton_Live_Scripts/

#### This fork adds a new `User 2` sub-mode: `polymetric stepseq`, and a new `User 1` sub-mode: `looping clip`.

Both modes are fully working, but only tested on a Launchpad X on Windows.
For more detailed install instructions check the original website above.


## Simple Install Instructions
Download this repo as a zip, and unzip the folder to <img width="667" height="24" alt="image" src="https://github.com/user-attachments/assets/6e3eadcd-1f0e-4371-b874-640dec8913f2" />

You should have a folder Launchpad95PolyMetric along with all the other MIDI remote scripts. 
Then simply select Launchpad95PolyMetric under Control Surface, and choose LPX MIDI Port 2 for in and out if using LPX

Full manual for the new polymetric sequencer mode: [PolymetricSequencerMode.md](PolymetricSequencerMode.md)

## Polymetric Sequencer Mode

It is a clip-based melodic sequencer where five independent lanes can run at different cycle lengths:

- gate
- pitch
- octave
- velocity
- note length

The sequencer still writes normal MIDI notes into the selected Ableton Live clip, but each lane wraps independently, so the pattern evolves over time without needing multiple clips or a realtime generator.

Quick overview:

- Enter it by pressing `User 2` until `POLYMETRIC SEQUENCER MODE` appears.
- Tap lane buttons to edit gate, pitch, octave, velocity, or note length.
- Long-press a lane button to edit that lane's sequence length on the full 8x8 grid.
- Pitch can be switched between mono and poly with a double-tap on the pitch button.
- Quantization, scale edit, clip lock, and track lock all work like the melodic step sequencer.

Why it is useful:

- Create evolving sequences from a single MIDI clip.
- Keep rhythm and pitch cycles independent.
- Use ordinary MIDI clips that still open and edit normally in Live's piano roll.
- Save lane lengths directly in the clip name with a token like `[poly:g8,p7,o5,v8,l3]`.

See [PolymetricSequencerMode.md](PolymetricSequencerMode.md) for the full manual.

## Looping Clip Mode

A multi-track visual clip looper that uses the full 8x8 pad matrix. It works with both audio and MIDI clips and lets you jump the loop brace to equal slices across the selected scene's visible clips.

Quick overview:

- Enter it by pressing `User 1` three times (cycle through instrument → device → **looping clip**).
- Default view shows 4 tracks from the current scene, each taking 2 rows of the grid for 16 slices.
- Side button 1 toggles between **4-track** (16 slices per track) and **8-track** (8 slices per track) layouts.
- Hold any two pads on the same track at the same time to set the loop between them.
- Holding the first and last pad together restores the full clip span for that track.
- Tap and release a single pad inside the current loop to jump playback to that slice and play.
- Slice size is derived from the clip's marker range when the mode is entered.
- The component currently edits `loop_start` and `loop_end` only; it does not rewrite MIDI notes.

### Grid Layout

**4-track mode** (default):
```
Row 0-1 → Track 0  (16 pads: cols 0-7 × 2 rows)
Row 2-3 → Track 1
Row 4-5 → Track 2
Row 6-7 → Track 3
```

**8-track mode** (toggled with side button 1):
```
Row 0 → Track 0  (8 pads: cols 0-7)
Row 1 → Track 1
...
Row 7 → Track 7
```

### Pad Colors

| Color | Meaning |
|-------|---------|
| Off | Pad outside loop range |
| Dim blue | Pad inside loop range |
| Green | Loop start boundary |
| Red | Loop end boundary |
| Green pulse | Playhead position |
| Amber blink | Pending start selection (held) |
| Black | No clip on this track |

### Side Buttons

| Button | Function |
|--------|----------|
| 1 | Toggle 4-track / 8-track mode |
| 3 | Quantization placeholder (currently no action) |

### Scene And Track Following

The component follows Ableton Live's selected scene automatically.

There is internal support for a track offset, but no track-bank button binding is currently wired in the looping component.

### Audio & MIDI Support

Works with both audio and MIDI clips. The mode reads `loop_start`, `loop_end`, `start_marker`, and `end_marker`, and writes `loop_start` / `loop_end`. MIDI note data is left unchanged.

