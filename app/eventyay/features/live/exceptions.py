from eventyay.base.operational_logging import OUTCOME_FAILURE, is_safe_identifier, log_event


class ConsumerException(Exception):
    def __init__(self, code, message=None):
        self.code = code
        self.message = message
        if code in ('protocol.unauthenticated', 'protocol.unknown_command', 'event.unknown_event'):
            return
        log_event('video', 'live.command', OUTCOME_FAILURE, error_code=code if is_safe_identifier(code) else 'consumer_error')
