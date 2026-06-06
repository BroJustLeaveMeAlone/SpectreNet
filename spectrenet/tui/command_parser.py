# spectrenet/tui/command_parser.py
from dataclasses import dataclass, field


@dataclass
class Command:
    verb: str
    args: list[str] = field(default_factory=list)
    flags: dict[str, str] = field(default_factory=dict)


def parse_command(line: str):
    """Parse a command string into a Command object.

    Args:
        line: Command string (e.g., "scan 10.0.0.1 --tool nmap")

    Returns:
        Command object or None if input is empty/whitespace.
    """
    tokens = line.split()
    if not tokens:
        return None

    verb = tokens[0]
    args: list[str] = []
    flags: dict[str, str] = {}

    i = 1
    while i < len(tokens):
        tok = tokens[i]
        if tok.startswith("--"):
            key = tok[2:]
            if i + 1 < len(tokens) and not tokens[i + 1].startswith("--"):
                flags[key] = tokens[i + 1]
                i += 2
            else:
                flags[key] = "true"
                i += 1
        else:
            args.append(tok)
            i += 1

    return Command(verb=verb, args=args, flags=flags)
