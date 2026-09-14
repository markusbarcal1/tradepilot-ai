from uuid import UUID


# Temporary compatibility identity for pre-authentication development. Phase 3
# will replace this internal context with the authenticated JWT subject.
DEFAULT_DEV_USER_ID = UUID("00000000-0000-4000-8000-000000000001")
DEFAULT_DEV_USER_EMAIL = "legacy-bootstrap@local.invalid"
DEFAULT_DEV_USER_DISPLAY_NAME = "Legacy Local User"
