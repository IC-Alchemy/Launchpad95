import time
import Live

from _Framework.ButtonElement import ButtonElement
from _Framework.ButtonMatrixElement import ButtonMatrixElement
from _Framework.CompoundComponent import CompoundComponent


try:
    xrange
except NameError:
    # Ableton's older Python runtime used xrange; this keeps the file happy
    # in both the legacy environment and normal Python.
    xrange = range


DOUBLE_PRESS_WINDOW = 0.25


class TrackLoopState:
    # One small state bundle per visible track. Keeping this in one object
    # makes it easier to think of each track as its own "lane" on the grid.

    def __init__(self):
        self.track = None
        self.clip = None
        self.clip_slot = None
        self.loop_start = 0.0
        self.loop_end = 0.0
        self.clip_start = 0.0
        self.clip_end = 0.0
        self.playhead = None
        self.pending_start_step = None
        self.pending_end_step = None
        self.last_pad_time = 0.0
        self.last_pad_index = -1


class LoopingClipModeComponent(CompoundComponent):

    def __init__(self, matrix, side_buttons, top_buttons, control_surface):
        super(LoopingClipModeComponent, self).__init__()
        self._control_surface = control_surface
        self._osd = None
        self._name = "looping clip mode"

        self._matrix = matrix
        self._side_buttons = side_buttons
        self._top_buttons = top_buttons

        self._is_4_track_mode = True
        self._track_offset = 0
        self._selected_scene_index = 0
        self._quantization_step_size = 16

        # We keep eight state objects around even in 4-track mode. In that mode,
        # each track simply gets more vertical space on the 8x8 grid.
        self._track_states = [TrackLoopState() for _ in xrange(8)]

        self._grid_buffer = [[0] * 8 for _ in xrange(8)]
        self._grid_back_buffer = [[0] * 8 for _ in xrange(8)]
        self._force_update = True

        self._button_listeners = [
            (self._side_buttons[0], self._track_count_button_value),
            (self._side_buttons[1], self._bank_left_button_value),
            (self._side_buttons[2], self._bank_right_button_value),
            (self._side_buttons[3], self._reserved_button_value),
            (self._side_buttons[4], self._stop_button_value),
            (self._side_buttons[5], self._mute_button_value),
            (self._side_buttons[6], self._solo_button_value),
            (self._side_buttons[7], self._arm_button_value),
            (self._top_buttons[0], self._scene_up_button_value),
            (self._top_buttons[1], self._scene_down_button_value),
            (self._top_buttons[2], self._top_bank_left_button_value),
            (self._top_buttons[3], self._top_bank_right_button_value)
        ]
        for button, callback in self._button_listeners:
            if button is not None:
                button.add_value_listener(callback, identify_sender=True)

        if self._matrix is not None:
            self._matrix.add_value_listener(self._matrix_value)

        self.set_enabled(False)

    def disconnect(self):
        for button, callback in self._button_listeners:
            if button is not None:
                button.remove_value_listener(callback)
        self._button_listeners = []
        self._side_buttons = None
        self._top_buttons = None
        if self._matrix is not None:
            self._matrix.remove_value_listener(self._matrix_value)
        self._matrix = None
        self._osd = None
        for state in self._track_states:
            self._remove_clip_listeners(state)
            self._reset_state(state)
        super(LoopingClipModeComponent, self).disconnect()

    def set_osd(self, osd):
        self._osd = osd

    def set_enabled(self, enabled):
        if enabled:
            self._selected_scene_index = self._current_scene_index()
            self._clamp_track_offset()
            self._force_update = True
            self._refresh_track_states()
            self._update_OSD()
        else:
            self._clear_pending_steps()
            for state in self._track_states:
                self._remove_clip_listeners(state)
                self._reset_state(state)
            self._clear_grid()
        CompoundComponent.set_enabled(self, enabled)

    def _track_count_for_mode(self):
        # 4-track mode gives each track two rows (16 pads). 8-track mode gives
        # each track one row (8 pads).
        return 4 if self._is_4_track_mode else 8

    def _pads_per_track(self):
        return 16 if self._is_4_track_mode else 8

    def _rows_per_track(self):
        return 2 if self._is_4_track_mode else 1

    def _current_scene_index(self):
        try:
            return list(self.song().scenes).index(self.song().view.selected_scene)
        except (RuntimeError, ValueError):
            return self._selected_scene_index

    def _clamp_track_offset(self):
        visible = self._track_count_for_mode()
        max_offset = max(0, len(list(self.song().tracks)) - visible)
        if self._track_offset > max_offset:
            self._track_offset = max_offset

    def _step_to_grid(self, step, track_index):
        cols = 8
        rows = self._rows_per_track()
        base_row = track_index * rows
        col = step % cols
        sub_row = step // cols
        # In 4-track mode, steps 0-7 are the first row and 8-15 are the second.
        return col, base_row + sub_row

    def _grid_to_step(self, x, y):
        rows = self._rows_per_track()
        track_index = y // rows
        if track_index >= self._track_count_for_mode():
            return None, None
        sub_row = y % rows
        # Translate a pad press back into a musical slice of the clip.
        step = sub_row * 8 + x
        if step >= self._pads_per_track():
            return None, None
        return track_index, step

    def _reset_state(self, state):
        state.track = None
        state.clip = None
        state.clip_slot = None
        state.loop_start = 0.0
        state.loop_end = 0.0
        state.clip_start = 0.0
        state.clip_end = 0.0
        state.playhead = None
        state.pending_start_step = None
        state.pending_end_step = None

    def _refresh_track_states(self):
        self._selected_scene_index = self._current_scene_index()
        self._clamp_track_offset()
        song = self.song()
        tracks = list(song.tracks)
        scene_index = self._selected_scene_index
        visible_tracks = self._track_count_for_mode()

        for i in xrange(len(self._track_states)):
            state = self._track_states[i]
            if i >= visible_tracks:
                self._remove_clip_listeners(state)
                self._reset_state(state)
                continue

            track_idx = self._track_offset + i
            if track_idx >= len(tracks):
                self._remove_clip_listeners(state)
                self._reset_state(state)
                continue

            track = tracks[track_idx]
            clip_slot = None
            clip = None

            try:
                clip_slots = list(track.clip_slots)
                if scene_index < len(clip_slots):
                    clip_slot = clip_slots[scene_index]
                    if clip_slot is not None and clip_slot.has_clip:
                        clip = clip_slot.clip
            except (RuntimeError, IndexError):
                clip_slot = None
                clip = None

            state.track = track
            if clip_slot != state.clip_slot or clip != state.clip:
                self._remove_clip_listeners(state)
                state.clip_slot = clip_slot
                state.clip = clip
                state.playhead = None
                if state.clip is not None:
                    self._add_clip_listeners(state)
                    self._read_clip_loop(state)
                else:
                    state.loop_start = 0.0
                    state.loop_end = 0.0
                    state.clip_start = 0.0
                    state.clip_end = 0.0
            elif state.clip is not None:
                self._read_clip_loop(state)

    def _read_clip_loop(self, state):
        if state.clip is not None:
            try:
                state.loop_start = state.clip.loop_start
                state.loop_end = state.clip.loop_end
                state.clip_start = state.clip.start_marker
                state.clip_end = state.clip.end_marker
                if state.clip.is_playing and self.song().is_playing:
                    state.playhead = state.clip.playing_position
                else:
                    state.playhead = None
            except RuntimeError:
                state.loop_start = 0.0
                state.loop_end = 0.0
                state.clip_start = 0.0
                state.clip_end = 0.0
                state.playhead = None

    def _clip_quant(self, state):
        clip_length = state.clip_end - state.clip_start
        if clip_length > 0:
            # The marker range is the visual timeline; each lane slices that
            # range into 16 or 8 equal regions, depending on the layout mode.
            return clip_length / float(self._quantization_step_size)
        # Safe fallback if Live gives us a strange clip range.
        return 0.25

    def _step_to_beat(self, state, step):
        # Convert a grid step into an absolute beat position inside the clip.
        return state.clip_start + step * self._clip_quant(state)

    def _beat_to_step(self, state, beat):
        quant = self._clip_quant(state)
        if quant <= 0:
            return 0
        # Tiny offset avoids rounding down when floating-point math lands just
        # below the next integer boundary.
        return int((beat - state.clip_start) / quant + 0.0001)

    def _add_clip_listeners(self, state):
        if state.clip is not None:
            try:
                # These listeners let the pad view follow Live in real time:
                # loop brace changes, playback movement, and play/stop state.
                if not state.clip.loop_start_has_listener(self._on_loop_changed):
                    state.clip.add_loop_start_listener(self._on_loop_changed)
                if not state.clip.loop_end_has_listener(self._on_loop_changed):
                    state.clip.add_loop_end_listener(self._on_loop_changed)
                if not state.clip.playing_position_has_listener(self._on_playing_position_changed):
                    state.clip.add_playing_position_listener(self._on_playing_position_changed)
                if not state.clip.playing_status_has_listener(self._on_playing_status_changed):
                    state.clip.add_playing_status_listener(self._on_playing_status_changed)
            except RuntimeError:
                pass

    def _remove_clip_listeners(self, state):
        if state.clip is not None:
            try:
                if state.clip.loop_start_has_listener(self._on_loop_changed):
                    state.clip.remove_loop_start_listener(self._on_loop_changed)
                if state.clip.loop_end_has_listener(self._on_loop_changed):
                    state.clip.remove_loop_end_listener(self._on_loop_changed)
                if state.clip.playing_position_has_listener(self._on_playing_position_changed):
                    state.clip.remove_playing_position_listener(self._on_playing_position_changed)
                if state.clip.playing_status_has_listener(self._on_playing_status_changed):
                    state.clip.remove_playing_status_listener(self._on_playing_status_changed)
            except RuntimeError:
                pass

    def _on_loop_changed(self):
        if self.is_enabled():
            for state in self._track_states:
                self._read_clip_loop(state)
            self._force_update = True
            self.update()

    def _on_playing_position_changed(self):
        if self.is_enabled():
            for state in self._track_states:
                self._read_clip_loop(state)
            self._force_update = True
            self.update()

    def _on_playing_status_changed(self):
        self._on_playing_position_changed()

    def _clear_pending_steps(self):
        for state in self._track_states:
            state.pending_start_step = None
            state.pending_end_step = None

    def _select_track_for_state(self, state):
        if state is None or state.track is None:
            return
        try:
            if self.song().view.selected_track != state.track:
                self.song().view.selected_track = state.track
        except RuntimeError:
            pass

    def _focused_state(self):
        try:
            selected_track = self.song().view.selected_track
        except RuntimeError:
            selected_track = None

        for i in xrange(self._track_count_for_mode()):
            state = self._track_states[i]
            if state.track == selected_track:
                return state

        for i in xrange(self._track_count_for_mode()):
            state = self._track_states[i]
            if state.track is not None:
                return state

        return None

    def _apply_midi_note_bounds(self, state, beat_start, beat_end):
        if state.clip is None:
            return
        try:
            if not state.clip.is_midi_clip:
                return
            state.clip.select_all_notes()
            note_cache = state.clip.get_selected_notes()
            new_notes = []
            for note in note_cache:
                note_start = note[1]
                note_duration = note[2]
                if note_start < beat_start or note_start >= beat_end:
                    continue
                max_duration = beat_end - note_start
                if max_duration <= 0:
                    continue
                trimmed_duration = min(note_duration, max_duration)
                new_notes.append([note[0], note_start, trimmed_duration, note[3], note[4]])
            state.clip.replace_selected_notes(tuple(new_notes))
            state.clip.deselect_all_notes()
        except RuntimeError:
            pass

    def _set_clip_loop_range(self, state, start_step, end_step):
        if state.clip is None:
            return

        pads = self._pads_per_track()
        start_step = max(0, min(start_step, pads - 1))
        end_step = max(start_step + 1, min(end_step, pads))

        beat_start = self._step_to_beat(state, start_step)
        if end_step >= pads:
            # The last pad should feel like "play to the end of the clip",
            # not "stop at a synthetic subdivision."
            beat_end = state.clip_end
        else:
            beat_end = self._step_to_beat(state, end_step)

        if beat_end <= beat_start:
            return

        try:
            # Live can be picky about loop_start staying before loop_end, so
            # when we move the start past the current end we update end first.
            if beat_start >= state.clip.loop_end:
                state.clip.loop_end = beat_end
                state.clip.loop_start = beat_start
            else:
                state.clip.loop_start = beat_start
                state.clip.loop_end = beat_end

            # Keep the clip markers aligned with the selected range so audio
            # and MIDI clips both tighten to the same visible subsection.
            if beat_start >= state.clip.end_marker:
                state.clip.end_marker = beat_end
                state.clip.start_marker = beat_start
            else:
                state.clip.start_marker = beat_start
                state.clip.end_marker = beat_end

            self._apply_midi_note_bounds(state, beat_start, beat_end)
            self._read_clip_loop(state)
        except RuntimeError:
            pass

    def _matrix_value(self, value, x, y, is_momentary):
        if not self.is_enabled() or self._matrix is None or (value == 0 and is_momentary):
            return

        track_index, step = self._grid_to_step(x, y)
        if track_index is None:
            return

        state = self._track_states[track_index]
        if state.track is None:
            return

        if state.clip is None:
            return

        self._select_track_for_state(state)

        now = time.time()
        if state.pending_start_step is None:
            self._clear_pending_steps()
            state.pending_start_step = step
            state.last_pad_time = now
            state.last_pad_index = step
            self._force_update = True
            self.update()
            return

        if state.pending_start_step == step:
            if state.last_pad_index == step and (now - state.last_pad_time) <= DOUBLE_PRESS_WINDOW:
                self._set_clip_loop_range(state, step, step + 1)
                self._clear_pending_steps()
            else:
                state.last_pad_time = now
                state.last_pad_index = step
            self._force_update = True
            self.update()
            return

        start = min(state.pending_start_step, step)
        end = max(state.pending_start_step, step) + 1
        self._set_clip_loop_range(state, start, end)
        self._clear_pending_steps()
        state.last_pad_time = now
        state.last_pad_index = step
        self._force_update = True
        self.update()

    def _toggle_track_mode(self):
        self._is_4_track_mode = not self._is_4_track_mode
        self._quantization_step_size = 16 if self._is_4_track_mode else 8
        self._clear_pending_steps()
        self._clamp_track_offset()
        self._refresh_track_states()
        focused_state = self._focused_state()
        if focused_state is not None:
            self._select_track_for_state(focused_state)
        self._force_update = True
        self._control_surface.show_message("Looper %d-Trk" % self._track_count_for_mode())
        self._update_OSD()
        self.update()

    def _nudge_track_offset(self, delta):
        tracks = list(self.song().tracks)
        count = self._track_count_for_mode()
        max_offset = max(0, len(tracks) - count)
        new_offset = max(0, min(self._track_offset + delta, max_offset))
        if new_offset != self._track_offset:
            self._track_offset = new_offset
            self._clear_pending_steps()
            self._refresh_track_states()
            focused_state = self._focused_state()
            if focused_state is not None:
                self._select_track_for_state(focused_state)
            self._force_update = True
            self.update()

    def _visible_bank_size(self):
        return 4 if self._is_4_track_mode else 8

    def _can_bank_left(self):
        return self._track_offset > 0

    def _can_bank_right(self):
        tracks = list(self.song().tracks)
        return self._track_offset + self._visible_bank_size() < len(tracks)

    def _can_scene_up(self):
        return self._selected_scene_index > 0

    def _can_scene_down(self):
        return self._selected_scene_index < len(list(self.song().scenes)) - 1

    def _scroll_scene(self, delta):
        if delta == 0:
            return
        scenes = list(self.song().scenes)
        if not scenes:
            return
        new_index = max(0, min(self._selected_scene_index + delta, len(scenes) - 1))
        if new_index != self._selected_scene_index:
            try:
                self.song().view.selected_scene = scenes[new_index]
            except RuntimeError:
                pass

    def _toggle_track_mute(self):
        state = self._focused_state()
        if state is None or state.track is None:
            return
        try:
            state.track.mute = not state.track.mute
            self._control_surface.show_message("track %s %s" % (state.track.name, "muted" if state.track.mute else "unmuted"))
        except RuntimeError:
            pass

    def _toggle_track_solo(self):
        state = self._focused_state()
        if state is None or state.track is None:
            return
        try:
            state.track.solo = not state.track.solo
            self._control_surface.show_message("track %s %s" % (state.track.name, "solo" if state.track.solo else "unsolo"))
        except RuntimeError:
            pass

    def _toggle_track_arm(self):
        state = self._focused_state()
        if state is None or state.track is None or not state.track.can_be_armed:
            return
        try:
            state.track.arm = not state.track.arm
            self._control_surface.show_message("track %s %s" % (state.track.name, "armed" if state.track.arm else "unarmed"))
        except RuntimeError:
            pass

    def _stop_visible_tracks(self):
        for i in xrange(self._track_count_for_mode()):
            state = self._track_states[i]
            if state.track is None:
                continue
            try:
                state.track.stop_all_clips()
            except RuntimeError:
                pass
        self._control_surface.show_message("stop visible tracks")

    def _button_is_pressed(self, value, sender):
        return value != 0 or not sender.is_momentary()

    def _track_count_button_value(self, value, sender):
        if self.is_enabled() and self._button_is_pressed(value, sender):
            self._toggle_track_mode()

    def _bank_left_button_value(self, value, sender):
        if self.is_enabled() and self._button_is_pressed(value, sender):
            self._nudge_track_offset(-self._visible_bank_size())

    def _bank_right_button_value(self, value, sender):
        if self.is_enabled() and self._button_is_pressed(value, sender):
            self._nudge_track_offset(self._visible_bank_size())

    def _reserved_button_value(self, value, sender):
        if self.is_enabled() and self._button_is_pressed(value, sender):
            self._force_update = True
            self.update()

    def _stop_button_value(self, value, sender):
        if self.is_enabled() and self._button_is_pressed(value, sender):
            self._stop_visible_tracks()
            self._force_update = True
            self.update()

    def _mute_button_value(self, value, sender):
        if self.is_enabled() and self._button_is_pressed(value, sender):
            self._toggle_track_mute()
            self._force_update = True
            self.update()

    def _solo_button_value(self, value, sender):
        if self.is_enabled() and self._button_is_pressed(value, sender):
            self._toggle_track_solo()
            self._force_update = True
            self.update()

    def _arm_button_value(self, value, sender):
        if self.is_enabled() and self._button_is_pressed(value, sender):
            self._toggle_track_arm()
            self._force_update = True
            self.update()

    def _scene_up_button_value(self, value, sender):
        if self.is_enabled() and self._button_is_pressed(value, sender):
            self._scroll_scene(-1)

    def _scene_down_button_value(self, value, sender):
        if self.is_enabled() and self._button_is_pressed(value, sender):
            self._scroll_scene(1)

    def _top_bank_left_button_value(self, value, sender):
        if self.is_enabled() and self._button_is_pressed(value, sender):
            self._nudge_track_offset(-self._visible_bank_size())

    def _top_bank_right_button_value(self, value, sender):
        if self.is_enabled() and self._button_is_pressed(value, sender):
            self._nudge_track_offset(self._visible_bank_size())

    def _render_grid(self):
        if self._matrix is None:
            return

        for x in xrange(8):
            for y in xrange(8):
                self._grid_back_buffer[x][y] = "DefaultButton.Disabled"

        for i in xrange(self._track_count_for_mode()):
            state = self._track_states[i]
            pads = self._pads_per_track()
            quant = self._clip_quant(state)
            if state.clip is None or quant <= 0:
                # Empty tracks still get a consistent visual lane so the player
                # can see which tracks are available in this bank.
                for step in xrange(pads):
                    col, row = self._step_to_grid(step, i)
                    if 0 <= row < 8:
                        self._grid_back_buffer[col][row] = "LoopingClipMode.TrackEmpty"
                continue

            loop_start_step = max(0, min(self._beat_to_step(state, state.loop_start), pads - 1))
            loop_end_step = max(loop_start_step + 1, min(self._beat_to_step(state, state.loop_end), pads))
            if state.loop_end >= state.clip_end:
                loop_end_step = pads

            for step in xrange(pads):
                col, row = self._step_to_grid(step, i)
                if row >= 8:
                    continue
                # Paint the loop like a phrase on a timeline: start marker,
                # body, and end marker.
                if step >= loop_start_step and step < loop_end_step:
                    if step == loop_start_step:
                        color = "LoopingClipMode.PadStart"
                    elif step == loop_end_step - 1:
                        color = "LoopingClipMode.PadEnd"
                    else:
                        color = "LoopingClipMode.PadInLoop"
                else:
                    color = "LoopingClipMode.PadOff"
                self._grid_back_buffer[col][row] = color

            if state.playhead is not None and quant > 0:
                playhead_step = self._beat_to_step(state, state.playhead)
                if 0 <= playhead_step < pads:
                    # The playhead light is a moving cursor showing where the
                    # clip is currently sounding.
                    col, row = self._step_to_grid(playhead_step, i)
                    if row < 8:
                        self._grid_back_buffer[col][row] = "LoopingClipMode.Playing"

            if state.pending_start_step is not None:
                # While the player is still choosing the loop start, show that
                # anchor point before the range is committed.
                col, row = self._step_to_grid(state.pending_start_step, i)
                if row < 8:
                    self._grid_back_buffer[col][row] = "LoopingClipMode.PadSelected"

        for x in xrange(8):
            for y in xrange(8):
                if self._grid_back_buffer[x][y] != self._grid_buffer[x][y] or self._force_update:
                    # Double-buffer the pad colors so we only send MIDI/light
                    # updates when something actually changed.
                    self._grid_buffer[x][y] = self._grid_back_buffer[x][y]
                    self._matrix.get_button(x, y).set_light(self._grid_buffer[x][y])

        self._force_update = False

    def _clear_grid(self):
        if self._matrix is None:
            return
        for x in xrange(8):
            for y in xrange(8):
                self._grid_buffer[x][y] = "DefaultButton.Disabled"
                self._grid_back_buffer[x][y] = "DefaultButton.Disabled"
                self._matrix.get_button(x, y).set_light("DefaultButton.Disabled")

    def update(self):
        if not self.is_enabled():
            return
        self._refresh_track_states()
        self._update_buttons()
        self._render_grid()
        self._update_OSD()

    def _update_buttons(self):
        self._update_track_count_button()
        self._update_bank_buttons()
        self._update_scene_buttons()
        self._update_track_action_buttons()

    def _update_track_count_button(self):
        button = self._side_buttons[0]
        if button is not None:
            button.set_on_off_values("LoopingClipMode.Toggle.On", "LoopingClipMode.Toggle.Off")
            if self._is_4_track_mode:
                button.turn_on()
            else:
                button.turn_off()

    def _update_bank_buttons(self):
        left_buttons = [self._side_buttons[1], self._top_buttons[2]]
        right_buttons = [self._side_buttons[2], self._top_buttons[3]]

        for button in left_buttons:
            if button is not None:
                button.set_on_off_values("Mode.LoopingClipMode.On", "Mode.LoopingClipMode.Off")
                if self._can_bank_left():
                    button.turn_on()
                else:
                    button.turn_off()

        for button in right_buttons:
            if button is not None:
                button.set_on_off_values("Mode.LoopingClipMode.On", "Mode.LoopingClipMode.Off")
                if self._can_bank_right():
                    button.turn_on()
                else:
                    button.turn_off()

        if self._side_buttons[3] is not None:
            self._side_buttons[3].set_light("DefaultButton.Disabled")

    def _update_scene_buttons(self):
        up_button = self._top_buttons[0]
        down_button = self._top_buttons[1]
        if up_button is not None:
            up_button.set_on_off_values("Mode.LoopingClipMode.On", "Mode.LoopingClipMode.Off")
            if self._can_scene_up():
                up_button.turn_on()
            else:
                up_button.turn_off()
        if down_button is not None:
            down_button.set_on_off_values("Mode.LoopingClipMode.On", "Mode.LoopingClipMode.Off")
            if self._can_scene_down():
                down_button.turn_on()
            else:
                down_button.turn_off()

    def _update_track_action_buttons(self):
        focused_state = self._focused_state()
        track = focused_state.track if focused_state is not None else None

        stop_button = self._side_buttons[4]
        if stop_button is not None:
            stop_button.set_on_off_values("TrackController.Stop.On", "TrackController.Stop.Off")
            if track is not None:
                stop_button.turn_on()
            else:
                stop_button.turn_off()

        mute_button = self._side_buttons[5]
        if mute_button is not None:
            mute_button.set_on_off_values("TrackController.Mute.On", "TrackController.Mute.Off")
            if track is not None and not track.mute:
                mute_button.turn_on()
            else:
                mute_button.turn_off()

        solo_button = self._side_buttons[6]
        if solo_button is not None:
            solo_button.set_on_off_values("TrackController.Solo.On", "TrackController.Solo.Off")
            if track is not None and track.solo:
                solo_button.turn_on()
            else:
                solo_button.turn_off()

        arm_button = self._side_buttons[7]
        if arm_button is not None:
            arm_button.set_on_off_values("TrackController.Recording.On", "TrackController.Recording.Off")
            if track is not None and track.can_be_armed and track.arm:
                arm_button.turn_on()
            else:
                arm_button.turn_off()

    def _update_OSD(self):
        if self._osd is None:
            return

        visible_count = self._track_count_for_mode()
        last_track = min(len(list(self.song().tracks)), self._track_offset + visible_count)
        mode_label = "%d-track (%d-%d)" % (visible_count, self._track_offset + 1, max(self._track_offset + 1, last_track))
        quant_label = "1/%d" % self._quantization_step_size

        focused_state = self._focused_state()
        track_name = "---"
        clip_name = "---"
        if focused_state is not None and focused_state.track is not None:
            track_name = focused_state.track.name
            if focused_state.clip is not None:
                clip_name = focused_state.clip.name or "(unnamed clip)"

        self._osd.set_mode("Looping Clip Mode")
        self._osd.attributes[0] = "---"
        self._osd.attribute_names[0] = "Scale"
        self._osd.attributes[1] = "---"
        self._osd.attribute_names[1] = "Root"
        self._osd.attributes[2] = mode_label
        self._osd.attribute_names[2] = "Tracks"
        self._osd.attributes[3] = quant_label
        self._osd.attribute_names[3] = "Quant"
        for i in xrange(4, 8):
            self._osd.attributes[i] = " "
            self._osd.attribute_names[i] = " "

        self._osd.info[0] = "track : " + track_name
        self._osd.info[1] = "clip  : " + clip_name
        self._osd.update()

    def on_track_list_changed(self):
        if self.is_enabled():
            self._clamp_track_offset()
            self._force_update = True
            self.update()

    def on_scene_list_changed(self):
        if self.is_enabled():
            self._selected_scene_index = self._current_scene_index()
            self._force_update = True
            self.update()

    def on_selected_track_changed(self):
        if self.is_enabled():
            self._force_update = True
            self.update()

    def on_selected_scene_changed(self):
        if self.is_enabled():
            scene = self._current_scene_index()
            if scene != self._selected_scene_index:
                self._selected_scene_index = scene
                self._clear_pending_steps()
                self._refresh_track_states()
                self._force_update = True
            self.update()
