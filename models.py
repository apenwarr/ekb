from django.db import models

class Tag(models.Model):
    name = models.CharField(max_length=200, db_index=True, unique=True)

class Word(models.Model):
    name = models.CharField(max_length=40, db_index=True, unique=True)
    total = models.IntegerField()

class Doc(models.Model):
    filename = models.CharField(max_length=200, db_index=True, unique=True)
    title = models.CharField(max_length=200, db_index=True, unique=True)
    last_modified = models.DateTimeField()
    tags = models.ManyToManyField(Tag)
    related = models.ManyToManyField('self', through='RelatedWeight',
				     symmetrical=False)
    words = models.ManyToManyField(Word, through='WordWeight')
    text = models.TextField()

    def get_url(self):
	return "/kb/%d/%s" % (self.id, self.filename)

class WordWeight(models.Model):
    word = models.ForeignKey(Word)
    doc = models.ForeignKey(Doc)
    weight = models.FloatField()

class RelatedWeight(models.Model):
    parent = models.ForeignKey(Doc, related_name = 'related_to')
    doc = models.ForeignKey(Doc, related_name = 'related_from')
    weight = models.FloatField()
