Launchpad95 : Improved Novation Launchpad remote scripts with Instrument Mode, Scales, Step Sequencer and Device Controller.

These scripts are modified version of Ableton Live 9.0 scripts for Novation Launchpad and provide the same functionality but add support for editing the midi clips using a step sequencer and Device Controller. It also replaces User Mode one with an Instrument Mode mimicking Ableton Push Instrument Mode behaviour.

It does not require any external tool like Max for Live (M4L) in order to work. This script is just a plain Live Control Surface Python Script. 

Full manual for the new polymetric sequencer mode: [PolymetricSequencerMode.md](PolymetricSequencerMode.md)

## Polymetric Sequencer Mode

#### This fork adds a new `User 2` sub-mode: `polymetric stepseq`.

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

See [PolymetricSequencerMode.md](/z:/Code/DSP/LaunchpadAlchemy95/PolymetricSequencerMode.md) for the full manual.

