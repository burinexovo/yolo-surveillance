from utils.logging import setup_logging
import logging

setup_logging(
    level=logging.DEBUG,
    # log_file="logs/app.log",
)

logger = logging.getLogger(__name__)

logger.debug("System debug")
logger.info("System info")
logger.warning("System warning")
logger.error("System error")
logger.critical("System critical")
MAX_DISAPPEAR = 5
leaves = {1, 2, 3}
logger.debug("no detections, leaves after disappea > %d: %s", MAX_DISAPPEAR, leaves)
