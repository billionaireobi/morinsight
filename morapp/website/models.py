from django.db import models
from django.contrib.auth.models import User, Group
from django.db.models.signals import post_save
from django.dispatch import receiver

class UserProfile(models.Model):
    PROFILE_TYPE_CHOICES = [
        ('Management', 'Management'),
        ('Client', 'Client'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    date_modified = models.DateTimeField(auto_now=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    profile_type = models.CharField(max_length=50, choices=PROFILE_TYPE_CHOICES, blank=True, null=True)
    join_date = models.DateField(blank=True, null=True)
    gender = models.CharField(max_length=10, blank=True, null=True)

    def __str__(self):
        return self.user.username

    def is_management(self):
        return self.user.is_superuser or self.user.groups.filter(name='Management').exists()

    def is_client(self):
        return self.user.groups.filter(name='Clients').exists()

    class Meta:
        permissions = [
            ("can_change_profile_type", "Can change profile type field"),
        ]

@receiver(post_save, sender=User)
def create_profile(sender, instance, created, **kwargs):
    if created:
        if instance.is_superuser:
            profile = UserProfile.objects.create(user=instance, profile_type='Management')
            group = Group.objects.get_or_create(name='Management')[0]
            instance.groups.add(group)
        else:
            profile = UserProfile.objects.create(user=instance, profile_type='Client')
            group = Group.objects.get_or_create(name='Clients')[0]
            instance.groups.add(group)