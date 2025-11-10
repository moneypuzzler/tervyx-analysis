.PHONY: all update ingest validate metrics figures report clean help

# Default target
all: update ingest validate metrics figures report

# Update tervyx submodule to pinned commit
update:
	@echo "=== Updating tervyx submodule ==="
	bash scripts/update_submodule.sh

# Ingest entries into index
ingest:
	@echo "=== Ingesting entries ==="
	python3 scripts/ingest.py \
		--root tervyx/entries \
		--out reports/tables/index.parquet \
		--format parquet

# Validate index
validate:
	@echo "=== Validating index ==="
	python3 scripts/validate_index.py \
		--in reports/tables/index.parquet \
		--schemas tervyx/protocol/schemas \
		--policy tervyx/policy.yaml

# Build metrics
metrics:
	@echo "=== Building metrics ==="
	python3 scripts/build_metrics.py \
		--in reports/tables/index.parquet \
		--out reports/tables/metrics.csv

# Generate figures
figures:
	@echo "=== Generating figures ==="
	python3 scripts/plot_figures.py \
		--in reports/tables \
		--out reports/figures

# Generate report
report:
	@echo "=== Generating report ==="
	python3 scripts/make_report.py \
		--metrics reports/tables \
		--figures reports/figures \
		--out reports/summary.md

# Clean generated outputs
clean:
	@echo "=== Cleaning outputs ==="
	rm -rf reports/tables/*.csv reports/tables/*.parquet
	rm -rf reports/figures/*.png reports/figures/*.svg
	rm -f reports/summary.md

# Show help
help:
	@echo "TERVYX Analysis Makefile"
	@echo ""
	@echo "Targets:"
	@echo "  all        - Run full pipeline (update → ingest → validate → metrics → figures → report)"
	@echo "  update     - Update tervyx submodule to pinned commit"
	@echo "  ingest     - Parse entries into index.parquet"
	@echo "  validate   - Validate index quality and policy anchors"
	@echo "  metrics    - Compute TEL-5/gate/J-Oracle statistics"
	@echo "  figures    - Generate visualization charts"
	@echo "  report     - Assemble summary.md report"
	@echo "  clean      - Remove generated outputs"
	@echo "  help       - Show this help message"
