Original LaunchPad95 manual/ website https://motscousus.com/stuff/2011-07_Novation_Launchpad_Ableton_Live_Scripts/

#### This fork just adds a new `User 2` sub-mode: `polymetric stepseq`.

The new sequencer mode is fully working, but only tested on a Launchpad X on Windows.
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

