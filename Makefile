.PHONY: test doctor briefing wrapup lint

test:     ; scripts/dev.sh test
doctor:   ; scripts/dev.sh doctor
briefing: ; scripts/dev.sh briefing
wrapup:   ; scripts/dev.sh wrapup
lint:     ; scripts/dev.sh lint
