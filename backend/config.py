from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DB_HOST: str = "localhost"
    DB_USER: str = "acore"
    DB_PASS: str = ""
    DB_NAME: str = "acore_characters"
    WORLD_DB_NAME: str = "acore_world"
    CORS_ORIGINS: str = "http://localhost:5000"

    model_config = {"env_file": "../.env", "env_file_encoding": "utf-8"}


settings = Settings()
