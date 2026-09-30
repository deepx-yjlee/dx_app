# sudo authorization needed

####################
# [DRI] DevOps
WORKDIR := /root/workdir
####################

###### INPUT #######
# Interface with test framework
# If value of interface is not allowed, then identify exit code and raise an error like '@exit $(.SHELLSTATUS)'.
ARCH = x86_64
DEMO = ic
TARGET = ASIC

####################
# [DRI] RT
.PHONY: install_opencv check_arch build target check_demo run

SUPPORTED_CPU_ARCH := x86_64 aarch64 # value table : CPU ARCHITECTURE which needs to be tested on dxnn ci
SUPPORTED_TARGET := ASIC # value table : HW Boards which needs to be tested on dxnn ci
SAMPLE_DEMO := ic od

MODULE_RT := dx_rt
DIRECTORY_RT = /usr/local


# install opencv dependent with dx_app/extern
install_all: check_arch
	@echo ">> install all"
	cd .. && ./install.sh --all --arch $(ARCH)

# build dx_app
build: check_arch
	@echo ">> start build"
	cd .. && ./build.sh --clean --arch $(ARCH)

check_arch:
	@echo ">> check CPU architecture supported"
ifneq ($(filter $(ARCH),$(SUPPORTED_CPU_ARCH)),)
	@echo "$(ARCH) supported from $(SUPPORTED_CPU_ARCH)"
else
	@echo "ARCH $(ARCH) is not supported! Supported CPUs are $(SUPPORTED_CPU_ARCH)."
# when input error,
	$(shell exit 100)
	@exit $(.SHELLSTATUS)
endif

library_ldconfig: 
	@echo ">> update system's library cache"
	ldconfig

# execute dx_app application
run: target check_demo library_ldconfig
	@echo ">> execute $(DEMO)"
ifeq ($(DEMO), ic)
	cd .. && ./bin/run_classifier -c example/run_classifier/imagenet_example.json
else ifeq ($(DEMO), od)
	timeout 2s bash -c 'cd .. && ./bin/run_detector -c example/run_detector/yolov5s3_example.json' || exit 1
endif

target:
	@echo ">> check target - $(TARGET)"
ifeq ($(filter $(TARGET),$(SUPPORTED_TARGET)),)
	@echo "invalid type"
	@exit 1
else
	@echo "valid type from '$(SUPPORTED_TARGET)'"
endif

check_demo:
	@echo ">> check application available"
ifneq ($(filter $(DEMO),$(SAMPLE_DEMO)),)
	@echo "$(DEMO) available"
else
	@echo "Application $(DEMO) is not available! Sample demo applications are $(SAMPLE_DEMO)"
	$(shell exit 100)
	@exit $(.SHELLSTATUS)
endif

####################
