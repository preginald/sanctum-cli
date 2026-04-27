# sanctum-cli

Unified CLI for Sanctum Core — manage tickets, articles, milestones, invoices, and more.

## Install

```bash
pip install sanctum-cli
```

## Usage

```bash
sanctum ticket list
sanctum article show DOC-009
sanctum search phoenix
sanctum --agent operator ticket create -s "Fix login" -p <project-uuid>
```

## Development

```bash
pip install -e ".[dev]"
pytest
```
