SDIR:=$(strip $(shell dirname $(realpath $(lastword $(MAKEFILE_LIST))))/../api)
ODIR:=$(strip $(shell dirname $(realpath $(lastword $(MAKEFILE_LIST)))))
DIR:=$(strip $(shell dirname $(realpath $(lastword $(MAKEFILE_LIST)))))


all: checkout build

checkout:

build:
	echo $(DIR)
	# docker run --rm -v $(SDIR)/:/api -v $(ODIR):/build dtr.dev.cray.com/cray/create-adoc convert -i /api/openapi.yaml -d /build
	cp $(SDIR)/openapi.yaml $(ODIR)
	docker run -v $(DIR):/docs -v $(ODIR):/build dtr.dev.cray.com/cray/create-html:v1.0.0 --doctype book /docs/index.adoc  -D /build
	docker run -v $(DIR):/docs -v $(ODIR):/build dtr.dev.cray.com/cray/create-pdf:v1.0.0  --doctype book /docs/index.adoc -D /build

clean:
	rm *.pdf *.html overview.adoc security.adoc definitions.adoc paths.adoc
