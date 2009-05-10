from django.db import models

class Thingy(models.Model):
    name = models.CharField(max_length=200)
    puppies = models.IntegerField()
        
