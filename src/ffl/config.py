from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    database_url: str = "postgresql+asyncpg://ffl:ffl@localhost:5432/ffl"

    atf_data_url: str = (
        "https://www.atf.gov/firearms/docs/undefined/ffllisting_0txt/download"
    )

    geocode_batch_size: int = 2500
    geocode_benchmark: str = "Public_AR_Current"
    geocode_vintage: str = "Current_Current"

    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_origins: list[str] = ["http://localhost:3000"]


settings = Settings()
