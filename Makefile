all:

clean:
	-rm *~
	$(MAKE) -C src clean
	$(MAKE) -C sql clean
