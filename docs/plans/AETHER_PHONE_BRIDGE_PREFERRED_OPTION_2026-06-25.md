# Aether Phone Bridge Preferred Option - 2026-06-25

Purpose: capture Nick's preferred direction for a lightweight phone-to-Codex/Aether communication path.

## Preferred Option

Use a tiny authenticated local web relay / cheap control plane.

It does not need to be special. The basic target is:

- a random long token;
- view/send-message only;
- no arbitrary shell command endpoint;
- no direct remote command execution;
- optional Cloudflare Tunnel or Tailscale exposure;
- visible local logs;
- inexpensive/simple hosting or tunnel path if needed.

## Guardrail

The phone bridge should be a message/control plane, not a remote shell.

The safer shape is:

```text
phone message -> authenticated relay -> Codex/Aether sees instruction -> local agent applies judgment
```

Avoid:

```text
phone command -> tunnel -> local shell execution
```

## Status

Preference saved only. Do not implement until Nick explicitly asks.
