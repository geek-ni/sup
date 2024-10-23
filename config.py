from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # Database connection URL
    DATABASE_URL: str = "sqlite:///./passes.db"

    # Arduino connection settings
    ARDUINO_PORT: str = '/dev/tty.usbmodem11301'
    ARDUINO_BAUDRATE: int = 9600

    # Door open duration in seconds
    DOOR_OPEN_DURATION: int = 5

    # Configuration for loading environment variables from a .env file
    model_config = SettingsConfigDict(env_file=".env")

# Instantiate the settings
settings = Settings()