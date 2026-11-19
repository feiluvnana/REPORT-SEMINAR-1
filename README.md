# Seminar 1 (HUST) — Đề tài A1: Dùng AI phát hiện mơ hồ, thiếu sót, mâu thuẫn trong tài liệu đặc tả yêu cầu (SRS)

**Nhóm thực hiện:** Nhóm 4 — Trường Công nghệ Thông tin và Truyền thông (SoICT), Đại học Bách khoa Hà Nội  
**Giảng viên hướng dẫn:** TS. Nguyễn Thanh Hùng (Khoa Khoa học Máy tính)  
**Thành viên:**
- Nguyễn Tùng Dương (20251175M — Nhóm trưởng)
- Trần Xuân Nam (20251177M)
- Phạm Gia Khánh (20252636M)

> **Đọc nhanh:** Để xem toàn bộ cơ sở lý thuyết, phân tích phương pháp, trích dẫn và kết quả học thuật, hãy mở **[Báo cáo đầy đủ (`main.pdf`)](main.pdf)** hoặc **[Slide thuyết trình (`slides/slides.pdf`)](slides/slides.pdf)** ([bản kèm ghi chú](slides/slides-notes.pdf)). Tài liệu `README.md` này hướng dẫn cài đặt, cấu trúc mã nguồn và cách tái lập toàn bộ thực nghiệm từ đầu. Kế hoạch chi tiết và tiến độ được theo dõi tại [`PLAN.md`](PLAN.md).

---

## 1. Mục tiêu nghiên cứu
Nghiên cứu thực nghiệm đánh giá khả năng phát hiện **3 loại khiếm khuyết SRS** (*mơ hồ / ambiguity*, *thiếu sót / incompleteness*, *mâu thuẫn / inconsistency*) của các tác tử AI đối chiếu với chuẩn chuyên gia (**Claude Opus**), trả lời 4 câu hỏi nghiên cứu:
- **RQ1:** Độ chính xác (Precision, Recall / tỷ lệ phát hiện đúng, Miss Rate / tỷ lệ bỏ sót, $F_1$) của các công cụ AI so với chuyên gia và công cụ nền tảng dựa trên luật (`T0`).
- **RQ2:** Tác động của tệp kỹ năng [`SKILL.md`](skill/req-defect-detector/SKILL.md) (bảng phân loại 15 tiểu loại + checklist + schema) so với câu lệnh thuần (*plain prompt*).
- **RQ3:** Loại khiếm khuyết nào khó phát hiện nhất đối với công cụ AI.
- **RQ4:** Độ ổn định của kết quả qua 3 lượt chạy lặp lại (Jaccard và Fleiss' $\kappa$).

---

## 2. Cấu trúc thư mục (tại gốc repository)

```text
.
├── PLAN.md                              # Kế hoạch chi tiết & nhật ký tiến độ
├── README.md                            # Tài liệu hướng dẫn tiếng Việt (tệp này)
├── meta.tex                             # Thông tin nhóm, giảng viên, học kỳ (dùng chung)
├── data/
│   ├── raw/pure_xml/                    # Dữ liệu XML gốc từ PURE (Zenodo 1414117)
│   ├── keepass.json                     # 32 yêu cầu (KP-001..KP-032)
│   ├── peering.json                     # 24 yêu cầu (PE-001..PE-024)
│   ├── gammaj.json                      # 51 yêu cầu (GJ-001..GJ-051)
│   └── seeded_lms.json                  # 40 yêu cầu LMS có cấy lỗi (SD-001..SD-040)
├── skill/req-defect-detector/SKILL.md   # Kỹ năng phát hiện lỗi theo ISO 29148 & Berry et al.
├── prompts/
│   ├── plain_prompt.txt                 # Câu lệnh thuần (cùng schema & quy tắc chuẩn hóa)
│   └── skill_prompt.txt                 # Câu lệnh kích hoạt kỹ năng SKILL.md
├── ground_truth/
│   ├── seed_key.json                    # Đáp án chuẩn 30 lỗi cấy của seeded_lms
│   ├── expert_pass1.json                # Chuẩn chuyên gia Claude Opus lượt 1 (chờ chạy)
│   ├── expert_pass2.json                # Chuẩn chuyên gia Claude Opus lượt 2 (chờ chạy)
│   ├── final_gt.json                    # Chuẩn sau phân xử (chờ chạy)
│   ├── adjudication_log.md              # Nhật ký phân xử bất đồng (chờ chạy)
│   └── HASHES.txt                       # Mã băm SHA-256 đóng băng trước Phase 4
├── runs/<tool>/<doc>/run_<k>.json       # Kết quả chạy T0 (đã xong) và T1-T4 (chờ Phase 4)
├── eval/
│   ├── prepare_data.py                  # Trích xuất PURE XML -> JSON chuẩn hóa
│   ├── seed_defects.py                  # Sinh seeded_lms.json + seed_key.json
│   ├── baseline_rules.py                # Công cụ nền tảng T0 (Smella/QuARS-style)
│   ├── check_gt.py                      # Tính Cohen's kappa, Recall cấy lỗi & đóng băng SHA-256
│   ├── parse_tool_output.py             # Tách JSON từ đầu ra CLI & kiểm tra schema
│   ├── run_tools.sh                     # Chạy T1-T4 x 4 tài liệu x 3 lượt (cô lập, có retry)
│   ├── evaluate.py                      # Tính độ đo, Bootstrap CI, bảng LaTeX & 5 biểu đồ
│   ├── check_consistency.py             # Kiểm tra nhất quán tệp TeX, PDF, số liệu & git
│   └── results/                         # metrics.csv, tables/*.tex, error_samples.json
├── pic/                                 # Logo HUST & các biểu đồ PNG
├── main.tex -> main.pdf                 # Báo cáo đầy đủ bằng tiếng Việt (XeLaTeX)
└── slides/
    ├── beamerthemeHUST.sty              # Giao diện Beamer màu đỏ HUST
    ├── hust_logo.png                    # Logo HUST
    ├── slides.tex -> slides.pdf         # Slide thuyết trình
    └── slides-notes.tex -> slides-notes.pdf  # Slide kèm ghi chú người nói
```

---

## 3. Cài đặt môi trường từ bản clone mới

Mọi lệnh dưới đây chạy từ **thư mục gốc của repository** (`.`):

### Yêu cầu tiên quyết
- **Python 3.12** + **`uv`** (tạo `.venv` cục bộ vì thư mục `.venv/` không được lưu trong Git). *Lưu ý trên macOS dùng Homebrew Python 3.15: tránh dùng Python 3.15 hệ thống do lỗi `pyexpat`; luôn dùng `.venv/bin/python`.*
- **TeX Live / XeLaTeX (`latexmk -xelatex`)** để biên dịch `main.tex` và `slides/*.tex`.
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
   .venv/bin/python eval/prepare_data.py
   .venv/bin/python eval/seed_defects.py
   ```
2. **Chạy công cụ nền tảng dựa trên luật (`T0`):**
   ```bash
   .venv/bin/python eval/baseline_rules.py
   ```
3. **Kiểm tra chuẩn chuyên gia & đóng băng SHA-256** *(sau khi có `expert_pass1.json`, `expert_pass2.json`, `final_gt.json` từ Claude Opus)*:
   ```bash
   .venv/bin/python eval/check_gt.py --analyze
   .venv/bin/python eval/check_gt.py --freeze
   ```
4. **Chạy các cấu hình LLM (`T1`–`T4`: Gemini 4 Hydrogen & Gemini 4 Neon) và tính độ đo, bảng, biểu đồ:**
   ```bash
   bash eval/run_tools.sh
   .venv/bin/python eval/evaluate.py
   ```
   *(Có thể tự kiểm tra logic khớp và độ ổn định của script đánh giá bất kỳ lúc nào bằng `.venv/bin/python eval/evaluate.py --self-test`.)*
5. **Biên dịch báo cáo và slide (XeLaTeX):**
   ```bash
   latexmk -xelatex main.tex
   (cd slides && latexmk -xelatex slides.tex && latexmk -xelatex slides-notes.tex)
   ```
6. **Kiểm tra nhất quán cuối cùng (Step 15):**
   ```bash
   .venv/bin/python eval/check_consistency.py          # sau khi có đầy đủ kết quả Phase 3-6
   .venv/bin/python eval/check_consistency.py --pre-freeze  # kiểm tra khung TeX, PDF & git
   ```

---

## 5. Trước khi trình bày: kiểm tra, rà soát, nắm vững

### 5.1. Cần kiểm tra (bắt buộc)
| # | Việc cần làm | Cách làm | Phụ trách |
|---|---|---|---|
| 1 | **Đối chiếu chuẩn với người** | Một thành viên tự gắn nhãn khoảng 20 yêu cầu PURE mà không xem chuẩn (Claude chuẩn bị mẫu và phiếu trống). Claude tính κ giữa người và chuẩn, rồi đưa kết quả vào báo cáo §5.1 và slide. Việc này trả lời câu hỏi dễ gặp nhất: "chuyên gia là AI chứ không phải người" | Khánh |
| 2 | **Quyết định phân xử** | Đọc 16 dòng trong `ground_truth/adjudication_log.md`, đánh dấu quyết định nào không đồng ý. Nếu sửa: báo Claude để đóng băng lại và chạy lại đánh giá | Dương |
| 3 | **Tài liệu tham khảo** | Kiểm tra tác giả, tên bài, nơi công bố, năm và DOI của 10 tài liệu trong báo cáo. Kém chắc chắn nhất: Fabbrini 2001, Fabbrini 2005, Lubos 2024, Ronanki 2025, Berry 2003 | Nam |
| 4 | **Số liệu khớp nhau** | Dò thủ công khoảng 5 con số giữa `main.pdf`, `slides.pdf` và `eval/results/metrics.csv` | Dương |
| 5 | **Yêu cầu của giảng viên** | Đối chiếu định dạng, số trang, trang bìa, các mục bắt buộc, hình thức và hạn nộp với yêu cầu của TS. Nguyễn Thanh Hùng | Dương |

### 5.2. Cần rà soát
| # | Việc cần làm | Phụ trách |
|---|---|---|
| 1 | Đọc `main.pdf` và slide: câu thiếu tự nhiên, thuật ngữ không thống nhất ("khiếm khuyết" và "lỗi", "mơ hồ" và "nhập nhằng"), lỗi dấu | Cả nhóm |
| 2 | Đọc khoảng 5 ví dụ trong `eval/results/error_analysis.md`: cách phân loại có công bằng không ("chuyên gia quá khắt khe" hay công cụ thật sự sai)? | Cả nhóm |
| 3 | Xem 2–3 đầu ra gốc trong `runs/T2/*/run_1.json` để biết công cụ thực sự xuất ra gì | Cả nhóm |
| 4 | Biểu đồ trong `pic/` có đọc rõ khi chiếu lên màn hình không (cỡ chữ, màu) | Nam |
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
