from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError

# Create your models here.
class Movie(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=255)
    price = models.IntegerField()
    description = models.TextField()
    image = models.ImageField(upload_to='movie_images/')
    amount_left = models.PositiveIntegerField(
        null=True, blank=True,
        help_text="Optional inventory. Leave blank for unlimited."
    )
    
    def __str__(self):
        return str(self.id) + ' - ' + self.name
    
    @property
    def is_available(self):
        # Unlimited if blank; otherwise > 0
        return self.amount_left is None or self.amount_left > 0

    def clean(self):
        """
        Once amount_left hits 0, prevent editing it (lock it at 0).
        Admin can set/update at any time *while* amount_left > 0.
        """
        if self.pk:
            old = type(self).objects.only('amount_left').get(pk=self.pk)
            if old.amount_left == 0 and self.amount_left != 0:
                raise ValidationError(
                    {"amount_left": "This value is locked because inventory is 0."}
                )
        super().clean()
    
class Review(models.Model):
    id = models.AutoField(primary_key=True)
    comment = models.CharField(max_length=255)
    date = models.DateTimeField(auto_now_add=True)
    movie = models.ForeignKey(Movie,
        on_delete=models.CASCADE)
    user = models.ForeignKey(User,
        on_delete=models.CASCADE)
    def __str__(self):
        return str(self.id) + ' - ' + self.movie.name