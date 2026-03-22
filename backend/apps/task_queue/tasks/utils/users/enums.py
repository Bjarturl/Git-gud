from enum import Enum


class Action(str, Enum):
    NO_USERNAME = "no_username"
    SKIPPED_EXISTING = "skipped_existing"
    UPDATED_EXISTING = "updated_existing"
    CREATED_NEW = "created_new"
