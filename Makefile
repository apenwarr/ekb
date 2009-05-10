
default:
	@echo 'Try: make clean'
	@false

clean::
	find -name '*.pyc' -o -name '*~' | xargs rm -fv
	rm -f example/example.db
