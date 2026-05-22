from enum import Enum


class Environment(str, Enum):
    LOCAL = "local"
    STAGING = "staging"
    PRODUCTION = "production"


SHOW_DOCS_ENVIRONMENTS = (Environment.LOCAL, Environment.STAGING)
