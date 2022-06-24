all:

clean:
	-rm *~
	$(MAKE) -C sql clean
