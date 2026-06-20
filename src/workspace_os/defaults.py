"""
WOS Default Configuration - World-Class Team Standards

All WOS cycles now operate with world-class development team standards by default.
These are MANDATORY behaviors, not optional features.

User requirement: "todas las mejoras de wos deben ser un comportamiento mandatorio
de cuando se ejecuta wos"
"""

import os


# Squad Lead Mode - MANDATORY (intelligent agent coordination)
# Only disable if you need legacy round-robin behavior
SQUAD_LEAD_ENABLED = os.environ.get("WOS_DISABLE_SQUAD_LEAD", "").lower() != "true"

# Role Rotation Cycle - Default 9 items (3 agents × 3 roles)
ROLE_ROTATION_CYCLE = int(os.environ.get("WOS_ROLE_ROTATION_CYCLE", "9"))

# Squad Context Window - Share last N work summaries between agents
SQUAD_CONTEXT_WINDOW = int(os.environ.get("WOS_SQUAD_CONTEXT_WINDOW", "5"))

# Dynamic Rebalancing - Adjust batch sizes based on utilization
DYNAMIC_REBALANCING = os.environ.get("WOS_DISABLE_DYNAMIC_REBALANCING", "").lower() != "true"

# Performance Tracking - Learn from agent performance
PERFORMANCE_TRACKING = os.environ.get("WOS_DISABLE_PERFORMANCE_TRACKING", "").lower() != "true"

# Progress Monitoring - Show animated progress by default
PROGRESS_MONITORING = os.environ.get("WOS_DISABLE_PROGRESS_MONITORING", "").lower() != "true"


def get_default_config():
    """
    Get default WOS configuration with world-class team standards.

    These defaults ensure:
    - High quality (95%+ success rate target)
    - Intelligent coordination (Squad Lead mode)
    - Continuous learning (performance tracking)
    - Good visibility (progress monitoring)
    """
    from workspace_os.agent_policy import _is_testing, available_work_agents

    # Testing uses minimal workers; production defaults to 16 for balanced quality/throughput
    # 16 workers = good balance between speed and quality control
    # Can be overridden with WOS_MAX_WORKERS for specific needs
    default_workers = len(available_work_agents()) if _is_testing() else 16

    return {
        # Squad Lead - Intelligent Coordination (MANDATORY)
        "squad_lead_enabled": SQUAD_LEAD_ENABLED,
        "role_rotation_cycle": ROLE_ROTATION_CYCLE,
        "squad_context_window": SQUAD_CONTEXT_WINDOW,
        "dynamic_rebalancing": DYNAMIC_REBALANCING,

        # Performance - Balanced Quality/Throughput
        "max_workers": int(os.environ.get("WOS_MAX_WORKERS", default_workers)),
        "checkpoint_interval_seconds": float(os.environ.get("WOS_CHECKPOINT_INTERVAL_SECONDS", "300.0")),
        "min_items_per_checkpoint": int(os.environ.get("WOS_MIN_ITEMS_PER_CHECKPOINT", str(2 * default_workers))),

        # Quality - Strict Gates
        "enable_auto_healing": os.environ.get("WOS_ENABLE_AUTO_HEALING", "true").lower() in ("true", "1", "yes"),
        "max_healing_attempts": int(os.environ.get("WOS_MAX_HEALING_ATTEMPTS", "2")),
        "checkpoint_fast_path_threshold": float(os.environ.get("WOS_CHECKPOINT_FAST_PATH_THRESHOLD", "0.8")),

        # Optimization
        "enable_issue_assignment": os.environ.get("WOS_ENABLE_ISSUE_ASSIGNMENT", "true").lower() in ("true", "1", "yes"),
        "performance_tracking": PERFORMANCE_TRACKING,
        "progress_monitoring": PROGRESS_MONITORING,
    }


def print_config_banner():
    """Print configuration banner showing active settings"""
    config = get_default_config()

    print("╔══════════════════════════════════════════════════════════════╗")
    print("║       WOS - World-Class Development Team Configuration       ║")
    print("╚══════════════════════════════════════════════════════════════╝")
    print()
    print("🎯 Squad Lead Mode:")
    print(f"  ✓ Intelligent Coordination: {'ENABLED' if config['squad_lead_enabled'] else 'DISABLED'}")
    print(f"  ✓ Role Rotation: Every {config['role_rotation_cycle']} work items")
    print(f"  ✓ Context Sharing: Last {config['squad_context_window']} items")
    print(f"  ✓ Dynamic Rebalancing: {'ENABLED' if config['dynamic_rebalancing'] else 'DISABLED'}")
    print()
    print("⚙️  Performance Settings:")
    print(f"  ✓ Max Workers: {config['max_workers']}")
    print(f"  ✓ Checkpoint Interval: {config['checkpoint_interval_seconds']:.0f}s")
    print(f"  ✓ Min Items per Checkpoint: {config['min_items_per_checkpoint']}")
    print()
    print("🛡️  Quality Gates:")
    print(f"  ✓ Auto-Healing: {'ENABLED' if config['enable_auto_healing'] else 'DISABLED'}")
    print(f"  ✓ Max Healing Attempts: {config['max_healing_attempts']}")
    print(f"  ✓ Fast-Path Threshold: {config['checkpoint_fast_path_threshold']:.0%}")
    print()
    print("📊 Optimization:")
    print(f"  ✓ Issue Pre-Assignment: {'ENABLED' if config['enable_issue_assignment'] else 'DISABLED'}")
    print(f"  ✓ Performance Tracking: {'ENABLED' if config['performance_tracking'] else 'DISABLED'}")
    print()
    print("Target: 95%+ success rate | World-class development standards")
    print()


def validate_config():
    """Validate configuration and warn about non-optimal settings"""
    config = get_default_config()
    warnings = []

    if not config['squad_lead_enabled']:
        warnings.append("⚠️  Squad Lead mode is DISABLED - this reduces quality and learning")

    if config['max_workers'] < 8:
        warnings.append(f"⚠️  Max workers ({config['max_workers']}) is very low - consider increasing for better throughput")

    if config['max_workers'] > 32:
        warnings.append(f"⚠️  Max workers ({config['max_workers']}) is very high - this may reduce quality control")

    if not config['enable_auto_healing']:
        warnings.append("⚠️  Auto-healing is DISABLED - failures won't be automatically corrected")

    if config['checkpoint_fast_path_threshold'] < 0.5:
        warnings.append(f"⚠️  Fast-path threshold ({config['checkpoint_fast_path_threshold']:.0%}) is low - more tests will be skipped")

    if warnings:
        print("Configuration Warnings:")
        for warning in warnings:
            print(f"  {warning}")
        print()

    return len(warnings) == 0


# Export for use in other modules
__all__ = [
    'get_default_config',
    'print_config_banner',
    'validate_config',
    'SQUAD_LEAD_ENABLED',
    'ROLE_ROTATION_CYCLE',
    'SQUAD_CONTEXT_WINDOW',
    'DYNAMIC_REBALANCING',
    'PERFORMANCE_TRACKING',
    'PROGRESS_MONITORING',
]
