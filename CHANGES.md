## Changes in 0.1.2 (in development)

* Improve handling of environment file specification (#63)
* Stop running container on SIGINT (#62)
* `xcetool image run --server` prints server and viewer URLs (#46)
* Improve documentation (#54, #55)
* Improve type annotations and checks (#68)
* Include Dockerfile in built images (#55)
* Look for environment.yml automatically (#41)
* Allow `xcengine image run` to pass arguments to the container (#57, #77)
* Add option for `xcengine image run` to open a browser window (#58)
* Add option to skip image build and just create Dockerfile and context (#60)
* Refactor code and improve test coverage (#40, #80)

## Changes in 0.1.1

* Improve automated parameter extraction (#9)
* Handle notebooks without parameters (#11)
* Handle non-code cells (#12)
* Ignore magic commands in input notebooks (#14)
* Add NDVI sample notebook
* Improve STAC output (#19)
* Tweak CWL format (#24)
* Use micromamba entry point in Docker image (#26)
* Allow setting of CWL workflow ID (#29)
* Support in-notebook configuration of workflow ID, environment file,
  and container image tag (#30, #33)
* Support writing of stage-out STAC by notebook (#32)
* Make viewer work on non-default ports (#21)
* Improve dynamic example notebook
* Support NetCDF output (#28)
* Improve documentation (#22)
* Make extracted parameter order deterministic (#37)
* Improve unit test coverage (#5)

## Changes in 0.1.0

* Initial release
