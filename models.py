from django.db import models

class Doc(models.Model):
    title = models.CharField(max_length=200, db_index=True, unique=True)
    last_modified = models.DateTimeField()
    text = models.TextField()

class Tag(models.Model):
    name = models.CharField(max_length=200, db_index=True)
    doc = models.ForeignKey(Doc, db_index=True)
