from django.db.models.signals import post_migrate, post_save
from django.dispatch import receiver
from django.contrib.auth.models import User, Group, Permission
from django.contrib.admin.models import LogEntry, CHANGE
from django.contrib.contenttypes.models import ContentType
from .models import UserProfile

@receiver(post_migrate)
def create_groups_and_permissions(sender, **kwargs):
    # Only run for the 'website' app
    if sender.name != 'website':
        return

    # Create groups
    management_group, _ = Group.objects.get_or_create(name='Management')
    Group.objects.get_or_create(name='Clients')

    # Assign can_change_profile_type permission to Management
    try:
        content_type = ContentType.objects.get(app_label='website', model='userprofile')
        can_change_profile_type = Permission.objects.get(
            codename='can_change_profile_type',
            content_type=content_type
        )
        management_group.permissions.add(can_change_profile_type)
        print("Assigned 'can_change_profile_type' permission to Management group")
    except (ContentType.DoesNotExist, Permission.DoesNotExist) as e:
        print(f"Warning: Could not assign 'can_change_profile_type' permission: {e}")

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance, profile_type='Client')
        group = Group.objects.get_or_create(name='Clients')[0]
        instance.groups.add(group)

@receiver(post_save, sender=UserProfile)
def log_profile_type_change(sender, instance, **kwargs):
    if hasattr(instance, '_original_profile_type') and instance.profile_type != instance._original_profile_type:
        try:
            LogEntry.objects.create(
                user_id=instance.user.id,
                content_type_id=ContentType.objects.get_for_model(instance).id,
                object_id=instance.pk,
                object_repr=str(instance),
                action_flag=CHANGE,
                change_message=f"Profile type changed from {instance._original_profile_type} to {instance.profile_type}"
            )
        except Exception as e:
            print(f"Error logging profile type change: {e}")

@receiver(post_save, sender=UserProfile)
def set_original_profile_type(sender, instance, **kwargs):
    instance._original_profile_type = instance.profile_type