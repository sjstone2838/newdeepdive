from django.conf.urls import *
from . import views
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
#new line
from django.conf import settings


urlpatterns = patterns('lessons.views',
	(r'^$', 'index'),
	(r'^(?P<lesson_id>\d+)/$', 'lesson'),
	(r'^(?P<lesson_id>\d+)/result/$', 'result'),
	(r'^(?P<lesson_id>\d+)/quiz/$', 'quiz'),
	(r'^/?login/$','validate_user'),
	(r'^/?new_user/$','new_user'),
	(r'^/?profile/$','profile'),
)
#for using bootstrap / static files, 
# per http://www.effectivedjango.com/tutorial/static.html
urlpatterns += staticfiles_urlpatterns()

#new section
if not settings.DEBUG:
    urlpatterns += patterns('',
        (r'^static/(?P<path>.*)$', 'django.contrib.staticfiles.views', {'document_root': settings.STATIC_ROOT}),
    )

