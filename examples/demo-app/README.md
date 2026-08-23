# Demo App

This repository is a small authentication example used to test the local AI coding assistant.

Architecture:

API layer
    ↓
Service layer
    ↓
Authentication + Database

Important files:

- app/api.py contains request handling.
- app/service.py contains business logic.
- app/auth.py contains password hashing and token logic.
- app/database.py contains SQLite operations.

The login endpoint contains a deliberate HTTP status-code bug.
