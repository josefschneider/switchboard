
import logging
import logging.config

DEFAULT_LOG_SETTINGS = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'simple': {
            'format': '%(asctime)s [%(levelname)s] (%(name)s) %(message)s'
        }
    },
    'handlers': {
        'file': {
            'class':'logging.handlers.RotatingFileHandler',
            'level': 'INFO',
            'formatter': 'simple',
            'filename': 'swb.log',
            'maxBytes': 10485760,
            'backupCount': 3,
            'encoding': 'utf8'
        },
        'stdout': {
            'class':'logging.StreamHandler',
            'level': 'DEBUG',
            'formatter': 'simple'
        }
    },
    'loggers': {
        '': {
            'handlers': ['file', 'stdout'],
            'level': 'DEBUG',
            'propagate': True
        }
    }
}

logger = logging.getLogger(__name__)

def set_log_config(log_settings):
    logging.config.dictConfig(log_settings)
    logger.info('Logging initialised')

def init_logging(swb_config):
    if not swb_config.get('logging'):
        set_log_config(DEFAULT_LOG_SETTINGS)
        swb_config.set('logging', DEFAULT_LOG_SETTINGS)
    else:
        set_log_config(swb_config.get('logging'))
