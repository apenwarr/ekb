from django.db import models

class Tag(models.Model):
    name = models.CharField(max_length=200, db_index=True, unique=True)
    
class Doc(models.Model):
    filename = models.CharField(max_length=200, db_index=True, unique=True)
    title = models.CharField(max_length=200, db_index=True, unique=True)
    last_modified = models.DateTimeField()
    tags = models.ManyToManyField(Tag)
    text = models.TextField()

    def get_url(self):
	return "/kb/%d/%s" % (self.id, self.filename)
