
default:
	@echo 'Try: make load'
	@false

load:
	cd .. && DJANGO_SETTINGS_MODULE=settings \
		python -c 'import kb.load; kb.load.load_all("docs")'

clean::
	find -name '*.pyc' -o -name '*~' | xargs rm -fv
