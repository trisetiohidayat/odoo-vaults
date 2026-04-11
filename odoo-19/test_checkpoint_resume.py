import sys
import json
import os
sys.path.insert(0, '/Users/tri-mac/Obsidian Vault/Odoo 19')

def test_checkpoint_and_resume():
    """Test checkpoint save and resume."""
    from checkpoint_manager import CheckpointManager

    log_path = "/Users/tri-mac/Obsidian Vault/Odoo 19/Research-Log/active-run"

    # 1. Start run
    cm = CheckpointManager(log_path)
    state = cm.start_run("run-test-001", {'mode': 'quick'})
    assert state['status'] == 'running', "Should start in running state"

    # 2. Save some progress
    state = cm.load_checkpoint()
    state['modules_completed'] = ['base', 'product']
    state['modules_in_progress'] = ['stock']
    state['gaps_found_this_run'] = 5
    cm.save_checkpoint(state)

    # 3. Verify checkpoint saved
    saved = cm.load_checkpoint()
    assert saved['modules_completed'] == ['base', 'product'], "Should save progress"
    assert saved['status'] == 'running', "Should still be running"

    # 4. Simulate stop
    cm.stop_run()
    stopped = cm.load_checkpoint()
    assert stopped['status'] == 'stopped', "Should be stopped"
    assert 'stopped_at' in stopped, "Should have stopped timestamp"

    # 5. Verify status file updated
    status = cm.load_status()
    assert status['is_running'] == False, "Status should show not running"

    print("Checkpoint resume test passed!")
    print(f"  Saved modules: {saved['modules_completed']}")
    print(f"  Gaps found: {saved['gaps_found_this_run']}")

if __name__ == "__main__":
    test_checkpoint_and_resume()
