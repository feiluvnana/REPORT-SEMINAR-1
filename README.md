# Seminar 1 (HUST) — Đề tài A1: Dùng AI phát hiện mơ hồ, thiếu sót, mâu thuẫn trong tài liệu đặc tả yêu cầu (SRS)

**Nhóm thực hiện:** Nhóm 4 — Trường Công nghệ Thông tin và Truyền thông (SoICT), Đại học Bách khoa Hà Nội  
**Giảng viên hướng dẫn:** TS. Nguyễn Thanh Hùng (Khoa Khoa học Máy tính)  
**Thành viên:**
- Nguyễn Tùng Dương (20251175M — Nhóm trưởng)
- Trần Xuân Nam (20251177M)
- Phạm Gia Khánh (20252636M)

> **Đọc nhanh:** Để xem toàn bộ cơ sở lý thuyết, phân tích phương pháp, trích dẫn và kết quả học thuật, hãy mở **[Báo cáo đầy đủ (`report/main.pdf`)](report/main.pdf)** hoặc **[Slide thuyết trình (`slide/slides.pdf`)](slide/slides.pdf)** ([bản kèm ghi chú](slide/slides-notes.pdf)). Tài liệu `README.md` này hướng dẫn cài đặt, cấu trúc mã nguồn và cách tái lập toàn bộ thực nghiệm từ đầu. Kế hoạch chi tiết và tiến độ được theo dõi tại [`PLAN.md`](PLAN.md).

---

## 1. Mục tiêu nghiên cứu
Nghiên cứu thực nghiệm đánh giá khả năng phát hiện **3 loại khiếm khuyết SRS** (*mơ hồ / ambiguity*, *thiếu sót / incompleteness*, *mâu thuẫn / inconsistency*) của các tác tử AI đối chiếu với chuẩn chuyên gia (**Claude Opus**), trả lời 4 câu hỏi nghiên cứu:
- **RQ1:** Độ chính xác (Precision, Recall / tỷ lệ phát hiện đúng, Miss Rate / tỷ lệ bỏ sót, $F_1$) của các công cụ AI so với chuyên gia và công cụ nền tảng dựa trên luật (`T0`).
- **RQ2:** Tác động của tệp kỹ năng [`SKILL.md`](prompt/SKILL.md) (bảng phân loại 15 tiểu loại + checklist + schema) so với câu lệnh thuần (*plain prompt*).
- **RQ3:** Loại khiếm khuyết nào khó phát hiện nhất đối với công cụ AI.
- **RQ4:** Độ ổn định của kết quả qua 3 lượt chạy lặp lại (Jaccard và Fleiss' $\kappa$).

---

## 2. Cấu trúc thư mục (tại gốc repository)

```text
.
├── README.md  PLAN.md          # Hướng dẫn (tệp này) & kế hoạch chi tiết
├── dataset/                    # Đầu vào + đáp án
│   ├── raw/pure_xml/           # XML gốc của PURE (Zenodo 1414117)
│   ├── keepass.json            # 32 yêu cầu (KP-001..KP-032)
│   ├── peering.json            # 24 yêu cầu (PE-001..PE-024)
│   ├── gammaj.json             # 51 yêu cầu (GJ-001..GJ-051)
│   ├── seeded_lms.json         # 40 yêu cầu LMS có cấy lỗi (SD-001..SD-040)
│   ├── ground_truth/           # Chuẩn chuyên gia: expert_pass1/2, final_gt, seed_key,
│   │                           # annotation_guideline, adjudication_log, HASHES.txt (SHA-256)
│   └── human_check/            # Phiếu kiểm tra bởi người: part_a.csv, part_b.csv (xem mục 6)
├── prompt/                     # Mọi thứ công cụ nhận được
│   ├── plain.txt               # Câu lệnh thuần (T1/T3)
│   ├── skill.txt               # Câu lệnh kèm kỹ năng (T2/T4)
│   └── SKILL.md                # Kỹ năng phát hiện lỗi (ISO 29148 & Berry et al.)
├── script/                     # Toàn bộ mã nguồn
│   ├── paths.py                # Khai báo đường dẫn dùng chung
│   ├── prepare_data.py         # PURE XML -> JSON chuẩn hóa
│   ├── seed_defects.py         # Sinh seeded_lms.json + seed_key.json
│   ├── baseline_rules.py       # Công cụ nền tảng T0 (kiểu Smella/QuARS)
│   ├── check_gt.py             # Cohen's kappa, kiểm định cấy lỗi, đóng băng SHA-256
│   ├── run_tools.py / .sh      # Chạy T1-T4 x 4 tài liệu x 3 lượt (cô lập, kiểm toán, thử lại)
│   ├── parse_tool_output.py    # Tách JSON, kiểm toán lời gọi công cụ, kiểm tra schema
│   ├── evaluate.py             # Độ đo, Bootstrap CI, bảng LaTeX & biểu đồ
│   ├── audit_runs.py           # Kiểm toán 48 lượt chạy -> result/run/run_summary.csv
│   ├── extra_analysis.py       # Phân tích bổ sung: PURE theo loại, tác động kỹ năng, độ nhạy
│   ├── make_human_check.py     # Sinh phiếu kiểm tra bởi người (mục 6)
│   ├── score_human_check.py    # Chấm phiếu kiểm tra bởi người
│   └── check_consistency.py    # Kiểm tra nhất quán TeX, PDF, số liệu & git
├── result/                     # Mọi thứ được sinh ra
│   ├── run/<tool>/<doc>/run_<k>.{json,log,meta.json}   # Kết quả T0-T4 + run_status.csv
│   ├── metrics.csv  skill_effects.json  error_samples.json
│   └── tables/                 # Bảng LaTeX dùng trong báo cáo
├── report/                     # main.tex -> main.pdf, meta.tex (dùng chung), figures/ (logo + biểu đồ)
└── slide/                      # slides.tex -> slides.pdf, slides-notes.tex -> slides-notes.pdf,
                                # beamerthemeHUST.sty, logo HUST
```

---

## 3. Cài đặt môi trường từ bản clone mới

Mọi lệnh dưới đây chạy từ **thư mục gốc của repository** (`.`):

### Yêu cầu tiên quyết
- **Python 3.12** + **`uv`** (tạo `.venv` cục bộ vì thư mục `.venv/` không được lưu trong Git). *Lưu ý trên macOS dùng Homebrew Python 3.15: tránh dùng Python 3.15 hệ thống do lỗi `pyexpat`; luôn dùng `.venv/bin/python`.*
- **TeX Live / XeLaTeX (`latexmk -xelatex`)** để biên dịch `report/main.tex` và `slide/*.tex`.
- **Antigravity CLI (`agy`)** đã đăng nhập để chạy `T1`–`T4` (`gemini-4-hydrogen-high` và `gemini-4-neon-high`).

### Tạo môi trường ảo Python
```bash
uv venv .venv --python 3.12
uv pip install --python .venv/bin/python pillow numpy matplotlib
```

---

## 4. Các bước tái lập thực nghiệm

1. **Chuẩn bị dữ liệu PURE và tài liệu cấy lỗi `seeded_lms`:**
   ```bash
   .venv/bin/python script/prepare_data.py
   .venv/bin/python script/seed_defects.py
   ```
2. **Chạy công cụ nền tảng dựa trên luật (`T0`):**
   ```bash
   .venv/bin/python script/baseline_rules.py
   ```
3. **Kiểm tra chuẩn chuyên gia & đóng băng SHA-256** *(sau khi có `expert_pass1.json`, `expert_pass2.json`, `final_gt.json` từ Claude Opus)*:
   ```bash
   .venv/bin/python script/check_gt.py --analyze
   .venv/bin/python script/check_gt.py --freeze
   ```
4. **Chạy các cấu hình LLM (`T1`–`T4`: Gemini 4 Hydrogen & Gemini 4 Neon) và tính độ đo, bảng, biểu đồ:**
   ```bash
   bash script/run_tools.sh
   .venv/bin/python script/evaluate.py
   ```
   *(Có thể tự kiểm tra logic khớp và độ ổn định của script đánh giá bất kỳ lúc nào bằng `.venv/bin/python script/evaluate.py --self-test`.)*
5. **Biên dịch báo cáo và slide (XeLaTeX):**
   ```bash
   (cd report && latexmk -xelatex main.tex)
   (cd slide && latexmk -xelatex slides.tex && latexmk -xelatex slides-notes.tex)
   ```
6. **Kiểm tra nhất quán cuối cùng (Step 15):**
   ```bash
   .venv/bin/python script/check_consistency.py          # sau khi có đầy đủ kết quả Phase 3-6
   .venv/bin/python script/check_consistency.py --pre-freeze  # kiểm tra khung TeX, PDF & git
   ```

---

## 5. Trước khi trình bày: kiểm tra, rà soát, nắm vững

### 5.1. Cần kiểm tra (bắt buộc)
| # | Việc cần làm | Cách làm | Phụ trách |
|---|---|---|---|
| 1 | **Kiểm tra bởi người** | Điền 2 phiếu trong `dataset/human_check/` theo hướng dẫn ở **mục 6**. Việc này trả lời câu hỏi dễ gặp nhất: "chuyên gia là AI chứ không phải người" | Khánh (Phần A), cả nhóm (Phần B) |
| 2 | **Quyết định phân xử** | Đọc 16 dòng trong `dataset/ground_truth/adjudication_log.md`, đánh dấu quyết định nào không đồng ý. Nếu sửa: báo Claude để đóng băng lại và chạy lại đánh giá | Dương |
| 3 | **Tài liệu tham khảo** | Kiểm tra tác giả, tên bài, nơi công bố, năm và DOI của 10 tài liệu trong báo cáo. Kém chắc chắn nhất: Fabbrini 2001, Fabbrini 2005, Lubos 2024, Ronanki 2025, Berry 2003 | Nam |
| 4 | **Số liệu khớp nhau** | Dò thủ công khoảng 5 con số giữa `report/main.pdf`, `slide/slides.pdf` và `result/metrics.csv` | Dương |
| 5 | **Yêu cầu của giảng viên** | Đối chiếu định dạng, số trang, trang bìa, các mục bắt buộc, hình thức và hạn nộp với yêu cầu của TS. Nguyễn Thanh Hùng | Dương |

### 5.2. Cần rà soát
| # | Việc cần làm | Phụ trách |
|---|---|---|
| 1 | Đọc `report/main.pdf` và slide: câu thiếu tự nhiên, thuật ngữ không thống nhất ("khiếm khuyết" và "lỗi", "mơ hồ" và "nhập nhằng"), lỗi dấu | Cả nhóm |
| 2 | Đọc khoảng 5 ví dụ trong `result/error_analysis.md`: cách phân loại có công bằng không ("chuyên gia quá khắt khe" hay công cụ thật sự sai)? | Cả nhóm |
| 3 | Xem 2–3 đầu ra gốc trong `result/run/T2/*/run_1.json` để biết công cụ thực sự xuất ra gì | Cả nhóm |
| 4 | Biểu đồ trong `report/figures/` có đọc rõ khi chiếu lên màn hình không (cỡ chữ, màu) | Nam |
| 5 | Tập dượt khoảng 15 phút theo ghi chú thuyết trình, có bấm giờ; chạy thử demo trên máy trình chiếu và giữ sẵn slide dự phòng | Cả nhóm |

### 5.3. Cần nắm vững (mỗi thành viên giải thích được trong 1–2 câu)
- **Precision, recall (tỷ lệ phát hiện đúng), miss rate (tỷ lệ bỏ sót) và F1**: công thức và ý nghĩa.
- **Cohen's κ và Fleiss' κ**: đo gì, vì sao κ = 0,81 chỉ chứng minh chuyên gia AI *tự nhất quán* chứ không chứng minh *đúng*.
- **Khoảng tin cậy bootstrap 95%** và phép so sánh ghép cặp T2−T1, T4−T3.
- **Quy tắc so khớp:** một phát hiện = (`req_id`, loại lỗi); lỗi mâu thuẫn gắn vào yêu cầu xuất hiện sau.
- **Chống rò rỉ đáp án:** đóng băng SHA-256 trước khi chạy công cụ; giới hạn quyền agy; kiểm toán lời gọi công cụ (T2/T4 bắt buộc đọc `SKILL.md`, cấm web); đã loại các ví dụ lấy từ đáp án ra khỏi `SKILL.md` và T0.
- **Câu trả lời cho các câu hỏi dễ gặp:**

  | Câu hỏi có thể gặp | Trả lời ngắn |
  |---|---|
  | Chuyên gia là AI, không phải người? | 2 lượt độc lập, κ = 0,814, recall 30/30 trên tài liệu cấy lỗi, nhật ký phân xử, đối chiếu với người (mục 5.1, việc 1); đã nêu trong mối đe dọa tính hợp lệ |
  | Chuyên gia và công cụ đều là LLM? | Khác họ mô hình (Claude và Gemini); chuẩn được đóng băng trước khi chạy công cụ |
  | Kỹ năng và chuẩn dùng chung một phân loại? | Cần thiết để so khớp công bằng; một phần lợi ích của kỹ năng có thể đến từ việc khớp quy ước, điều này đã nêu rõ |
  | Dữ liệu nhỏ? | 147 yêu cầu, có khoảng tin cậy bootstrap, ghi nhận là hạn chế |
  | LLM đã thấy PURE khi huấn luyện? | Tài liệu cấy lỗi là mới; đã thảo luận trong báo cáo |
  | Lỗi cấy quá dễ? | Đúng: T0 đạt precision 0,84 trên tài liệu cấy lỗi so với 0,40 trên PURE, nên PURE là thước đo chính |
  | Mô hình có cố định phiên bản không? | Không; đã ghi lại agy 1.5.12, ngày chạy và bí danh mô hình; 3 lượt lặp kèm chỉ số độ ổn định |

---

## 6. Hướng dẫn kiểm tra bởi người (human check)

Nhãn chuẩn do AI (Claude Opus) tạo. Phần kiểm tra này để **người** xác nhận độ tin cậy của nhãn chuẩn và trả lời câu hỏi "các cảnh báo thừa của công cụ là nhiễu hay lỗi thật?". Kết quả được báo cáo **bên cạnh** kết quả chính; nhãn chuẩn đã đóng băng **không bị thay đổi**.

### 6.1. Quy tắc chung
- **Không mở** `dataset/ground_truth/`, `result/` (nhất là `result/human_check_key.json`) và thư mục `result/run/` cho đến khi điền xong cả hai phần.
- **Làm Phần A trước Phần B.** Người làm Phần A không được xem Phần B trước khi xong Phần A.
- Mở tệp `.csv` bằng Excel hoặc Google Sheets. Khi lưu, giữ **định dạng CSV UTF-8**, không đổi tên cột, không thêm hoặc xóa dòng.
- Nếu cần ngữ cảnh, có thể đọc toàn bộ tài liệu gốc trong `dataset/keepass.json`, `dataset/peering.json`, `dataset/gammaj.json`.

### 6.2. Ba loại khiếm khuyết
| Loại | Khi nào gắn nhãn | Ví dụ |
|---|---|---|
| **Mơ hồ** (ambiguity) | Từ ngữ chủ quan, không đo được hoặc có thể hiểu nhiều cách: "nhanh", "dễ dùng", "nếu có thể", đại từ không rõ chỉ ai, "và/hoặc" | "Hệ thống phản hồi *nhanh*" |
| **Thiếu sót** (incompleteness) | Thiếu thông tin cần để triển khai/kiểm thử: TBD, không rõ ai thực hiện, thiếu điều kiện kích hoạt, thiếu xử lý khi lỗi, thiếu giá trị/đơn vị, nêu điều kiện mà không nêu hệ quả | "Khóa tài khoản sau 3 lần sai" (khóa bao lâu?) |
| **Mâu thuẫn** (inconsistency) | Mâu thuẫn hoặc trùng lặp với một yêu cầu **trước đó** trong cùng tài liệu: giá trị khác nhau, quy tắc trái ngược, gọi cùng một đối tượng bằng tên khác, lặp lại gần như y hệt | YC 4: "tối đa 2 kiện" và YC 9: "tối đa 3 kiện" |

**Tiêu chí:** chỉ coi là khiếm khuyết khi một người rà soát cẩn thận **sẽ yêu cầu tác giả sửa**, vì lập trình viên hoặc kiểm thử viên có thể hiểu sai, không kiểm chứng được, hoặc nhận chỉ dẫn mâu thuẫn. Không tính lỗi chính tả/ngữ pháp không đổi nghĩa, và không tính từ ngữ đã được làm rõ bằng con số/chuẩn ngay trong yêu cầu.

### 6.3. Phần A — gắn nhãn độc lập (`dataset/human_check/part_a.csv`, 20 yêu cầu, 1 người, khoảng 30 phút)
Với mỗi yêu cầu, điền **0 hoặc 1** vào **cả ba** cột (không để trống):
- `ambiguity_0_1`, `incompleteness_0_1`, `inconsistency_0_1`: 1 nếu yêu cầu có loại khiếm khuyết đó, 0 nếu không.
- `inconsistency_related_ids`: nếu `inconsistency_0_1 = 1`, ghi mã yêu cầu trước đó bị mâu thuẫn/trùng (ví dụ `PE-007`).
- `note`: ghi chú ngắn nếu phân vân (không bắt buộc).

### 6.4. Phần B — đánh giá trường hợp bất đồng (`dataset/human_check/part_b.csv`, 30 trường hợp, cả nhóm hoặc 1 người, khoảng 30–45 phút)
Mỗi dòng là một **khẳng định** rằng yêu cầu có một khiếm khuyết (loại, tiểu loại, bằng chứng, lý do; với mâu thuẫn có kèm yêu cầu liên quan). Khẳng định có thể đến từ công cụ hoặc từ chuyên gia; **nguồn được ẩn** để đánh giá khách quan.
- `is_real_defect_yes_no_unsure`: điền `yes` (đúng là khiếm khuyết theo tiêu chí 6.2), `no` (không phải), hoặc `unsure` (không quyết định được).
- `note`: lý do ngắn, nhất là khi chọn `no` hoặc `unsure` (ví dụ "chỉ là văn phong", "cần kiến thức miền").
- Nếu làm theo nhóm: thảo luận và điền **một** quyết định thống nhất cho mỗi dòng.

### 6.5. Sau khi điền xong
Báo cho Claude, hoặc tự chạy:
```bash
.venv/bin/python script/score_human_check.py
```
Script báo lỗi nếu còn ô trống hoặc giá trị sai định dạng. Kết quả (κ giữa người và nhãn chuẩn, tỷ lệ cảnh báo thừa được xác nhận là lỗi thật, precision điều chỉnh của từng công cụ) được ghi vào `result/human_check_results.json` và đưa vào báo cáo, slide.

Có thể tạo lại phiếu trống y hệt (seed cố định) bằng `.venv/bin/python script/make_human_check.py`.

