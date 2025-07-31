from django.db.models.signals import post_migrate
from django.dispatch import receiver
from django.contrib.auth.models import Group, Permission
from django.contrib.admin.models import LogEntry, CHANGE
from django.contrib.contenttypes.models import ContentType
from .models import UserProfile
import logging

logger = logging.getLogger(__name__)

@receiver(post_migrate)
def create_groups_and_permissions(sender, **kwargs):
    if sender.name != 'website':
        return

    # Create groups
    management_group, _ = Group.objects.get_or_create(name='Management')
    Group.objects.get_or_create(name='Clients')

    # Create cache table for DatabaseCache
    from django.core.cache import cache
    cache.get('test_cache')  # Trigger cache table creation if needed

    # Create and assign can_change_profile_type permission
    try:
        content_type = ContentType.objects.get(app_label='website', model='userprofile')
        can_change_profile_type, created = Permission.objects.get_or_create(
            codename='can_change_profile_type',
            name='Can change profile type',
            content_type=content_type
        )
        management_group.permissions.add(can_change_profile_type)
        logger.info(f"{'Created' if created else 'Assigned'} 'can_change_profile_type' permission to Management group")
    except ContentType.DoesNotExist as e:
        logger.warning(f"Could not assign 'can_change_profile_type' permission: ContentType does not exist: {e}")
    except Exception as e:
        logger.error(f"Unexpected error in create_groups_and_permissions: {e}")