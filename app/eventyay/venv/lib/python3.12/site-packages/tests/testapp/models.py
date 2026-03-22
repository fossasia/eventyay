from django.db import models

from django_scopes import ScopedManager


class PostManager(models.Manager):

    def get_queryset(self):
        return super().get_queryset().exclude(title='deleted')


class Site(models.Model):
    name = models.CharField(max_length=200)

    def __str__(self):
        return str(self.name)


class Post(models.Model):
    site = models.ForeignKey(Site, on_delete=models.CASCADE)
    title = models.CharField(max_length=200)

    objects = ScopedManager(site='site', _manager_class=PostManager)


class Comment(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE)
    text = models.TextField()

    objects = ScopedManager(site='post__site')


class Bookmark(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE)
    userid = models.IntegerField()

    objects = ScopedManager(site='post__site', user_id='userid')


class CommentGroup(models.Model):
    """ Contrived many-to-many example """
    site = models.ForeignKey(Site, on_delete=models.CASCADE)
    comments = models.ManyToManyField(Comment)

    objects = ScopedManager(site='site')
