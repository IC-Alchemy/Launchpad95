"""Clip-backed polymetric sequencer mode.

This editor keeps Ableton MIDI notes as the source of truth, then lets gate,
pitch, octave, velocity, and note length loop at different cycle lengths. For
a musician, that means one clip can behave like several phrases phasing against
each other instead of one fixed bar.

Comments in this file stay practical: each section explains its role, each
function says what it does, and most functions include a short cue about where
to change behavior if you want a different workflow.
"""

import re
import time

from _Framework.ButtonElement import ButtonElement

from .ScaleComponent import MUSICAL_MODES, KEY_NAMES
from .StepSequencerComponent import QUANTIZATION_NAMES
from .StepSequencerComponent2 import StepSequencerComponent2, MelodicNoteEditorComponent


try:
	xrange
except NameError:
	xrange = range


# Mode IDs select which musical lane the grid is editing.
# `POLY_MODE_LANE_LENGTH` is a utility page for changing how long each lane
# loops before it wraps back to step 1.
POLY_MODE_GATE = 0
POLY_MODE_LENGTH = 1
POLY_MODE_OCTAVE = 2
POLY_MODE_VELOCITY = 3
POLY_MODE_PITCH = 4
POLY_MODE_LANE_LENGTH = 20

# Lane names are reused in metadata, UI messages, and OSD text, so keeping
# them stable makes saved clips load predictably.
LANE_GATE = "gate"
LANE_LENGTH = "length"
LANE_OCTAVE = "octave"
LANE_VELOCITY = "velocity"
LANE_PITCH = "pitch"

# These lookups keep the code readable when switching between numeric mode IDs
# and musician-facing lane labels.
LANE_ORDER = [LANE_GATE, LANE_LENGTH, LANE_OCTAVE, LANE_VELOCITY, LANE_PITCH]
LANE_MODE = {
	LANE_GATE: POLY_MODE_GATE,
	LANE_LENGTH: POLY_MODE_LENGTH,
	LANE_OCTAVE: POLY_MODE_OCTAVE,
	LANE_VELOCITY: POLY_MODE_VELOCITY,
	LANE_PITCH: POLY_MODE_PITCH
}
MODE_LANE = dict((value, key) for key, value in LANE_MODE.items())

# Ableton notes already store pitch, start, velocity, and duration. The extra
# state this mode needs is each lane's cycle length, so it is packed into a
# clip-name token and restored when the clip is reopened.
METADATA_RE = re.compile(r"\s*\[poly:g(\d+),p(\d+),o(\d+),v(\d+),l(\d+)\]\s*")
MAX_POLY_STEPS = 128


class PolymetricNoteEditorComponent(MelodicNoteEditorComponent):
	"""Edit one clip as several independent looping lanes.

	Musically, this turns a plain step pattern into interlocking phrases that can
	drift against each other. Modify this class if you want new lanes, different
	grid behavior, or alternate note-writing rules.
	"""

	# Setup and lifecycle.

	def __init__(self, step_sequencer, matrix, side_buttons, control_surface):
		"""Set up editor state, defaults, and side-button behavior.

		Musically, the editor opens in pitch view so the first move is usually note
		selection. Modify this to change the startup lane, default lengths, or
		which hardware button controls gate mode.
		"""
		# MelodicNoteEditorComponent wires side button 3 as "random"; in this
		# mode that same inherited hook is repurposed as the gate page button.
		self._gate_button = None
		self._last_side_press_times = {}
		super(PolymetricNoteEditorComponent, self).__init__(step_sequencer, matrix, side_buttons, control_surface)
		self._mode = POLY_MODE_PITCH
		self._selected_length_lane = LANE_GATE
		self._set_default_lane_lengths()
		self.set_gate_button(self._side_buttons[3])

	def disconnect(self):
		"""Release the repurposed gate button before parent teardown.

		Modify this if you add more listeners or temporary state that must be
		cleaned up when the component is unloaded.
		"""
		self._gate_button = None
		super(PolymetricNoteEditorComponent, self).disconnect()

	def _init_data(self):
		"""Reset inherited note data plus the extra polymetric lane state.

		Musically, this clears the current phrase back to a neutral starting point.
		Modify this if you want fresh clips to inherit previous lane content or
		load custom defaults.
		"""
		super(PolymetricNoteEditorComponent, self)._init_data()
		self._notes_gates = [0] * MAX_POLY_STEPS
		self._set_default_lane_lengths()

	def _set_default_lane_lengths(self):
		"""Give every lane an initial cycle length before clip data is read.

		Musically, equal short defaults keep a new groove predictable before any
		polymeter is introduced. Modify this for instant odd-meter templates.
		"""
		self._lane_lengths = {
			LANE_GATE: 8,
			LANE_PITCH: 8,
			LANE_OCTAVE: 8,
			LANE_VELOCITY: 8,
			LANE_LENGTH: 8
		}

	def set_clip(self, clip):
		"""Bind a new clip and rebuild lane state from its stored content.

		Musically, this recalls the phrase exactly as the player last left it.
		Modify this if you want lane state to persist across clip changes.
		"""
		if self._clip != clip:
			self._init_data()
			self._clip = clip
			self._parse_metadata()

	def set_mode(self, mode):
		"""Switch the visible edit lane and track which lane length is editable.

		Musically, this decides whether the pads sculpt rhythm, melody, accents,
		or sustain. Modify this if mode changes should trigger extra behaviors.
		"""
		# Remember the lane whose length should be edited when entering length
		# edit. This keeps "long press current page" behavior deterministic.
		if mode != POLY_MODE_LANE_LENGTH:
			self._selected_length_lane = MODE_LANE.get(mode, self._selected_length_lane)
		self._mode = mode
		self._force_update = True
		self.update()

	def set_key_indexes(self, key_indexes):
		"""Update the scale degrees available on the grid and rewrite the clip.

		Musically, changing scale can reharmonize the phrase while the rhythm stays
		put. Modify this if you want to preserve out-of-scale notes instead.
		"""
		if self._key_indexes != key_indexes:
			self._key_indexes = key_indexes
			self._normalize_pitch_indexes()
			self._update_clip_notes()

	# Clip and note decoding.

	def _normalize_pitch_indexes(self):
		"""Ensure each step has at least one pitch slot selected.

		Musically, a gated step always has a playable note instead of an undefined
		placeholder. Modify this if you want to allow pitchless trigger lanes.
		"""
		for step in xrange(MAX_POLY_STEPS):
			has_pitch = False
			for note_index in xrange(7):
				if self._notes_pitches[step * 7 + note_index] == 1:
					has_pitch = True
			if not has_pitch:
				self._notes_pitches[step * 7] = 1

	def _default_length_from_clip(self):
		"""Use the clip loop length as the starting length for all lanes.

		Musically, a fresh lane begins by matching the clip's bar or phrase size.
		Modify this if defaults should come from a fixed value or song structure.
		"""
		if self._clip == None:
			return 8
		try:
			steps = int((self._clip.loop_end - self._clip.loop_start) / self._quantization)
		except (RuntimeError, ZeroDivisionError):
			steps = 8
		return max(1, min(MAX_POLY_STEPS, steps))

	def _parse_metadata(self):
		"""Load stored lane lengths from the clip-name token.

		Musically, this restores the exact phase relationship between looping
		lanes. Modify this if you want to save more settings than lane length.
		"""
		# If a clip has no metadata, all lanes initially cycle over the clip loop.
		# This mirrors the existing melodic sequencer until the user opts into
		# polymetric lengths.
		default_length = self._default_length_from_clip()
		for lane in LANE_ORDER:
			self._lane_lengths[lane] = default_length

		if self._clip == None:
			return
		name = self._clip.name or ""
		match = METADATA_RE.search(name)
		if match == None:
			return
		values = {
			LANE_GATE: int(match.group(1)),
			LANE_PITCH: int(match.group(2)),
			LANE_OCTAVE: int(match.group(3)),
			LANE_VELOCITY: int(match.group(4)),
			LANE_LENGTH: int(match.group(5))
		}
		for lane, value in values.items():
			self._lane_lengths[lane] = max(1, min(MAX_POLY_STEPS, value))

	def _write_metadata(self):
		"""Write lane lengths back into the clip-name token.

		Musically, this makes the groove recallable the next time the clip opens.
		Modify this if you want a different token format or optional metadata.
		"""
		if self._clip == None:
			return
		try:
			# Strip any old token before appending the current one; otherwise
			# repeated edits would steadily corrupt the user-visible clip name.
			name = self._clip.name or ""
			base_name = METADATA_RE.sub("", name).strip()
			token = "[poly:g%d,p%d,o%d,v%d,l%d]" % (
				self._lane_lengths[LANE_GATE],
				self._lane_lengths[LANE_PITCH],
				self._lane_lengths[LANE_OCTAVE],
				self._lane_lengths[LANE_VELOCITY],
				self._lane_lengths[LANE_LENGTH]
			)
			self._clip.name = ("%s %s" % (base_name, token)).strip()
		except RuntimeError:
			pass

	def _parse_notes(self):
		"""Translate cached Ableton MIDI notes into editable lane arrays.

		Musically, the first note at a step becomes the main voice, and later
		notes can become chord tones. Modify this if another note should define
		shared step values like velocity or length.
		"""
		# Existing clips use the first note at a step as the source for shared
		# velocity, octave, and length. In poly mode, additional notes at that
		# same step are kept as chord tones.
		for index in xrange(len(self._notes_pitches)):
			self._notes_pitches[index] = 0
		for index in xrange(MAX_POLY_STEPS):
			self._notes_gates[index] = 0
			self._notes_velocities[index] = 4
			self._notes_octaves[index] = 2
			self._notes_lengths[index] = 3

		first_note = [True] * MAX_POLY_STEPS
		for note in self._note_cache:
			note_position = note[1]
			note_key = note[0]
			note_length = note[2]
			note_velocity = note[3]
			note_muted = note[4]
			step = int(note_position / self._quantization)
			if note_muted or step < 0 or step >= MAX_POLY_STEPS:
				continue

			if first_note[step]:
				first_note[step] = False
				self._notes_gates[step] = 1

				for value_index in xrange(7):
					if note_velocity >= self._velocity_map[value_index]:
						self._notes_velocities[step] = value_index

				for value_index in xrange(7):
					if note_length * 4 >= self._length_map[value_index] * self._quantization:
						self._notes_lengths[step] = value_index

				self._store_pitch_for_note(step, note_key, None)
			elif not self._is_monophonic:
				self._store_pitch_for_note(step, note_key, self._notes_octaves[step])

		self._normalize_pitch_indexes()
		self._update_matrix()

	def _store_pitch_for_note(self, step, note_key, preferred_octave):
		"""Map a MIDI note number into scale-degree and octave slots.

		Musically, this is where raw pitches become the note choices shown on the
		grid. Modify this for wider note rows, alternate tunings, or absolute pitch
		storage.
		"""
		found = False
		for note_index in xrange(min(7, len(self._key_indexes))):
			octave_range = [preferred_octave] if preferred_octave != None else xrange(7)
			for octave in octave_range:
				if note_key == self._key_indexes[note_index] + 12 * (octave - 2) and not found:
					found = True
					self._notes_octaves[step] = octave
					self._notes_pitches[step * 7 + note_index] = 1
		if not found:
			self._notes_pitches[step * 7] = 1

	# Lane math and clip writing.

	def _lane_value_step(self, step, lane):
		"""Fold a timeline step into a lane's own cycle length.

		Musically, this is the phase engine that makes one lane loop against
		another. Modify this for offsets, ping-pong motion, or Euclidean playback.
		"""
		# Core polymetric rule: each lane reads from its own modulo cycle while
		# the clip timeline still advances on the normal quantized grid.
		return step % self._lane_lengths[lane]

	def _pitch_indexes_for_step(self, step):
		"""Collect every active pitch degree for a timeline step.

		Musically, this decides which chord tones fire on that pulse. Modify this
		if you want strums, note priority, or chord thinning.
		"""
		pitch_step = self._lane_value_step(step, LANE_PITCH)
		pitch_indexes = []
		for note_index in xrange(7):
			if self._notes_pitches[pitch_step * 7 + note_index] == 1:
				pitch_indexes.append(note_index)
		return pitch_indexes

	def _prune_polyphonic_pitches(self):
		"""Reduce each step to one selected pitch when mono mode is enabled.

		Musically, this collapses chords back into a single-note line. Modify this
		to keep the highest, lowest, or last-played pitch instead of the first.
		"""
		for step in xrange(MAX_POLY_STEPS):
			kept_pitch = False
			for note_index in xrange(7):
				index = step * 7 + note_index
				if self._notes_pitches[index] == 1:
					if kept_pitch:
						self._notes_pitches[index] = 0
					else:
						kept_pitch = True

	def _update_clip_notes(self):
		"""Render lane state back into ordinary Ableton MIDI notes.

		Musically, this is where rhythm, pitch, octave, dynamics, and duration meet
		to form the final groove on the clip timeline. Modify this to add swing,
		probability, accents, or overlap rules before notes are written.
		"""
		if self._clip != None and self._step_sequencer.is_enabled():
			note_cache = []
			try:
				start = int(self._clip.loop_start / self._quantization)
				end = int(self._clip.loop_end / self._quantization)
			except (RuntimeError, ZeroDivisionError):
				start = 0
				end = MAX_POLY_STEPS
			start = max(0, min(MAX_POLY_STEPS, start))
			end = max(start, min(MAX_POLY_STEPS, end))

			for step in xrange(start, end):
				gate_step = self._lane_value_step(step, LANE_GATE)
				if self._notes_gates[gate_step] != 1:
					continue

				# Resolve every emitted MIDI note from the lane's independent
				# play position, then write the final result back as ordinary
				# Ableton MIDI notes.
				octave_step = self._lane_value_step(step, LANE_OCTAVE)
				velocity_step = self._lane_value_step(step, LANE_VELOCITY)
				length_step = self._lane_value_step(step, LANE_LENGTH)
				pitch_indexes = self._pitch_indexes_for_step(step)

				time_value = step * self._quantization
				velocity = self._velocity_map[self._notes_velocities[velocity_step]]
				length = self._length_map[self._notes_lengths[length_step]] * self._quantization / 4.0
				for pitch_index in pitch_indexes:
					pitch = self._key_indexes[pitch_index] + 12 * (self._notes_octaves[octave_step] - 2)
					if pitch >= 0 and pitch < 128 and velocity >= 0 and velocity < 128 and length >= 0:
						note_cache.append([pitch, time_value, length, velocity, False])

			self._write_metadata()
			self._clip.select_all_notes()
			self._clip.replace_selected_notes(tuple(note_cache))

	def _active_lane(self):
		"""Return the lane currently being edited.

		Modify this if the length editor should follow another selection rule.
		"""
		return MODE_LANE.get(self._mode, self._selected_length_lane)

	def _active_lane_length(self):
		"""Return the cycle length of the selected length-edit lane.

		Modify this if lane length becomes dynamic or comes from another source.
		"""
		return self._lane_lengths[self._selected_length_lane]

	def _playhead_step_for_lane(self, lane):
		"""Map the transport playhead into one lane's loop position.

		Musically, the bottom-row marker shows where that lane is in its own
		cycle. Modify this if you want page-relative or phase-shifted playheads.
		"""
		if self._playhead == None:
			return None
		# The visual playhead follows the active lane's cycle, not only the clip
		# page. This is the main realtime feedback for polymeter.
		return int(self._playhead / self.quantization) % self._lane_lengths[lane]

	# Grid rendering.

	def _update_matrix(self):
		"""Redraw the pad grid from the current mode and clip state.

		Musically, the matrix becomes either a step page or a lane-length ruler.
		Modify this to add overlays, alternate colors, or more visual cues.
		"""
		if self.is_enabled() and self._matrix != None:
			for x in xrange(8):
				for y in xrange(8):
					self._grid_back_buffer[x][y] = 0

			if self._clip != None:
				if self._mode == POLY_MODE_LANE_LENGTH:
					self._render_lane_length()
				else:
					self._render_parameter_page()
			else:
				for x in xrange(8):
					for y in xrange(8):
						self._grid_back_buffer[x][y] = "DefaultButton.Disabled"

			for x in xrange(8):
				for y in xrange(8):
					if self._grid_back_buffer[x][y] != self._grid_buffer[x][y] or self._force_update:
						self._grid_buffer[x][y] = self._grid_back_buffer[x][y]
						self._matrix.get_button(x, y).set_light(self._grid_buffer[x][y])

			self._force_update = False

	def _render_parameter_page(self):
		"""Paint one 8-step page for the active musical lane.

		Musically, repeated columns reveal when a shorter lane is cycling under a
		longer phrase. Modify this to show extra state like accents or probability.
		"""
		lane = self._active_lane()
		playhead_step = self._playhead_step_for_lane(lane)
		for x in xrange(8):
			step = x + 8 * self._page
			gate_on = self._notes_gates[self._lane_value_step(step, LANE_GATE)] == 1
			has_note = gate_on
			# Render the page by projecting timeline columns through lane modulo
			# addressing. Repeated values are intentional when a lane is shorter
			# than the visible clip page.
			for y in xrange(7):
				if self._mode == POLY_MODE_PITCH:
					value_step = self._lane_value_step(step, LANE_PITCH)
					color = "PolymetricSequencer.NoteOn" if self._notes_pitches[value_step * 7 + 6 - y] == 1 else "PolymetricSequencer.NoteOff"
				elif self._mode == POLY_MODE_OCTAVE:
					value_step = self._lane_value_step(step, LANE_OCTAVE)
					color = self._value_color(self._notes_octaves[value_step] == 6 - y, has_note)
				elif self._mode == POLY_MODE_VELOCITY:
					value_step = self._lane_value_step(step, LANE_VELOCITY)
					color = self._value_color(self._notes_velocities[value_step] >= 6 - y, has_note)
				elif self._mode == POLY_MODE_LENGTH:
					value_step = self._lane_value_step(step, LANE_LENGTH)
					color = self._value_color(self._notes_lengths[value_step] >= 6 - y, has_note)
				else:
					value_step = self._lane_value_step(step, LANE_GATE)
					if self._notes_gates[value_step] == 1 and y == 3:
						color = "PolymetricSequencer.NoteOn"
					elif self._notes_gates[value_step] == 1:
						color = "PolymetricSequencer.NoteDim"
					else:
						color = "PolymetricSequencer.NoteOff"
				self._grid_back_buffer[x][y] = color

			if playhead_step != None and playhead_step == (step % self._lane_lengths[lane]):
				self._grid_back_buffer[x][7] = "PolymetricSequencer.Playhead1"
			else:
				self._grid_back_buffer[x][7] = "PolymetricSequencer.PageMarker"

	def _value_color(self, enabled, has_note):
		"""Choose the LED color for value-style lanes.

		Modify this if you want different dim states or lane-specific colors.
		"""
		if enabled:
			if has_note:
				return "PolymetricSequencer.FaderOn"
			return "PolymetricSequencer.FaderDim"
		return "PolymetricSequencer.FaderOff"

	def _render_lane_length(self):
		"""Use the full grid as a picker for one lane's cycle length.

		Musically, this makes odd phrase lengths like 5, 7, or 13 steps quick to
		set. Modify this if you want bar markers or another length layout.
		"""
		selected_length = self._active_lane_length()
		base_step = self._page * 64
		# Length edit uses the full 8x8 grid so users can set long cycles without
		# stepping through sixteen separate clip pages.
		for y in xrange(8):
			for x in xrange(8):
				step = base_step + y * 8 + x
				if step >= MAX_POLY_STEPS:
					self._grid_back_buffer[x][y] = "PolymetricSequencer.Blank"
				elif step == selected_length - 1:
					self._grid_back_buffer[x][y] = "PolymetricSequencer.LengthSelected"
				elif step < selected_length:
					self._grid_back_buffer[x][y] = "PolymetricSequencer.LengthOn"
				else:
					self._grid_back_buffer[x][y] = "PolymetricSequencer.LengthOff"

	def _length_step_from_grid(self, x, y):
		"""Convert an x/y pad press into a lane-length step number.

		Modify this if you want column-first or serpentine length ordering.
		"""
		return self._page * 64 + y * 8 + x

	def _parameter_step_from_grid(self, x):
		"""Convert a column press into the visible timeline step.

		Modify this if you want zoomed pages or a different grid-to-step mapping.
		"""
		return x + 8 * self._page

	# Grid input.

	def _matrix_value(self, value, x, y, is_momentary):
		"""Handle pad presses for parameter editing and lane-length editing.

		Musically, this is the main path from fingers on pads to changes in the
		pattern. Modify this to add audition, latching, or shifted gestures.
		"""
		if self.is_enabled() and self._matrix != None:
			if self._clip == None:
				self._step_sequencer.create_clip()
			elif ((value != 0) or (not is_momentary)):
				# Normal parameter pages use columns as clip steps; length edit
				# uses the whole matrix as a length picker.
				step = self._length_step_from_grid(x, y) if self._mode == POLY_MODE_LANE_LENGTH else self._parameter_step_from_grid(x)
				if step < 0 or step >= MAX_POLY_STEPS:
					return
				if self._mode == POLY_MODE_LANE_LENGTH:
					self._lane_lengths[self._selected_length_lane] = step + 1
					self._write_metadata()
				elif y < 7:
					self._handle_parameter_press(step, y)
				self._force_update = True
				self._update_matrix()
				self._update_clip_notes()

	def _handle_parameter_press(self, step, y):
		"""Apply one pad press to the currently selected parameter lane.

		Musically, this is where a tap becomes a note, accent, octave jump, or
		gate change. Modify this for ratchets, fills, or alternate mono rules.
		"""
		if self._mode == POLY_MODE_PITCH:
			value_step = self._lane_value_step(step, LANE_PITCH)
			pitch_index = value_step * 7 + 6 - y
			if self._is_monophonic:
				selected = self._notes_pitches[pitch_index] == 1
				for yy in xrange(7):
					self._notes_pitches[value_step * 7 + yy] = 0
				if not selected:
					self._notes_pitches[pitch_index] = 1
					# Choosing a pitch should create an audible event, matching
					# the melodic sequencer's "tap a note to make a step" feel.
					self._notes_gates[self._lane_value_step(step, LANE_GATE)] = 1
			else:
				self._notes_pitches[pitch_index] = 0 if self._notes_pitches[pitch_index] == 1 else 1
				if self._notes_pitches[pitch_index] == 1:
					self._notes_gates[self._lane_value_step(step, LANE_GATE)] = 1
		elif self._mode == POLY_MODE_OCTAVE:
			self._notes_octaves[self._lane_value_step(step, LANE_OCTAVE)] = 6 - y
		elif self._mode == POLY_MODE_VELOCITY:
			self._notes_velocities[self._lane_value_step(step, LANE_VELOCITY)] = 6 - y
		elif self._mode == POLY_MODE_LENGTH:
			self._notes_lengths[self._lane_value_step(step, LANE_LENGTH)] = 6 - y
		elif self._mode == POLY_MODE_GATE:
			value_step = self._lane_value_step(step, LANE_GATE)
			self._notes_gates[value_step] = 0 if self._notes_gates[value_step] == 1 else 1

	# Side-button handling.

	def _button_released_as_length_edit(self, sender, lane):
		"""Treat a long lane-button hold as a request to edit lane length.

		Musically, holding the lane button is the shortcut into phrase-length
		shaping. Modify this if you want a different hold time or secondary action.
		"""
		press_time = self._last_side_press_times.pop(sender, None)
		if press_time == None:
			return False
		if time.time() - press_time > 0.5:
			# Long-pressing any lane button edits that lane's cycle length.
			self._selected_length_lane = lane
			self.set_mode(POLY_MODE_LANE_LENGTH)
			self._control_surface.show_message("%s length" % lane)
			self._step_sequencer._update_OSD()
			return True
		return False

	def _update_random_button(self):
		"""Reuse the inherited random-button slot as the gate button refresh path.

		Modify this if you add a separate hardware button for randomization again.
		"""
		self._update_gate_button()

	def set_random_button(self, button):
		"""Keep the parent setup path intact while rebinding it to gate mode.

		Modify this if random and gate should become separate controls.
		"""
		# Parent constructor calls this while setting up the melodic editor.
		# Keep the inherited call path valid, but bind it to gate instead.
		self.set_gate_button(button)

	def set_gate_button(self, button):
		"""Register or unregister the dedicated gate button listener.

		Modify this if gate mode needs extra LED behavior or other listeners.
		"""
		assert isinstance(button, (ButtonElement, type(None)))
		current_button = getattr(self, "_gate_button", None)
		if current_button != button:
			if current_button != None:
				current_button.remove_value_listener(self._gate_button_value)
			self._gate_button = button
			if self._gate_button != None:
				self._gate_button.add_value_listener(self._gate_button_value, identify_sender=True)

	def _update_gate_button(self):
		"""Refresh the gate button LED to match the current editor state.

		Modify this if you want alternate colors or blink feedback during playback.
		"""
		if self.is_enabled() and self._gate_button != None:
			if self._clip != None:
				if self._mode == POLY_MODE_LANE_LENGTH and self._selected_length_lane == LANE_GATE:
					self._gate_button.set_light("PolymetricSequencer.SideLength")
				else:
					self._gate_button.set_on_off_values("PolymetricSequencer.SideOn", "PolymetricSequencer.SideOff")
					if self._mode == POLY_MODE_GATE:
						self._gate_button.turn_on()
					else:
						self._gate_button.turn_off()
			else:
				self._gate_button.set_light("DefaultButton.Disabled")

	def _gate_button_value(self, value, sender):
		"""Handle gate-button taps and holds.

		Musically, a short tap edits on/off rhythm, while a hold edits the gate
		lane's loop length. Modify this if tap and hold should do other actions.
		"""
		if self.is_enabled() and self._clip != None:
			if value != 0 or not sender.is_momentary():
				self._last_side_press_times[sender] = time.time()
			else:
				if not self._button_released_as_length_edit(sender, LANE_GATE):
					self.set_mode(POLY_MODE_GATE)
					self._control_surface.show_message("gate")
					self._step_sequencer._update_OSD()

	def _update_mode_notes_pitches_button(self):
		"""Refresh the pitch lane button LED.

		Modify this if pitch mode needs different colors or animation.
		"""
		self._update_lane_button(self._mode_notes_pitches_button, POLY_MODE_PITCH, LANE_PITCH, "StepSequencer2.Pitch.On", "StepSequencer2.Pitch.Dim")

	def _update_mode_notes_octaves_button(self):
		"""Refresh the octave lane button LED.

		Modify this if octave mode needs different colors or animation.
		"""
		self._update_lane_button(self._mode_notes_octaves_button, POLY_MODE_OCTAVE, LANE_OCTAVE, "StepSequencer2.Octave.On", "StepSequencer2.Octave.Dim")

	def _update_mode_notes_velocities_button(self):
		"""Refresh the velocity lane button LED.

		Musically, this is the accent lane indicator. Modify this if dynamic
		ranges should use their own colors.
		"""
		self._update_lane_button(self._mode_notes_velocities_button, POLY_MODE_VELOCITY, LANE_VELOCITY, "StepSequencer2.Velocity.On", "StepSequencer2.Velocity.Dim")

	def _update_mode_notes_lengths_button(self):
		"""Refresh the note-length lane button LED.

		Modify this if long sustains or ties should get distinct colors.
		"""
		self._update_lane_button(self._mode_notes_lengths_button, POLY_MODE_LENGTH, LANE_LENGTH, "StepSequencer2.Length.On", "StepSequencer2.Length.Dim")

	def _update_lane_button(self, button, mode, lane, on_color, off_color):
		"""Apply shared LED rules for side buttons that select lanes.

		Modify this to centralize new button themes or blink logic.
		"""
		if self.is_enabled() and button != None:
			if self._clip != None:
				if self._mode == POLY_MODE_LANE_LENGTH and self._selected_length_lane == lane:
					button.set_light("PolymetricSequencer.SideLength")
				else:
					button.set_on_off_values(on_color, off_color)
					if self._mode == mode:
						button.turn_on()
					else:
						button.turn_off()
			else:
				button.set_light("DefaultButton.Disabled")

	def _mode_button_notes_pitches_value(self, value, sender):
		"""Handle pitch-button taps, holds, and double-tap mono/poly toggling.

		Musically, this one control switches between melody editing and chord
		editing. Modify this if mono/poly should use another gesture.
		"""
		if self.is_enabled() and self._clip != None:
			if value != 0 or not sender.is_momentary():
				self._last_side_press_times[sender] = time.time()
			else:
				if self._button_released_as_length_edit(sender, LANE_PITCH):
					return
				if time.time() - self._last_notes_pitches_button_press < 0.5:
					self._is_monophonic = not self._is_monophonic
					if self._is_monophonic:
						self._prune_polyphonic_pitches()
					self._update_clip_notes()
					self._control_surface.show_message("mono" if self._is_monophonic else "poly")
				else:
					self.set_mode(POLY_MODE_PITCH)
					self._control_surface.show_message("pitch")
				self._last_notes_pitches_button_press = time.time()
				self._step_sequencer._update_OSD()

	def _mode_button_notes_octaves_value(self, value, sender):
		"""Handle octave-button presses through the shared lane-button path.

		Modify this if octave mode should get custom shortcuts.
		"""
		self._lane_button_value(value, sender, LANE_OCTAVE, POLY_MODE_OCTAVE, "octave")

	def _mode_button_notes_velocities_value(self, value, sender):
		"""Handle velocity-button presses through the shared lane-button path.

		Musically, this selects the accent lane. Modify this if you want fixed
		accent presets or alternate velocity gestures.
		"""
		self._lane_button_value(value, sender, LANE_VELOCITY, POLY_MODE_VELOCITY, "velocity")

	def _mode_button_notes_lengths_value(self, value, sender):
		"""Handle length-button presses through the shared lane-button path.

		Musically, this selects sustain editing. Modify this if tie or legato
		actions should live on the same button.
		"""
		self._lane_button_value(value, sender, LANE_LENGTH, POLY_MODE_LENGTH, "length")

	def _lane_button_value(self, value, sender, lane, mode, message):
		"""Handle shared short-tap mode changes and long-press length editing.

		Modify this if each lane needs a different hold threshold or second action.
		"""
		if self.is_enabled() and self._clip != None:
			if value != 0 or not sender.is_momentary():
				self._last_side_press_times[sender] = time.time()
			else:
				if not self._button_released_as_length_edit(sender, lane):
					self.set_mode(mode)
					self._control_surface.show_message(message)
					self._step_sequencer._update_OSD()


class PolymetricSequencerComponent(StepSequencerComponent2):
	"""Top-level sequencer wrapper that installs the polymetric editor.

	Musically, the outer workflow still feels like the regular step sequencer:
	clip follow, scale, quantization, and navigation stay familiar while the note
	editor adds interlocking lane cycles. Modify this class for mode-wide UI or
	OSD changes.
	"""

	def __init__(self, matrix, side_buttons, top_buttons, control_surface):
		"""Name the component and inherit the normal sequencer setup.

		Modify this if you want extra mode-wide state or a different visible name.
		"""
		super(PolymetricSequencerComponent, self).__init__(matrix, side_buttons, top_buttons, control_surface)
		self._name = "polymetric step sequencer"

	def _set_note_editor(self):
		"""Install the polymetric note editor while keeping StepSequencer2 around it.

		Modify this if you want to swap in another editor variant entirely.
		"""
		# Everything outside the editor remains StepSequencer2 behavior: clip
		# following, lock modes, quantization, scale, loop navigation, and OSD.
		self._note_editor = self.register_component(PolymetricNoteEditorComponent(self, self._matrix, self._side_buttons, self._control_surface))

	def _update_OSD(self):
		"""Refresh the on-screen display with musical and transport context.

		Musically, this is the quick status line for scale, timing, lane focus,
		phrase lengths, and mono/poly state. Modify this if you want more live
		performance readouts on screen.
		"""
		if self._osd != None:
			self._osd.set_mode("Polymetric Step Sequencer")
			if self._clip != None:
				self._osd.attributes[0] = MUSICAL_MODES[self._scale_selector._modus * 2]
				self._osd.attribute_names[0] = "Scale"
				self._osd.attributes[1] = KEY_NAMES[self._scale_selector._key % 12]
				self._osd.attribute_names[1] = "Root Note"
				self._osd.attributes[2] = self._scale_selector._octave
				self._osd.attribute_names[2] = "Octave"
				self._osd.attributes[3] = QUANTIZATION_NAMES[self._quantization_index]
				self._osd.attribute_names[3] = "Quantisation"
				active_lane = self._note_editor._active_lane()
				if self._note_editor._mode == POLY_MODE_LANE_LENGTH:
					self._osd.attributes[4] = "%s %d" % (self._note_editor._selected_length_lane, self._note_editor._active_lane_length())
					self._osd.attribute_names[4] = "Seq Length"
				else:
					self._osd.attributes[4] = active_lane
					self._osd.attribute_names[4] = "Parameter"
				self._osd.attributes[5] = "%d/%d/%d/%d/%d" % (
					self._note_editor._lane_lengths[LANE_GATE],
					self._note_editor._lane_lengths[LANE_PITCH],
					self._note_editor._lane_lengths[LANE_OCTAVE],
					self._note_editor._lane_lengths[LANE_VELOCITY],
					self._note_editor._lane_lengths[LANE_LENGTH]
				)
				self._osd.attribute_names[5] = "G/P/O/V/L"
				self._osd.attributes[6] = "Mono" if self._note_editor._is_monophonic else "Poly"
				self._osd.attribute_names[6] = "Polyphony"
				self._osd.attributes[7] = " "
				self._osd.attribute_names[7] = " "
			else:
				for index in xrange(8):
					self._osd.attributes[index] = " "
					self._osd.attribute_names[index] = " "

			if self._selected_track != None:
				if self._lock_to_track and self._is_locked:
					self._osd.info[0] = "track : " + self._selected_track.name + " (locked)"
				else:
					self._osd.info[0] = "track : " + self._selected_track.name
			else:
				self._osd.info[0] = " "
			if self._clip != None:
				name = self._clip.name
				if name == "":
					name = "(unamed clip)"
				if not self._lock_to_track and self._is_locked:
					self._osd.info[1] = "clip : " + name + " (locked)"
				else:
					self._osd.info[1] = "clip : " + name
			else:
				self._osd.info[1] = "no clip selected"
			self._osd.update()
