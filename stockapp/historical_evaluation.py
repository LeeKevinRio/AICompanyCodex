"""Strict historical windows shared by descriptive forecasts and trade diagnostics.

The replay engine creates each signal from its raw prefix and only then judges
the exact calendar window. Never pass today's adjusted series as past inputs.
"""
try:
    from .walk_forward import replay
except ImportError:
    from walk_forward import replay


def observations(bars,indicator,calendar,events=()):
    def normalized(prefix):
        result=indicator(prefix)
        return {**result,'score':result.get('score',50)} if result else None
    return replay(bars,normalized,calendar,events,days=max(1,min(365,len(bars)-59)))['reports']


def non_overlapping(rows):
    """Reserve the same scheduled slots even when a slot is excluded or pending."""
    end=''
    for row in rows:
        if row['asOf']<end:continue
        yield row
        end=row.get('endDate') or row['asOf']
