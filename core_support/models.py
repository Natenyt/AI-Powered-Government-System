from django.db import models


class Neighborhood(models.Model):
    """
    Represents a neighborhood/mahalla in the system.
    """
    id = models.BigAutoField(primary_key=True)
    
    name_uz = models.CharField(max_length=128, db_index=True)  # Uzbek name
    name_ru = models.CharField(max_length=128, blank=True, null=True)  # Russian name
    name_en = models.CharField(max_length=128, blank=True, null=True)  # English name
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Neighborhood"
        verbose_name_plural = "Neighborhoods"
        indexes = [
            models.Index(fields=["name_uz"]),
        ]
        ordering = ['name_uz']
    
    def __str__(self):
        return self.name_uz