from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql://user:password@localhost:5432/profiles_db"
    APP_NAME: str = "Profile Intelligence Service"
    APP_VERSION: str = "2.0.0"
    INTERNAL_SEED_ENABLED: bool = False
    INTERNAL_SEED_TOKEN: str = ""
    INTERNAL_SEED_FILE: str = "seed_profiles.json"

    class Config:
        env_file = ".env"


settings = Settings()
