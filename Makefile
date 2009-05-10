
default:
	@echo 'Try: make load'
	@false

load:
	cd .. && DJANGO_SETTINGS_MODULE=settings \
		python -c 'import ekb.load; ekb.load.load_all("docs")'

clean::
	find -name '*.pyc' -o -name '*~' | xargs rm -fv
	rm -f example/example.db
