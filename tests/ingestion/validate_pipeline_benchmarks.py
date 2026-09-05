# -*- coding: utf-8 -*-
import sys
sys.stdout.reconfigure(encoding="utf-8")
from collections import Counter
import json
import os
import time

sys.path.insert(0, os.path.abspath("."))

from backend.ingestion.bbox import validate_bbox
from backend.ingestion.pipeline import DocumentIngestionPipeline

def run_benchmarks():
    pipeline = DocumentIngestionPipeline()

    print("================================================================================")
    print("                      SIH DATASET INGESTION VALIDATION                          ")
    print("================================================================================")

    bids_dir = "data/raw/SIH26100_Dataset_v1_COMPLETE/sih26100_dataset_v1/documents/bids"
    tenders_dir = "data/raw/SIH26100_Dataset_v1_COMPLETE/sih26100_dataset_v1/documents/tenders"

    # Select representative sample: 50 bids + 10 tenders (including normal, anomalous, multi-page)
    sample_bids = [os.path.join(bids_dir, f"BID-{i:05d}.pdf") for i in range(1, 51)]
    sample_tenders = [os.path.join(tenders_dir, f"TENDER-{i:04d}.pdf") for i in range(1, 11)]

    all_sih_files = sample_bids + sample_tenders

    sih_pdf_count = 0
    sih_pages_count = 0
    sih_native_pages = 0
    sih_ocr_pages = 0
    sih_empty_pages = 0
    sih_low_text_pages = 0
    sih_extraction_failures = 0
    sih_bbox_failures = 0
    sih_total_chars = 0
    sih_total_blocks = 0

    t0 = time.perf_counter()

    for pdf_path in all_sih_files:
        if not os.path.exists(pdf_path):
            continue
        sih_pdf_count += 1
        res = pipeline.ingest_file(pdf_path)

        if res.overall_method.value == "FAILED":
            sih_extraction_failures += 1
            continue

        for p in res.pages:
            sih_pages_count += 1
            if p.extraction_method.value == "NATIVE_PDF":
                sih_native_pages += 1
            elif p.extraction_method.value == "OCR":
                sih_ocr_pages += 1

            if p.is_empty:
                sih_empty_pages += 1
            if p.is_low_text:
                sih_low_text_pages += 1

            sih_total_chars += len(p.text)
            sih_total_blocks += len(p.blocks)

            # Validate each block bounding box
            for b in p.blocks:
                valid, msg = validate_bbox(b.bbox, p.width, p.height)
                if not valid:
                    sih_bbox_failures += 1

    t1 = time.perf_counter()
    sih_elapsed = t1 - t0

    avg_chars_page = sih_total_chars / sih_pages_count if sih_pages_count > 0 else 0
    avg_blocks_page = sih_total_blocks / sih_pages_count if sih_pages_count > 0 else 0
    sec_per_pdf = sih_elapsed / sih_pdf_count if sih_pdf_count > 0 else 0
    sec_per_page = sih_elapsed / sih_pages_count if sih_pages_count > 0 else 0

    print(f"Total PDFs Processed             : {sih_pdf_count}")
    print(f"Total Pages Processed            : {sih_pages_count}")
    print(f"Successful Native Extraction Pgs : {sih_native_pages} ({(sih_native_pages/sih_pages_count)*100:.1f}%)")
    print(f"OCR Fallback Pages               : {sih_ocr_pages}")
    print(f"Empty Pages Detected             : {sih_empty_pages}")
    print(f"Low-Text Pages Detected          : {sih_low_text_pages}")
    print(f"Extraction Failures              : {sih_extraction_failures}")
    print(f"Bounding Box Validation Failures : {sih_bbox_failures}")
    print(f"Average Characters per Page      : {avg_chars_page:.1f}")
    print(f"Average Text Blocks per Page     : {avg_blocks_page:.1f}")
    print(f"Total Processing Time            : {sih_elapsed:.3f} s")
    print(f"Throughput Rate                  : {sec_per_pdf*1000:.1f} ms/PDF ({sec_per_page*1000:.1f} ms/page)")

    print("\n================================================================================")
    print("                    LAYER 2 REAL-WORLD SANITY VALIDATION                        ")
    print("================================================================================")

    l2_dir = "data/external/layer2/ncaor/documents"
    l2_files = [
        "gem_821_010626.PDF",
        "gem_072_110726.PDF",
        "gem_817_220726.PDF",
        "gem_845_240426.PDF",
        "NIT-NCPOR_PS-DOM-40GT-08.PDF"
    ]

    l2_pdf_count = 0
    l2_pages_count = 0
    l2_methods = Counter()
    l2_failures = 0
    l2_low_text = 0
    l2_bbox_failures = 0
    l2_total_chars = 0

    for l2_name in l2_files:
        l2_path = os.path.join(l2_dir, l2_name)
        if not os.path.exists(l2_path):
            continue
        l2_pdf_count += 1
        res = pipeline.ingest_file(l2_path)

        if res.overall_method.value == "FAILED":
            l2_failures += 1
            continue

        l2_methods[res.overall_method.value] += 1
        for p in res.pages:
            l2_pages_count += 1
            if p.is_low_text:
                l2_low_text += 1
            l2_total_chars += len(p.text)
            for b in p.blocks:
                valid, _ = validate_bbox(b.bbox, p.width, p.height)
                if not valid:
                    l2_bbox_failures += 1

    print(f"Layer 2 PDFs Processed           : {l2_pdf_count}")
    print(f"Layer 2 Pages Processed          : {l2_pages_count}")
    print(f"Extraction Method Distribution   : {dict(l2_methods)}")
    print(f"Layer 2 Extraction Failures      : {l2_failures}")
    print(f"Layer 2 Low-Text Pages           : {l2_low_text}")
    print(f"Layer 2 Bbox Validity Failures   : {l2_bbox_failures}")
    print(f"Layer 2 Total Characters         : {l2_total_chars}")

    print("\n================================================================================")
    print("                    DETERMINISM VERIFICATION (3 RUNS)                           ")
    print("================================================================================")

    test_pdf = sample_bids[0]
    runs = []
    for r in range(3):
        res = pipeline.ingest_file(test_pdf)
        dump = json.dumps(res.to_dict(), sort_keys=True)
        runs.append(dump)
        print(f"Run #{r+1}: Extracted {len(res.pages)} pages, {res.total_blocks} blocks, {len(dump)} bytes serialized")

    is_det = (runs[0] == runs[1] == runs[2])
    print(f"Determinism Check (Run 1 == Run 2 == Run 3): {is_det}")
    assert is_det, "Pipeline is not deterministic across repeated runs!"

if __name__ == "__main__":
    run_benchmarks()
