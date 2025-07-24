from django.db import models

class Report(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    file = models.FileField(upload_to='documents/')
    file_type = models.CharField(max_length=50, blank=True, null=True)
    file_size = models.PositiveIntegerField(blank=True, null=True)

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        # Automatically populate file_type and file_size
        if self.file:
            self.file_type = self.file.file.content_type
            self.file_size = self.file.size
        super().save(*args, **kwargs)

