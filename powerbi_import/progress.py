"""Migration progress tracker with callback support.

Provides ``MigrationProgress`` — a lightweight observer that tracks
step-level progress and can trigger user-supplied callbacks on each
step transition.  Works in both CLI (prints a progress bar) and
programmatic (callback) modes.

Usage::

    from powerbi_import.progress import MigrationProgress

    progress = MigrationProgress(total_steps=5, on_step=my_callback)
    progress.start("Extracting datasources")
    # ... do work ...
    progress.complete("Extracted 12 tables")
    progress.start("Converting DAX formulas")
    # ...
"""

import sys
import time


class MigrationProgress:
    """Tracks migration progress across steps.

    Args:
        total_steps: Total number of migration steps.
        on_step: Optional callback ``(step_index, step_name, status, message)``
                 called on each ``start()`` and ``complete()`` call.
        show_bar: If True (default), prints a progress bar to stderr.
        bar_width: Width of the progress bar in characters.
    """

    def __init__(self, total_steps=5, on_step=None, show_bar=True, bar_width=40):
        self.total_steps = total_steps
        self.on_step = on_step
        self.show_bar = show_bar
        self.bar_width = bar_width
        self._current = 0
        self._steps = []
        self._start_time = None
        self._step_start = None

    def start(self, step_name):
        """Mark a new step as in progress.

        Args:
            step_name: Human-readable description of the step.
        """
        self._current += 1
        self._step_start = time.time()
        if self._start_time is None:
            self._start_time = self._step_start

        self._steps.append({
            'index': self._current,
            'name': step_name,
            'status': 'in_progress',
            'started_at': self._step_start,
        })

        if self.on_step:
            self.on_step(self._current, step_name, 'in_progress', '')

        if self.show_bar:
            self._print_bar(step_name, 'in_progress')

    def complete(self, message=''):
        """Mark the current step as complete.

        Args:
            message: Optional completion message.
        """
        if self._steps:
            step = self._steps[-1]
            step['status'] = 'complete'
            step['message'] = message
            elapsed = time.time() - (self._step_start or time.time())
            step['elapsed'] = round(elapsed, 2)

            if self.on_step:
                self.on_step(step['index'], step['name'], 'complete', message)

            if self.show_bar:
                self._print_bar(step['name'], 'complete', message)

    def fail(self, error=''):
        """Mark the current step as failed.

        Args:
            error: Error description.
        """
        if self._steps:
            step = self._steps[-1]
            step['status'] = 'failed'
            step['error'] = error
            elapsed = time.time() - (self._step_start or time.time())
            step['elapsed'] = round(elapsed, 2)

            if self.on_step:
                self.on_step(step['index'], step['name'], 'failed', error)

            if self.show_bar:
                self._print_bar(step['name'], 'failed', error)

    def skip(self, step_name, reason=''):
        """Record a skipped step.

        Args:
            step_name: Name of the skipped step.
            reason: Why it was skipped.
        """
        self._current += 1
        self._steps.append({
            'index': self._current,
            'name': step_name,
            'status': 'skipped',
            'message': reason,
        })
        if self.on_step:
            self.on_step(self._current, step_name, 'skipped', reason)
        if self.show_bar:
            self._print_bar(step_name, 'skipped', reason)

    def summary(self):
        """Return a summary dict of all steps.

        Returns:
            dict: ``{'steps': [...], 'total_elapsed': float,
                     'completed': int, 'failed': int, 'skipped': int}``
        """
        total_elapsed = time.time() - (self._start_time or time.time())
        return {
            'steps': list(self._steps),
            'total_elapsed': round(total_elapsed, 2),
            'completed': sum(1 for s in self._steps if s['status'] == 'complete'),
            'failed': sum(1 for s in self._steps if s['status'] == 'failed'),
            'skipped': sum(1 for s in self._steps if s['status'] == 'skipped'),
        }

    # ── Internal ──

    def _print_bar(self, step_name, status, message=''):
        """Print a progress bar to stderr."""
        pct = self._current / max(self.total_steps, 1)
        filled = int(self.bar_width * pct)
        bar = '█' * filled + '░' * (self.bar_width - filled)

        icons = {
            'in_progress': '⏳',
            'complete': '✅',
            'failed': '❌',
            'skipped': '⏭️',
        }
        icon = icons.get(status, '  ')

        line = f"\r  {icon} [{bar}] {self._current}/{self.total_steps} {step_name}"
        if message:
            line += f" — {message}"

        sys.stderr.write(line)
        if status in ('complete', 'failed', 'skipped'):
            sys.stderr.write('\n')
        sys.stderr.flush()


class NullProgress:
    """No-op progress tracker (silent)."""

    def start(self, step_name):
        pass

    def complete(self, message=''):
        pass

    def fail(self, error=''):
        pass

    def skip(self, step_name, reason=''):
        pass

    def summary(self):
        return {'steps': [], 'total_elapsed': 0, 'completed': 0, 'failed': 0, 'skipped': 0}
