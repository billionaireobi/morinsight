from django.core.cache import cache
from rest_framework import status
from rest_framework.response import Response
from functools import wraps
import logging

logger = logging.getLogger(__name__)

def rate_limit(key='ip', rate='10/h'):
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(self, request, *args, **kwargs):
            view_name = self.__class__.__name__
            try:
                if not rate or '/' not in rate:
                    logger.warning(f"Invalid rate format for view {view_name}: rate={rate}")
                    return view_func(self, request, *args, **kwargs)

                count, duration = rate.split('/')
                count = int(count)
                if not duration:
                    logger.warning(f"Invalid duration for view {view_name}: duration={duration}")
                    return view_func(self, request, *args, **kwargs)

                period = {'s': 1, 'm': 60, 'h': 3600, 'd': 86400}
                if duration in period:
                    duration_value = 1
                    duration_unit = duration
                else:
                    duration_value = int(duration[:-1])
                    duration_unit = duration[-1]

                if duration_unit not in period or duration_value <= 0:
                    logger.warning(f"Invalid duration unit for view {view_name}: unit={duration_unit}")
                    return view_func(self, request, *args, **kwargs)

                duration_seconds = duration_value * period[duration_unit]

                identifier = request.META.get('REMOTE_ADDR', 'unknown') if key == 'ip' else 'global'
                cache_key = f"rate_limit:{key}:{identifier}:{view_name}"
                current_count = cache.get(cache_key, 0)
                logger.debug(f"Rate limit check: key={cache_key}, count={current_count}, max={count}")

                if current_count >= count:
                    logger.warning(f"Rate limit exceeded: key={cache_key}, view={view_name}")
                    return Response(
                        {"error": "Rate limit exceeded. Try again later."},
                        status=status.HTTP_429_TOO_MANY_REQUESTS
                    )

                cache.set(cache_key, current_count + 1, timeout=duration_seconds)
                logger.debug(f"Rate limit updated: key={cache_key}, new_count={current_count + 1}")
                return view_func(self, request, *args, **kwargs)
            except Exception as e:
                logger.error(f"Rate limit error in view {view_name}: {str(e)}")
                return view_func(self, request, *args, **kwargs)
        return _wrapped_view
    return decorator