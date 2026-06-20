#!/usr/bin/env python3
"""
WOS Cycle Progress Monitor - Animated Terminal Dashboard
Beautiful real-time visualization of WOS cycle progress
"""

import sys
import time
import os
import re
from datetime import datetime, timedelta
from pathlib import Path


# ANSI color codes and styles
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    UNDERLINE = '\033[4m'
    RESET = '\033[0m'

    # Background colors
    BG_BLUE = '\033[44m'
    BG_GREEN = '\033[42m'
    BG_YELLOW = '\033[43m'
    BG_RED = '\033[41m'


# Animation frames
SPINNER_FRAMES = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']
PULSE_FRAMES = ['◐', '◓', '◑', '◒']
WAVE_FRAMES = ['▁', '▂', '▃', '▄', '▅', '▆', '▇', '█', '▇', '▆', '▅', '▄', '▃', '▂']


def clear_screen():
    """Clear terminal screen"""
    os.system('cls' if os.name == 'nt' else 'clear')


def move_cursor(row, col):
    """Move cursor to specific position"""
    print(f"\033[{row};{col}H", end='')


def hide_cursor():
    """Hide terminal cursor"""
    print("\033[?25l", end='')


def show_cursor():
    """Show terminal cursor"""
    print("\033[?25h", end='')


def draw_box(width, height, title=""):
    """Draw a box with optional title"""
    top = f"╔{'═' * (width - 2)}╗"
    bottom = f"╚{'═' * (width - 2)}╝"
    side = "║"

    lines = [top]
    if title:
        title_text = f" {title} "
        padding = (width - len(title_text) - 2) // 2
        title_line = f"║{' ' * padding}{Colors.BOLD}{title_text}{Colors.RESET}{' ' * (width - padding - len(title_text) - 2)}║"
        lines.append(title_line)
        lines.append(f"╠{'═' * (width - 2)}╣")

    for _ in range(height - (3 if title else 2)):
        lines.append(f"{side}{' ' * (width - 2)}{side}")

    lines.append(bottom)
    return lines


def draw_progress_bar(progress, width=50, filled_char='█', empty_char='░', show_percentage=True):
    """Draw a colorful progress bar"""
    filled = int(progress * width / 100)
    empty = width - filled

    # Color gradient based on progress
    if progress < 30:
        color = Colors.RED
    elif progress < 70:
        color = Colors.YELLOW
    else:
        color = Colors.GREEN

    bar = f"[{color}{filled_char * filled}{Colors.DIM}{empty_char * empty}{Colors.RESET}]"

    if show_percentage:
        bar += f" {Colors.BOLD}{progress:3d}%{Colors.RESET}"

    return bar


def format_duration(seconds):
    """Format duration in human-readable format"""
    td = timedelta(seconds=seconds)
    hours = td.seconds // 3600
    minutes = (td.seconds % 3600) // 60
    secs = td.seconds % 60

    if hours > 0:
        return f"{hours}h {minutes:02d}m {secs:02d}s"
    elif minutes > 0:
        return f"{minutes}m {secs:02d}s"
    else:
        return f"{secs}s"


def extract_metrics(output_file):
    """Extract metrics from WOS cycle output"""
    try:
        with open(output_file, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception:
        return {
            'completed': 0,
            'failed': 0,
            'checkpoints': 0,
            'utilization': 0,
            'running': 0,
            'max_agents': 16,
            'is_done': False,
            'latest_work': None,
        }

    # Extract metrics using regex
    completed = len(re.findall(r'Completed work item', content))
    failed = len(re.findall(r'Failed work item', content))
    checkpoints = len(re.findall(r'Checkpointing', content))

    # Latest utilization
    util_matches = re.findall(r'(\d+)% util', content)
    utilization = int(util_matches[-1]) if util_matches else 0

    # Running agents
    agent_matches = re.findall(r'(\d+)/(\d+) agents busy', content)
    if agent_matches:
        running, max_agents = map(int, agent_matches[-1])
    else:
        running, max_agents = 0, 16

    # Latest work item
    work_matches = re.findall(r'work item (\d+)', content)
    latest_work = int(work_matches[-1]) if work_matches else None

    # Check if done
    is_done = 'Cycle Complete' in content or 'Cycle exited' in content

    # Squad lead metrics
    squad_active = 'squad' in content.lower()

    return {
        'completed': completed,
        'failed': failed,
        'checkpoints': checkpoints,
        'utilization': utilization,
        'running': running,
        'max_agents': max_agents,
        'is_done': is_done,
        'latest_work': latest_work,
        'squad_active': squad_active,
    }


def draw_dashboard(metrics, elapsed, duration_seconds, frame):
    """Draw the animated dashboard"""
    clear_screen()

    # Calculate progress
    progress = min(100, int(elapsed * 100 / duration_seconds))
    remaining = max(0, duration_seconds - elapsed)

    total_work = metrics['completed'] + metrics['failed']
    success_rate = int(metrics['completed'] * 100 / total_work) if total_work > 0 else 0

    # Header
    print(f"\n{Colors.BOLD}{Colors.CYAN}╔{'═' * 78}╗{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}║{' ' * 20}🚀 WOS Cycle Progress Monitor 🚀{' ' * 21}║{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}╚{'═' * 78}╝{Colors.RESET}\n")

    # Spinner animation
    spinner = SPINNER_FRAMES[frame % len(SPINNER_FRAMES)]
    status_text = "RUNNING" if not metrics['is_done'] else "COMPLETE"
    status_color = Colors.BLUE if not metrics['is_done'] else Colors.GREEN
    print(f"  {status_color}{spinner} Status: {Colors.BOLD}{status_text}{Colors.RESET}\n")

    # Time Progress Box
    print(f"{Colors.CYAN}  ⏱️  Time Progress{Colors.RESET}")
    print(f"  {draw_progress_bar(progress, width=60)}")
    print(f"  {Colors.DIM}Elapsed:{Colors.RESET}   {format_duration(elapsed)}")
    if remaining > 0:
        print(f"  {Colors.DIM}Remaining:{Colors.RESET} {format_duration(remaining)}")
    else:
        overtime = elapsed - duration_seconds
        print(f"  {Colors.YELLOW}Overtime:{Colors.RESET}  {format_duration(overtime)}")
    print()

    # Work Items Box
    print(f"{Colors.CYAN}  📊 Work Items{Colors.RESET}")
    print(f"  ┌{'─' * 60}┐")
    print(f"  │ {Colors.GREEN}✓ Completed:{Colors.RESET} {metrics['completed']:3d}  "
          f"{Colors.YELLOW}✗ Failed:{Colors.RESET} {metrics['failed']:3d}  "
          f"{Colors.BOLD}Success:{Colors.RESET} {success_rate:3d}% │")
    if metrics['latest_work']:
        pulse = PULSE_FRAMES[frame % len(PULSE_FRAMES)]
        print(f"  │ {pulse} Current work item: #{metrics['latest_work']:<5}                             │")
    print(f"  └{'─' * 60}┘")
    print()

    # Agent Utilization Box
    print(f"{Colors.CYAN}  🤖 Agent Status{Colors.RESET}")
    agent_bar_width = 40
    agent_progress = int(metrics['running'] * 100 / metrics['max_agents']) if metrics['max_agents'] > 0 else 0

    print(f"  {draw_progress_bar(agent_progress, width=agent_bar_width)}")
    print(f"  {Colors.DIM}Active Agents:{Colors.RESET} {metrics['running']}/{metrics['max_agents']}  "
          f"{Colors.DIM}Utilization:{Colors.RESET} {metrics['utilization']}%")

    # Squad mode indicator
    if metrics.get('squad_active'):
        print(f"  {Colors.GREEN}🎯 Squad Lead Mode: ACTIVE{Colors.RESET}")
    print()

    # Checkpoints
    print(f"{Colors.CYAN}  🎯 Quality Gates{Colors.RESET}")
    checkpoint_indicator = '●' * metrics['checkpoints'] + '○' * max(0, 5 - metrics['checkpoints'])
    print(f"  {checkpoint_indicator}  {metrics['checkpoints']} checkpoints completed")
    print()

    # Estimated completion
    if total_work > 0 and elapsed > 0 and not metrics['is_done']:
        items_per_min = total_work * 60 / elapsed
        estimated_total = int(items_per_min * (duration_seconds / 60))

        print(f"{Colors.CYAN}  📈 Projections{Colors.RESET}")
        print(f"  {Colors.DIM}Rate:{Colors.RESET}           {items_per_min:.1f} items/min")
        print(f"  {Colors.DIM}Projected Total:{Colors.RESET} ~{estimated_total} work items")
        print()

    # Wave animation at bottom
    wave_frame = frame % len(WAVE_FRAMES)
    wave = ''.join([WAVE_FRAMES[(wave_frame + i) % len(WAVE_FRAMES)] for i in range(40)])
    print(f"\n  {Colors.BLUE}{wave}{Colors.RESET}")

    # Footer
    if not metrics['is_done']:
        print(f"\n  {Colors.DIM}Press Ctrl+C to exit monitor (cycle continues in background){Colors.RESET}")
    else:
        print(f"\n  {Colors.GREEN}{Colors.BOLD}✓ Cycle completed successfully!{Colors.RESET}")
        print(f"  {Colors.DIM}Run 'wos cycle status' for detailed results{Colors.RESET}")


def main():
    if len(sys.argv) < 2:
        print("Usage: monitor-cycle-animated.py <output_file> [duration_minutes]")
        print("\nExample:")
        print("  python monitor-cycle-animated.py /tmp/wos-cycle.output 45")
        sys.exit(1)

    output_file = sys.argv[1]
    duration_minutes = int(sys.argv[2]) if len(sys.argv) > 2 else 45
    duration_seconds = duration_minutes * 60

    if not os.path.exists(output_file):
        print(f"Error: Output file not found: {output_file}")
        sys.exit(1)

    # Wait for file to have content
    print("Waiting for cycle to start...")
    start_time = time.time()
    while os.path.getsize(output_file) == 0 and (time.time() - start_time) < 30:
        time.sleep(1)

    hide_cursor()

    try:
        frame = 0
        cycle_start_time = time.time()

        while True:
            metrics = extract_metrics(output_file)
            elapsed = int(time.time() - cycle_start_time)

            draw_dashboard(metrics, elapsed, duration_seconds, frame)

            if metrics['is_done']:
                show_cursor()
                print()
                break

            time.sleep(0.5)  # Update every 500ms for smooth animation
            frame += 1

    except KeyboardInterrupt:
        show_cursor()
        print(f"\n\n{Colors.YELLOW}Monitor stopped. Cycle continues in background.{Colors.RESET}")
        print(f"Output file: {output_file}\n")
    except Exception as e:
        show_cursor()
        print(f"\n{Colors.RED}Error: {e}{Colors.RESET}\n")
        sys.exit(1)


if __name__ == '__main__':
    main()
