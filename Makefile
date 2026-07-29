default:
	flask --app app run --host=0.0.0.0 --port=30808

repomix:
	repomix --include "app.py,templates/**" -o video_organizer.xml

build:
	docker build -f Dockerfile.local -t re0.3facfe.com/video_organizer .
	docker push re0.3facfe.com/video_organizer
