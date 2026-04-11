# AutoResearch User Guide

## Quick Start

### Starting Research
```
/autorestart                    # Start with defaults (deep mode, 60min)
/autorestart --modules=stock   # Focus on specific module
/autorestart --mode=quick      # Quick verification only
/autorestart --limit=30m       # Set time limit
```

### Monitoring
```
/autorestatus                  # Show current status
/autorelog 100                 # Show last 100 log lines
```

### Verification
```
/autoverify module=stock       # Verify specific module
/autoverify model=stock.quant  # Verify specific model
```

### Stopping
```
/autorestop                    # Graceful stop (saves progress)
/autorestop --force            # Immediate stop
```

## Understanding Output

### Verification Status
- **Verified:** Code read and confirmed
- **Partial:** Core verified, edge cases need more
- **Outdated:** Code differs from documentation
- **Unknown:** Never been verified

### Depth Levels
- **L1 (Surface):** What is this?
- **L2 (Context):** Why does it exist?
- **L3 (Edge Cases):** What are the boundaries?
- **L4 (Historical):** How did it evolve?

## Checking Progress

### Research Log Location
- Backlog: `Research-Log/backlog.md`
- Verified Status: `Research-Log/verified-status.md`
- Current Run: `Research-Log/active-run/`
- Completed Runs: `Research-Log/completed-runs/`
- Insights: `Research-Log/insights/`

### Reading Checkpoint
```bash
cat Research-Log/active-run/checkpoint.json
```

### Finding New Gaps
```bash
cat Research-Log/backlog.md | grep -A5 "Critical"
```

## Architecture

### Core Components

1. **scanner_module.py** - Scans Odoo addons directory, lists all modules
2. **scanner_model.py** - Scans module models, extracts fields and methods
3. **verification_engine.py** - Verifies documentation against actual code
4. **depth_engine.py** - Explores L1-L4 depth for fields and methods
5. **research_agent.py** - Coordinates parallel verification + depth
6. **checkpoint_manager.py** - Manages checkpoint save/resume
7. **gap_detector.py** - Compares code vs vault, identifies gaps

### Skills
- `/autorestart` - Start/stop research
- `/autorestop` - Stop gracefully or force
- `/autorestatus` - Show current status
- `/autoverify` - Verify specific module
- `/autorelog` - Show activity log

## Troubleshooting

### Research stopped unexpectedly
- Check `/autorestatus` for last checkpoint
- Use `/autorestart` to resume from last position

### Gap detection seems incomplete
- Verify `~/odoo/odoo19/odoo/addons/` path is correct
- Check that modules directory exists

### Too many unverified items
- Run `/autorestart --mode=deep` for thorough verification
- Run `/autoverify module=X --deep` for specific module

## Examples

### Start Deep Research on Stock Module
```
/autorestart --modules=stock --mode=deep --limit=2h
```

### Verify Sale Module Documentation
```
/autoverify module=sale --deep
```

### Check Current Research Status
```
/autorestatus
```

### Stop and Save Progress
```
/autorestop
```
