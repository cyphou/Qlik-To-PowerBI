"""Main entry point for Fabric artifact deployment."""
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from fabric_api import FabricDeployer, FabricClient, FabricAuthenticator
from fabric_api.config.settings import get_settings
from logging.config import dictConfig

logger = logging.getLogger(__name__)


def _setup_logging():
    """Configure logging from settings."""
    settings = get_settings()
    log_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "standard": {
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            },
            "json": {
                "format": '{"timestamp": "%(asctime)s", "level": "%(levelname)s", '
                '"logger": "%(name)s", "message": "%(message)s"}'
            },
        },
        "handlers": {
            "default": {
                "level": settings.log_level,
                "class": "logging.StreamHandler",
                "formatter": settings.log_format,
                "stream": "ext://sys.stdout",
            },
            "file": {
                "level": settings.log_level,
                "class": "logging.FileHandler",
                "formatter": "standard",
                "filename": "fabric-deployment.log",
            },
        },
        "loggers": {
            "": {
                "handlers": ["default", "file"],
                "level": settings.log_level,
                "propagate": True,
            }
        },
    }
    dictConfig(log_config)


def main():
    """Deploy Fabric artifacts."""
    _setup_logging()
    settings = get_settings()

    try:
        logger.info("Starting Fabric artifact deployment")

        authenticator = FabricAuthenticator(
            use_managed_identity=settings.use_managed_identity
        )
        client = FabricClient(authenticator)
        deployer = FabricDeployer(client)

        logger.info("Fetching available workspaces")
        workspaces = client.list_workspaces()
        logger.info(f'Found {len(workspaces.get("value", []))} workspace(s)')

        artifacts_dir = Path(__file__).parent.parent / "artifacts"
        if artifacts_dir.exists():
            logger.info(f"Deploying artifacts from: {artifacts_dir}")
            results = deployer.deploy_artifacts_batch(
                workspace_id=settings.fabric_workspace_id,
                artifacts_dir=artifacts_dir,
                overwrite=True,
            )
            for result in results:
                if "error" in result:
                    logger.error(f'Failed: {result["file"]} - {result["error"]}')
                else:
                    logger.info(f'Deployed: {result["file"]}')
        else:
            logger.warning(f"Artifacts directory not found: {artifacts_dir}")

        logger.info("Fabric artifact deployment completed successfully")
        return 0
    except Exception as e:
        logger.error(f"Deployment failed: {str(e)}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
