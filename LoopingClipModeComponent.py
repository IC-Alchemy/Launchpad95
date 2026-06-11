import time
import Live

from _Framework.ButtonElement import ButtonElement
from _Framework.ButtonMatrixElement import ButtonMatrixElement
from _Framework.CompoundComponent import CompoundComponent

try:
    xrange
except NameError:
    xrange = range


class TrackLoopState:

    def __init__(self):
        self.track = None
        self.clip = None
        self.clip_slot = None
        self.loop_start = 0.0
        self.loop_end = 0.0
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

        self._track_states = [TrackLoopState() for _ in xrange(8)]

        self._track_count_button = None
        self.set_track_count_button(self._side_buttons[0])
        self._quantization_button = None
        self.set_quantization_button(self._side_buttons[2])

        self._quantization_step_size = 16

        self._grid_buffer = [[0] * 8 for _ in xrange(8)]
        self._grid_back_buffer = [[0] * 8 for _ in xrange(8)]
        self._force_update = True

        if self._matrix is not None:
            self._matrix.add_value_listener(self._matrix_value)

        self.set_enabled(False)

    def disconnect(self):
        self._track_count_button = None
        self._quantization_button = None
        self._side_buttons = None
        self._top_buttons = None
        if self._matrix is not None:
            self._matrix.remove_value_listener(self._matrix_value)
        self._matrix = None
        self._osd = None
        for state in self._track_states:
            self._remove_clip_listeners(state)
        super(LoopingClipModeComponent, self).disconnect()

    def set_osd(self, osd):
        self._osd = osd

    def set_enabled(self, enabled):
        if enabled:
            self._force_update = True
            self._refresh_track_states()
            self._update_OSD()
        else:
            for state in self._track_states:
                self._remove_clip_listeners(state)
                state.clip = None
                state.clip_slot = None
            self._clear_grid()
        CompoundComponent.set_enabled(self, enabled)

    def _track_count_for_mode(self):
        return 4 if self._is_4_track_mode else 8

    def _pads_per_track(self):
        return 16 if self._is_4_track_mode else 8

    def _rows_per_track(self):
        return 2 if self._is_4_track_mode else 1

    def _step_to_grid(self, step, track_index):
        pads = self._pads_per_track()
        cols = 8
        rows = self._rows_per_track()
        base_row = track_index * rows
        col = step % cols
        sub_row = step // cols
        return col, base_row + sub_row

    def _grid_to_step(self, x, y):
        pads = self._pads_per_track()
        rows = self._rows_per_track()
        track_index = y // rows
        if track_index >= self._track_count_for_mode():
            return None, None
        sub_row = y % rows
        step = sub_row * 8 + x
        return track_index, step

    def _refresh_track_states(self):
        song = self.song()
        tracks = list(song.tracks)
        scene_index = self._selected_scene_index
        scenes = list(song.scenes)

        for i in xrange(self._track_count_for_mode()):
            state = self._track_states[i]
            track_idx = self._track_offset + i
            if track_idx < len(tracks):
                track = tracks[track_idx]
                state.track = track
                clip_slot = None
                if scene_index < len(scenes):
                    try:
                        clip_slots = list(track.clip_slots)
                        if scene_index < len(clip_slots):
                            clip_slot = clip_slots[scene_index]
                    except (RuntimeError, IndexError):
                        clip_slot = None

                if clip_slot != state.clip_slot:
                    self._remove_clip_listeners(state)
                    state.clip_slot = clip_slot
                    if clip_slot is not None and clip_slot.has_clip:
                        state.clip = clip_slot.clip
                        if state.clip is not None:
                            self._add_clip_listeners(state)
                            self._read_clip_loop(state)
                    else:
                        state.clip = None
                elif state.clip_slot is not None and state.clip_slot.has_clip:
                    if state.clip is not None:
                        self._read_clip_loop(state)
            else:
                self._remove_clip_listeners(state)
                state.track = None
                state.clip = None
                state.clip_slot = None

    def _read_clip_loop(self, state):
        if state.clip is not None:
            try:
                state.loop_start = state.clip.loop_start
                state.loop_end = state.clip.loop_end
            except RuntimeError:
                state.loop_start = 0.0
                state.loop_end = 0.0

    def _add_clip_listeners(self, state):
        if state.clip is not None:
            try:
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
            state.clip = None

    def _on_loop_changed(self):
        if self.is_enabled():
            for state in self._track_states:
                self._read_clip_loop(state)
            self._force_update = True
            self.update()

    def _on_playing_position_changed(self):
        if self.is_enabled():
            for state in self._track_states:
                if state.clip is not None:
                    try:
                        if state.clip.is_playing and self.song().is_playing:
                            state.playhead = state.clip.playing_position
                        else:
                            state.playhead = None
                    except RuntimeError:
                        state.playhead = None
            self._force_update = True
            self.update()

    def _on_playing_status_changed(self):
        self._on_playing_position_changed()

    def _set_clip_loop_range(self, state, start_step, end_step):
        if state.clip is None:
            return
        step_size = self._quantization_step_size
        quant = state.loop_end / step_size if state.loop_end > 0 else 0.25
        beat_start = start_step * quant
        beat_end = end_step * quant
        try:
            if beat_start >= state.clip.loop_end:
                state.clip.loop_end = beat_end
                state.clip.loop_start = beat_start
                state.clip.end_marker = beat_end
                state.clip.start_marker = beat_start
            else:
                state.clip.loop_start = beat_start
                state.clip.loop_end = beat_end
                state.clip.start_marker = beat_start
                state.clip.end_marker = beat_end
            state.loop_start = beat_start
            state.loop_end = beat_end
        except RuntimeError:
            pass

    def _matrix_value(self, value, x, y, is_momentary):
        if not self.is_enabled() or self._matrix is None:
            return
        track_index, step = self._grid_to_step(x, y)
        if track_index is None:
            return
        state = self._track_states[track_index]
        if state.clip is None:
            return

        pads = self._pads_per_track()
        now = time.time()

        if value > 0:
            if state.pending_end_step is not None:
                state.pending_end_step = step
            else:
                state.pending_start_step = step
                state.pending_end_step = None
        else:
            if state.pending_start_step is None:
                return

            if state.pending_end_step is None:
                if state.last_pad_index == step and (now - state.last_pad_time) < 0.25:
                    state.pending_end_step = step + 1
                else:
                    state.pending_end_step = step + 1

            if state.pending_start_step is not None and state.pending_end_step is not None:
                start = min(state.pending_start_step, state.pending_end_step)
                end = max(state.pending_start_step, state.pending_end_step)
                self._set_clip_loop_range(state, start, end)

            state.pending_start_step = None
            state.pending_end_step = None
            state.last_pad_time = now
            state.last_pad_index = step
            self._force_update = True
            self.update()

    def _toggle_track_mode(self):
        self._is_4_track_mode = not self._is_4_track_mode
        self._quantization_step_size = 16 if self._is_4_track_mode else 8
        for state in self._track_states:
            self._remove_clip_listeners(state)
            state.clip = None
            state.clip_slot = None
            state.pending_start_step = None
            state.pending_end_step = None
        self._refresh_track_states()
        self._force_update = True
        self._control_surface.show_message("Looper %d-Trk" % self._track_count_for_mode())
        self._update_OSD()
        self.update()

    def _nudge_track_offset(self, delta):
        tracks = list(self.song().tracks)
        count = self._track_count_for_mode()
        new_offset = self._track_offset + delta
        if 0 <= new_offset <= max(0, len(tracks) - count):
            self._track_offset = new_offset
            for state in self._track_states:
                self._remove_clip_listeners(state)
                state.clip = None
                state.clip_slot = None
            self._refresh_track_states()
            self._force_update = True
            self.update()

    def _render_grid(self):
        if self._matrix is None:
            return
        step_size = self._quantization_step_size

        for x in xrange(8):
            for y in xrange(8):
                self._grid_back_buffer[x][y] = "DefaultButton.Disabled"

        for i in xrange(self._track_count_for_mode()):
            state = self._track_states[i]
            pads = self._pads_per_track()
            quant = state.loop_end / step_size if state.loop_end > 0 else 0.25
            if state.clip is None or quant <= 0:
                for step in xrange(pads):
                    col, row = self._step_to_grid(step, i)
                    if 0 <= row < 8:
                        self._grid_back_buffer[col][row] = "LoopingClipMode.TrackEmpty"
                continue

            loop_start_step = int(state.loop_start / quant + 0.0001)
            loop_end_step = int(state.loop_end / quant + 0.0001)

            for step in xrange(pads):
                col, row = self._step_to_grid(step, i)
                if row >= 8:
                    continue
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
                playhead_step = int(state.playhead / quant)
                if 0 <= playhead_step < pads:
                    col, row = self._step_to_grid(playhead_step, i)
                    if row < 8:
                        self._grid_back_buffer[col][row] = "LoopingClipMode.Playing"

            if state.pending_start_step is not None and state.pending_end_step is None:
                col, row = self._step_to_grid(state.pending_start_step, i)
                if row < 8:
                    self._grid_back_buffer[col][row] = "LoopingClipMode.PadSelected"

        for x in xrange(8):
            for y in xrange(8):
                if self._grid_back_buffer[x][y] != self._grid_buffer[x][y] or self._force_update:
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
        self._update_quantization_button()

    def _update_track_count_button(self):
        if self._track_count_button is not None:
            self._track_count_button.set_on_off_values("LoopingClipMode.Toggle.On", "LoopingClipMode.Toggle.Off")
            if self._is_4_track_mode:
                self._track_count_button.turn_on()
            else:
                self._track_count_button.turn_off()

    def set_track_count_button(self, button):
        if self._track_count_button != button:
            if self._track_count_button is not None:
                self._track_count_button.remove_value_listener(self._track_count_button_value)
            self._track_count_button = button
            if self._track_count_button is not None:
                self._track_count_button.add_value_listener(self._track_count_button_value, identify_sender=True)

    def _track_count_button_value(self, value, sender):
        if self.is_enabled():
            if value == 0 and sender.is_momentary():
                self._toggle_track_mode()

    def _update_quantization_button(self):
        if self._quantization_button is not None:
            self._quantization_button.set_on_off_values("DefaultButton.On", "DefaultButton.Off")
            self._quantization_button.turn_off()

    def set_quantization_button(self, button):
        if self._quantization_button != button:
            if self._quantization_button is not None:
                self._quantization_button.remove_value_listener(self._quantization_button_value)
            self._quantization_button = button
            if self._quantization_button is not None:
                self._quantization_button.add_value_listener(self._quantization_button_value, identify_sender=True)

    def _quantization_button_value(self, value, sender):
        pass

    def _update_OSD(self):
        if self._osd is None:
            return
        mode_name = "Looper 4-Trk" if self._is_4_track_mode else "Looper 8-Trk"
        self._osd.set_mode(mode_name)
        if self._is_4_track_mode:
            tracks_range = "%d-%d" % (self._track_offset + 1, self._track_offset + 4)
        else:
            tracks_range = "%d-%d" % (self._track_offset + 1, self._track_offset + 8)
        self._osd.attributes[0] = tracks_range
        self._osd.attribute_names[0] = "Tracks"
        self._osd.attributes[1] = " "
        self._osd.attribute_names[1] = " "
        self._osd.attributes[2] = " "
        self._osd.attribute_names[2] = " "
        self._osd.attributes[3] = " "
        self._osd.attribute_names[3] = " "
        for i in xrange(4, 8):
            self._osd.attributes[i] = " "
            self._osd.attribute_names[i] = " "

        self._osd.info[0] = " "
        self._osd.info[1] = " "
        self._osd.update()

    def on_selected_scene_changed(self):
        if self.is_enabled():
            try:
                scene = list(self.song().scenes).index(self.song().view.selected_scene)
                if scene != self._selected_scene_index:
                    self._selected_scene_index = scene
                    for state in self._track_states:
                        self._remove_clip_listeners(state)
                        state.clip = None
                        state.clip_slot = None
                    self._refresh_track_states()
                    self._force_update = True
                    self.update()
            except (RuntimeError, ValueError):
                pass
