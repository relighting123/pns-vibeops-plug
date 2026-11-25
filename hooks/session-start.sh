#!/bin/sh
# Bounded static reminder: no model calls, network, state writes or project commands.
printf '%s\n' 'PNS VibeOps Plug: when starting or resuming SDLC work, read artifacts/sdlc-progress.md if present and verify it against current Git changes. Load only the current stage skill. Record actual test results; a checkpoint is not proof of success.'
