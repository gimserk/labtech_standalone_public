"""Small MicroPython-compatible Cyber City v1 command decoder.

Only set commands are accepted. UTC RTC/NTP must be synchronized before
expiring commands can be safely executed. Does not evaluate Python code.
"""
import time
try:
    import ujson as json
except ImportError:
    import json


class CommandError(ValueError):
    pass


def _valid_uuid(value):
    if not isinstance(value, str) or len(value) != 36:
        return False
    for i, char in enumerate(value.lower()):
        if i in (8, 13, 18, 23):
            if char != '-':
                return False
        elif char not in '0123456789abcdef':
            return False
    return True


def _deadline_epoch(value):
    # Python/Django isoformat of a UTC datetime, plus the Z spelling.
    if not isinstance(value, str) or not (value.endswith('+00:00') or value.endswith('Z')):
        raise CommandError('Only UTC deadlines are supported')
    clock = value[:-6] if value.endswith('+00:00') else value[:-1]
    # ISO8601 seconds, optional fractional seconds.
    clock = clock.split('.')[0]
    try:
        if len(clock) != 19 or clock[10] != 'T':
            raise ValueError('bad date length')
        parts = (int(clock[0:4]), int(clock[5:7]), int(clock[8:10]),
                 int(clock[11:13]), int(clock[14:16]), int(clock[17:19]))
        if clock[4] != '-' or clock[7] != '-' or clock[13] != ':' or clock[16] != ':':
            raise ValueError('bad delimiters')
        if not (2025 <= parts[0] <= 2099 and 1 <= parts[1] <= 12
                and 1 <= parts[2] <= 31 and parts[3] <= 23
                and parts[4] <= 59 and parts[5] <= 59):
            raise ValueError('bad date')
        # CPython expects a 9-field struct_time and time.mktime is local-time.
        # MicroPython expects 8 fields, with the device RTC set to UTC.
        try:
            import calendar
        except ImportError:
            epoch = time.mktime(parts + (0, 0))
        else:
            epoch = calendar.timegm(parts + (0, 0, 0))
        if tuple(time.gmtime(epoch)[:6]) != parts:
            raise ValueError('Invalid UTC calendar date')
        return epoch
    except (ValueError, OverflowError, OSError, TypeError) as exc:
        raise CommandError('Invalid deadline') from exc


def decode_command(payload):
    if not isinstance(payload, (bytes, str)) or len(payload) > 512:
        raise CommandError('Invalid command size')
    try:
        data = json.loads(payload)
    except (ValueError, TypeError) as exc:
        raise CommandError('Malformed command JSON') from exc
    if not isinstance(data, dict) or type(data.get('schema')) is not int or data['schema'] != 1:
        raise CommandError('Unsupported command schema')
    ident = data.get('command_id')
    if not _valid_uuid(ident):
        raise CommandError('Invalid command identifier')
    if data.get('action') != 'set':
        raise CommandError('Unsupported command action')
    value = data.get('value')
    if type(value) not in (str, int, bool) or (isinstance(value, str) and len(value) > 128):
        raise CommandError('Invalid command value')
    if time.localtime()[0] < 2025:
        raise CommandError('RTC not synchronized')
    if _deadline_epoch(data.get('expires_at')) <= time.time():
        raise CommandError('Command expired')
    return ident, str(int(value)) if isinstance(value, bool) else str(value)
