default:
	@echo "Try: make load"
	@echo "     make run"

load:
	./manage.py syncdb
	ekb/load docs

run: load
	./manage.py runserver 0.0.0.0:8000
