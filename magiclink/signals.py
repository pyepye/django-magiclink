from django.dispatch import Signal

magiclink_requested = Signal()
magiclink_sent = Signal()
login_succeeded = Signal()
login_failed = Signal()
spam_detected = Signal()
