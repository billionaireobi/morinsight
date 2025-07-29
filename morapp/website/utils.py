from django.core.cache import cache
from rest_framework import status
from rest_framework.response import Response
from functools import wraps
import time

def rate_limit(key='ip', rate='10/h'):
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(self, request, *args, **kwargs):
            # Validate rate format
            if not rate or '/' not in rate:
                print(f"Invalid rate format for view {self.__class__.__name__}: rate={rate}")
                return view_func(self, request, *args, **kwargs)  # Bypass rate-limiting if invalid

            try:
                count, duration = rate.split('/')
                count = int(count)
                if not duration:
                    print(f"Invalid duration for view {self.__class__.__name__}: duration={duration}")
                    return view_func(self, request, *args, **kwargs)  # Bypass if duration is empty

                # Parse duration (e.g., 'h' or '1h')
                period = {'s': 1, 'm': 60, 'h': 3600, 'd': 86400}
                if duration in period:
                    duration_value = 1  # Implicit 1 for 'h', 'm', etc.
                    duration_unit = duration
                else:
                    duration_value = int(duration[:-1])  # Extract number (e.g., '1' from '1h')
                    duration_unit = duration[-1]  # Extract unit (e.g., 'h')
                
                if duration_unit not in period or duration_value <= 0:
                    print(f"Invalid duration unit for view {self.__class__.__name__}: unit={duration_unit}")
                    return view_func(self, request, *args, **kwargs)  # Bypass if invalid unit

                duration_seconds = duration_value * period[duration_unit]
            except (ValueError, KeyError) as e:
                print(f"Rate limit parsing error for view {self.__class__.__name__}: {e}")
                return view_func(self, request, *args, **kwargs)  # Bypass on parsing errors

            # Generate cache key
            if key == 'ip':
                identifier = request.META.get('REMOTE_ADDR', 'unknown')
            else:
                identifier = 'global'

            cache_key = f"rate_limit:{key}:{identifier}:{self.__class__.__name__}"
            current_count = cache.get(cache_key, 0)
            print(f"Rate limit check: key={cache_key}, count={current_count}, max={count}, view={self.__class__.__name__}")  # Debug

            if current_count >= count:
                print(f"Rate limit exceeded: key={cache_key}, view={self.__class__.__name__}")
                return Response(
                    {"error": "Rate limit exceeded. Try again later."},
                    status=status.HTTP_429_TOO_MANY_REQUESTS
                )

            # Increment count and set expiry
            cache.set(cache_key, current_count + 1, timeout=duration_seconds)
            print(f"Rate limit updated: key={cache_key}, new_count={current_count + 1}, view={self.__class__.__name__}")
            return view_func(self, request, *args, **kwargs)
        return _wrapped_view
    return decorator