import json
import os
from datetime import datetime

class CheckpointManager:
    """Manage research checkpointing for resume capability."""

    def __init__(self, log_path=None):
        self.log_path = log_path or "/Users/tri-mac/Obsidian Vault/Odoo 19/Research-Log/active-run"
        self.checkpoint_file = os.path.join(self.log_path, "checkpoint.json")
        self.status_file = os.path.join(self.log_path, "status.json")

    def save_checkpoint(self, state):
        """Save current research state."""
        state['last_checkpoint'] = datetime.now().isoformat()
        with open(self.checkpoint_file, 'w') as f:
            json.dump(state, f, indent=2)
        return True

    def load_checkpoint(self):
        """Load last checkpoint for resume."""
        if not os.path.exists(self.checkpoint_file):
            return None

        with open(self.checkpoint_file, 'r') as f:
            return json.load(f)

    def update_status(self, status):
        """Update run status."""
        with open(self.status_file, 'w') as f:
            json.dump(status, f, indent=2)

    def load_status(self):
        """Load current status."""
        if not os.path.exists(self.status_file):
            return None
        with open(self.status_file, 'r') as f:
            return json.load(f)

    def start_run(self, run_id, options):
        """Initialize new research run."""
        state = {
            'run_id': run_id,
            'started_at': datetime.now().isoformat(),
            'last_checkpoint': datetime.now().isoformat(),
            'options': options,
            'status': 'running',
            'current_module': '',
            'current_model': '',
            'current_task': '',
            'current_depth_level': 1,
            'modules_completed': [],
            'modules_in_progress': [],
            'modules_pending': [],
            'gaps_found_this_run': 0,
            'verified_entries': 0,
            'depth_escalations_done': 0,
            'unverified_items': 0,
            'stop_requested': False
        }
        self.save_checkpoint(state)

        status = {
            'is_running': True,
            'run_id': run_id,
            'mode': options.get('mode', 'deep'),
            'time_limit': options.get('limit', '60m'),
            'checkpoint_interval': options.get('checkpoint', '10m'),
            'target_modules': options.get('modules', 'all')
        }
        self.update_status(status)

        return state

    def stop_run(self, graceful=True):
        """Stop current run."""
        checkpoint = self.load_checkpoint()
        if checkpoint:
            checkpoint['status'] = 'stopped' if graceful else 'force_stopped'
            checkpoint['stopped_at'] = datetime.now().isoformat()
            self.save_checkpoint(checkpoint)

        status = self.load_status()
        if status:
            status['is_running'] = False
            status['stopped_at'] = datetime.now().isoformat()
            self.update_status(status)


def test_checkpoint_manager():
    cm = CheckpointManager()
    state = cm.start_run("run-2026-04-10-001", {'mode': 'deep'})
    assert state['status'] == 'running'

    loaded = cm.load_checkpoint()
    assert loaded['run_id'] == "run-2026-04-10-001"

    cm.stop_run()
    loaded = cm.load_checkpoint()
    assert loaded['status'] == 'stopped'

    print("Checkpoint resume test passed!")


if __name__ == "__main__":
    test_checkpoint_manager()
