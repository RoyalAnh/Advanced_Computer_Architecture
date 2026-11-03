# BÁO CÁO BÀI TẬP LỚN (bản nháp) – Thiết kế máy tính RISC-V RV32I (+M, +Zicsr/ngắt, +F tập con) trên Logisim-evolution

> Bản nháp do Grok Bot soạn. Mọi số liệu trong mục 6 lấy từ các lần chạy mô phỏng thật (xem `Grok_output/tests/logs/`).

## 1. Mục tiêu và phạm vi
- Thiết kế 2 phiên bản CPU RV32I: **đơn chu kỳ** (`RiscV_SingleCycle.circ`) và **pipeline 5 tầng IF→ID→EX→MEM→WB** (`RiscV_Pipeline.circ`).
- Thông số chung: dữ liệu 32 bit, lệnh 32 bit, 32 thanh ghi × 32 bit (x0 luôn bằng 0), PC 32 bit.
- Bộ nhớ lệnh là ROM 1024 word (4 KB). Bộ nhớ dữ liệu là RAM 1024 word (4 KB), đánh địa chỉ theo byte (word = `addr[11:2]`, byte trong word = `addr[1:0]`). Hỗ trợ truy cập byte/half-word bằng LoadUnit/StoreUnit.
- Tập lệnh bắt buộc (24 lệnh):
  - R: ADD SUB AND OR XOR SLT SLTU SLL SRL SRA
  - I: ADDI ANDI ORI XORI SLTI SLTIU SLLI SRLI SRAI
  - Bộ nhớ: LW SW
  - Điều khiển: BEQ BNE JAL JALR
- Đã làm thêm: BLT BGE BLTU BGEU, LUI AUIPC, **LB LH LBU LHU SB SH**, và `ecall` dùng làm lệnh dừng (halt).
- Chương trình được nạp vào instruction memory (ROM `IMEM`) từ file ảnh do assembler `asm.py` tạo ra, không chỉnh trực tiếp thanh ghi.

## 2. Tổng quan kiến trúc và các mô-đun
| Mô-đun (subcircuit) | Vào | Ra | Chức năng |
|---|---|---|---|
| `ALU` | a, b (32), op (4) | y (32) | 0 ADD, 1 SUB, 2 SLL, 3 SLT, 4 SLTU, 5 XOR, 6 SRL, 7 SRA, 8 OR, 9 AND. SLT/SLTU dùng Comparator (có dấu/không dấu) rồi **zero-extend** 1→32 bit. Lượng dịch = b[4:0] |
| `RegFile` | clk, we, rs1, rs2, rd (5), wd (32) | r1, r2 | Decoder 5→32 AND với we tạo enable cho 31 Register. x0 là hằng 0. Đọc bằng 2 MUX 32→1. Ghi ở cạnh lên clock. (Bản trước có thêm cổng x1..x31 để quan sát; nay đã bỏ, test đọc thanh ghi qua đoạn DUMP, xem mục 5) |
| `ImmGen` | instr, sel (3) | imm (32) | Ghép bit và mở rộng dấu cho các dạng I/S/B/U/J (sel 0..4) |
| `BranchUnit` | a, b, f3 | cond | Comparator có dấu và không dấu. f3 chọn BEQ/BNE/BLT/BGE/BLTU/BGEU |
| `LoadUnit` | din (32), off (2), f3 | v (32) | Dịch phải 8·off, rồi mở rộng dấu (LB/LH) hoặc zero (LBU/LHU); LW lấy nguyên word |
| `StoreUnit` | old, wd (32), off, f3 | new (32) | SB/SH/SW: `new = (old & ~mask) \| ((wd << 8·off) & mask)` |
| `Control` | instr | ctrl (20 bit) | **Giải mã bằng ROM** (`CTRL`, 512×20). Địa chỉ = {funct7[5], funct3, opcode[6:2]} |

**Từ điều khiển (20 bit, LSB trước):**

| Bit | Trường |
|---|---|
| 0 | RegWrite |
| 1–2 | ASel (0 = rs1, 1 = PC, 2 = 0) |
| 3 | BSel (0 = rs2, 1 = imm) |
| 4–7 | ALUOp |
| 8 | MemRead |
| 9 | MemWrite |
| 10 | ResPC4 (kết quả = PC+4 cho JAL/JALR) |
| 11–13 | ImmSel |
| 14 | Branch |
| 15 | Jal |
| 16 | Jalr |
| 17 | Halt (ecall) |
| 18 | UseRs1 (lệnh có đọc rs1, dùng cho hazard) |
| 19 | UseRs2 (lệnh có đọc rs2) |

Bảng giải mã được sinh bằng `cpu_gen3.py::ctrl_rom()`. Ưu điểm: thêm lệnh mới chỉ cần sửa bảng mà không phải nối lại cổng logic.

| Lệnh | RegWrite | ASel | BSel | ALUOp | Mem | ResPC4 | ImmSel | Khác |
|---|---|---|---|---|---|---|---|---|
| R-type | 1 | rs1 | rs2 | theo f3/f7 | – | 0 | – | |
| I-ALU | 1 | rs1 | imm | theo f3 (srai: f7) | – | 0 | I | |
| LW | 1 | rs1 | imm | ADD | Read | 0 | I | wb = dữ liệu RAM |
| SW | 0 | rs1 | imm | ADD | Write | – | S | |
| Bxx | 0 | – | – | – | – | – | B | Branch |
| JAL | 1 | – | – | – | – | 1 | J | Jal, đích = PC+imm |
| JALR | 1 | rs1 | imm | ADD | – | 1 | I | Jalr, đích = (rs1+imm) & ~1 |
| LUI / AUIPC | 1 | 0 / PC | imm | ADD | – | 0 | U | |
| ECALL | 0 | | | | | | | Halt |

## 3. Datapath đơn chu kỳ
- PC (Register 32 bit) → ROM `IMEM`[PC[11:2]] → instr → Control, RegFile và ImmGen.
- ALU nhận: A = MUX(ASel: rs1 / PC / 0), B = MUX(BSel: rs2 / imm).
- RAM `DMEM` (đọc bất đồng bộ, ghi ở cạnh lên):
  - addr = ALU[11:2]
  - din = rs2
  - WE = MemWrite
- Dữ liệu ghi về: wb = MemRead ? RAM : (ResPC4 ? PC+4 : ALU).
- PC kế tiếp:
  - `Jalr ? (ALU & 0xFFFFFFFE)`
  - `: (Jal | Branch&cond) ? PC+imm`
  - `: PC+4`
- Thanh ghi, RAM và PC cùng cập nhật ở cạnh lên của Clock. Mỗi lệnh mất 1 chu kỳ.
- Bộ đếm `cycles` đếm số chu kỳ. Chân `halt` = 1 khi lệnh `ecall` được nạp.

### Các lỗi của bản gốc T5 đã sửa trong thiết kế mới
| Lỗi ở `RiscVComputer_T5.circ` (đo ở giai đoạn 1) | Cách sửa |
|---|---|
| SLL (R-type) cho kết quả 0 | ALU có Shifter `ll` riêng, lượng dịch = b[4:0], ALUOp giải mã đúng (f3=1) |
| SLTU/SLTIU cho 0xFFFFFFFF | Comparator unsigned, ngõ LT zero-extend 1→32 bit |
| LW sai (lần đầu 0xFFFFFFFF, các lần sau giá trị cũ) | RAM đọc bất đồng bộ. Chân nạp/ghi được xác định đúng thực nghiệm (port: addr, dout, din, OE, WE, CLK). Có MUX chọn dữ liệu ghi về |
| JAL không nhảy và không ghi rd | Jal chọn PC+imm(J), rd = PC+4 |
| JALR mã opcode sai (0x6f) | Giải mã opcode 0x67. PC = (rs1+imm)&~1, rd = PC+4 |
| main không có chân vào/ra | Có `PC_out`, `cycles`, `halt` (pipeline thêm `STALL`, `FLUSH`) |

## 4. Pipeline 5 tầng
Có các thanh ghi tầng IF/ID, ID/EX, EX/MEM và MEM/WB. Mỗi trường là một Register riêng; từ điều khiển 20 bit (thêm 2 bit `UseRs1`, `UseRs2`) đi kèm lệnh qua các tầng.

| Tầng | Công việc |
|---|---|
| IF | PC → ROM. PC+4 |
| ID | Control ROM, đọc RegFile, ImmGen, phát hiện hazard |
| EX | Forwarding MUX, ALU, BranchUnit, tính đích nhảy. **Nhánh/nhảy được giải quyết ở EX** |
| MEM | RAM |
| WB | Chọn dữ liệu và ghi RegFile |

### 4.1 Data hazard – Forwarding
Forwarding cho mỗi toán hạng (rs1, rs2) ở tầng EX:
- Nếu `EX/MEM.RegWrite && EX/MEM.rd != 0 && EX/MEM.rd == ID/EX.rs` thì lấy `EX/MEM.result` (ưu tiên cao nhất, dữ liệu mới nhất).
- Ngược lại, nếu `MEM/WB.RegWrite && MEM/WB.rd != 0 && MEM/WB.rd == ID/EX.rs` thì lấy `MEM/WB.data`.
- Ngược lại lấy giá trị đọc từ RegFile.

Bypass WB→ID: RegFile ghi ở cuối chu kỳ, nên khi lệnh ở WB ghi đúng thanh ghi mà lệnh ở ID đang đọc, giá trị `w_data` được chuyển thẳng vào ID. Nhờ vậy không cần "ghi nửa đầu chu kỳ, đọc nửa sau".

Giá trị đã forward cũng được dùng cho BranchUnit, JALR và dữ liệu ghi của SW.

### 4.2 Load-use hazard – Stall
- Điều kiện stall (đã tối ưu, chỉ stall khi lệnh sau **thật sự đọc** thanh ghi đó):
  `stall = ID/EX.MemRead && ID/EX.rd != 0 && ((ID/EX.rd == IF/ID.rs1 && UseRs1) || (ID/EX.rd == IF/ID.rs2 && UseRs2))`.
  `UseRs1/UseRs2` lấy từ Control ROM: LUI, AUIPC, JAL không đọc rs nào; lệnh loại I/load/JALR chỉ đọc rs1; R/store/branch đọc cả hai. Trước đây trường bit [19:15]/[24:20] của LUI/AUIPC/JAL/ADDI vô tình trùng rd của LW cũng gây stall thừa (t02 giảm 21→20 chu kỳ, t09 giảm 38→35).
- Khi stall:
  - giữ PC và IF/ID (enable = 0);
  - chèn **bubble** vào ID/EX bằng cách MUX từ điều khiển về 0 (đồng bộ, không dùng clear bất đồng bộ).
- Phạt 1 chu kỳ. Sau đó dữ liệu được forward từ MEM/WB.

### 4.3 Control hazard – Flush
- Khi lệnh ở EX là nhánh đúng điều kiện, JAL hoặc JALR, thì `flush = 1`:
  - PC ← đích;
  - IF/ID ← NOP (lệnh 0);
  - ID/EX ← bubble.
- Phạt 2 chu kỳ cho mỗi lần nhảy (chiến lược "dự đoán không nhảy").
- Flush được ưu tiên hơn stall: PC vẫn được ghi khi flush.

### 4.4 Dừng chương trình
Chân `halt` lấy bit Halt ở tầng **WB**. Mọi lệnh trước `ecall` đã ghi xong khi máy dừng.

### 4.5 Quan sát pipeline (phục vụ demo)
Các chân ra quan sát ở `main`: `PC_out` (tầng IF), `STALL`, `FLUSH`, `cycles`, `halt`. Trong GUI có thể nháy đúp các khối IF_ID/ID_EX/EX_MEM/MEM_WB để xem lệnh và giá trị ở từng tầng.

Bản mạch trước khi vẽ lại có thêm chân trace `ID_INSTR..WB_INSTR`. Trace dưới đây được ghi bằng bản đó (`Grok_output/tests/logs/pipeline_trace_t05_banTruoc.log`). Bản vẽ lại có cùng logic: số chu kỳ của cả 9 test trùng khớp từng test với bản trước.
 Trích đoạn:
```
cyc   PC  ID                   EX                   MEM                  WB                   STALL FLUSH
  7   1c  lw   x6, 0(x0)       sw   x5, 0(x0)       sub  x5, x4, x1      add  x4, x3, x3          0     0
  8   20  add  x7, x6, x6      lw   x6, 0(x0)       sw   x5, 0(x0)       sub  x5, x4, x1          1     0
  9   20  add  x7, x6, x6      -                    lw   x6, 0(x0)       sw   x5, 0(x0)           0     0   <- bubble
 16   34  addi x10, x0, 1      beq  x9, x5, t1      -                    lw   x9, 4(x0)           0     1   <- beq nhảy
 17   34  -                    -                    beq  x9, x5, t1      -                        0     0   <- 2 lệnh bị xoá
```

## 5. Công cụ
- **`asm.py`** chuyển `.s` thành `v3.0 hex words plain`, dùng cho Load Image của Logisim và cho tuỳ chọn `-l` khi chạy headless.
  - Hỗ trợ đầy đủ mã hoá R/I/S/B/U/J, nhãn và giả lệnh.
  - Kiểm tra phạm vi immediate và báo lỗi kèm số dòng.
- **`run_tests.py`** có một mô hình ISA chuẩn (golden model, viết bằng Python).
  - Chạy mỗi chương trình trên cả 2 mạch bằng Logisim headless.
  - So sánh **31 thanh ghi và toàn bộ RAM** với mô hình chuẩn.
  - Tuỳ chọn `--modules` chạy thêm test vector (`-w`) cho từng mô-đun.
- **Bộ sinh mạch** (`Grok_output/tests/generator/`):
  - netlist Python → `.circ`;
  - toạ độ chân của mọi linh kiện được truy vấn trực tiếp từ thư viện Logisim (PortQuery/SubQuery), nên không có dây nối sai do đặt tay.
  - **Bố cục (vẽ lại theo phong cách T5):** `main` gồm các subcircuit hình chữ nhật có tên chân, xếp theo cột từ trái sang phải đúng luồng dữ liệu, mỗi cột có tiêu đề. Single-cycle: `PC next | PC | IMEM | Decode/Control | RegFile/Imm | ALU | BranchUnit | DMEM | Write-back`. Pipeline: `IF | IF/ID | ID (InstrDecode, MainControl, HazardUnit, ForwardUnit) | ID/EX | EX | EX/MEM | MEM | MEM/WB | WB`. Dây thật chỉ nối khối ở hai cột kề nhau (dây ngắn); tín hiệu điều khiển và đường quay ngược dùng Tunnel có tên. Đã bỏ 31 chân x1..x31 và các chân trace. Ảnh: `Grok_output/previews/`. Bố cục do `layout.py` sinh; bản cũ lưu ở `Grok_output/old/`.
  - **Đọc thanh ghi khi test:** `run_tests.py` thay mỗi `ecall` bằng `jal x0, DUMP`; đoạn DUMP ở cuối chương trình `sw x0..x31` vào RAM word 480..511 rồi `ecall`. Địa chỉ các lệnh gốc không đổi. Chi phí đo được (single 33, pipeline 35 chu kỳ) được trừ ra, nên số chu kỳ trong mục 6 là của chương trình gốc.
  - Mô-đun mới: `LoadUnit` (dịch phải theo byte offset rồi mở rộng dấu/zero theo funct3) và `StoreUnit` (read-modify-write: `new = (old & ~mask) | ((wd << 8·off) & mask)`, mask byte/half/word).

## 6. Kiểm thử và kết quả (chạy thật, Logisim-evolution 5.0.0 headless)
### 6.1 Test từng mô-đun (test vector Logisim `-w`)
| Mô-đun | Số vector | Kết quả |
|---|---|---|
| ALU (10 phép × 7 cặp toán hạng, có số âm, 0x80000000, dịch 31) | 70 | **70/70 Passed** |
| ImmGen (I/S/B/U/J, biên âm/dương lớn nhất) | 10 | **10/10 Passed** |
| BranchUnit (6 loại nhánh × 5 cặp, có/không dấu) | 40 | **40/40 Passed** |

### 6.2 Test toàn CPU (so với golden model: 31 thanh ghi + RAM)
| Chương trình | Nội dung | Số lệnh thực thi | Single-cycle (chu kỳ) | Pipeline (chu kỳ) | Kết quả |
|---|---|---|---|---|---|
| t01_alu | 19 lệnh R/I-ALU bắt buộc, số âm, SLT/SLTU/SLTIU, ghi x0 | 29 | 28 | 32 | PASS / PASS |
| t02_mem | SW/LW, offset âm, LW liên tiếp, LW cùng địa chỉ | 17 | 16 | 20 (cũ 21) | PASS / PASS |
| t03_branch | Vòng lặp tổng 1..10 = 55, BEQ/BNE/BLT/BGE/BLTU/BGEU nhảy và không nhảy | 45 | 44 | 74 | PASS / PASS |
| t04_jump | JAL gọi hàm, JALR trả về, JALR với offset và xoá bit 0 | 11 | 10 | 22 | PASS / PASS |
| t05_hazard | Forward EX/MEM và MEM/WB, load-use, load→store, load→branch, flush JAL/BEQ, ghi x0 | 23 | 22 | 34 | PASS / PASS |
| t06_upper | LUI, AUIPC, li 32 bit | 9 | 8 | 12 | PASS / PASS |
| t07_fib | Fibonacci 12 số ghi RAM, đọc lại tính tổng = 232 | 152 | 151 | 211 | PASS / PASS |
| t08_bytehalf | SB/SH ở mọi offset, LB/LH (có dấu) và LBU/LHU, đọc lại word | 31 | 30 | 35 | PASS / PASS |
| t09_nostall | LW rồi ADDI/LUI/AUIPC có trường rs trùng rd (không được stall), load-use thật, BLT/BGE/BLTU/BGEU | 21 | 20 | 35 | PASS / PASS |

**Tổng: 18/18 PASS** (thêm test module: ALU 70/70, ImmGen 10/10, BranchUnit 40/40). Chạy lại trên bản bố cục dây mới, số chu kỳ giống hệt bản cũ. Log ở `Grok_output/tests/logs/run_all.log`.

Ghi chú: số chu kỳ single-cycle = số lệnh − 1, vì máy dừng ngay khi `ecall` được nạp. Số chu kỳ pipeline tính đến khi `ecall` tới WB, nên gồm 4 chu kỳ lấp đầy, các stall và 2 chu kỳ phạt cho mỗi lần nhảy.

Mỗi lệnh trong 24 lệnh bắt buộc xuất hiện ít nhất một lần trong t01–t09 và đều cho kết quả khớp với golden model:

| Lệnh | Nằm trong |
|---|---|
| ADD, SUB, AND, OR, XOR, SLL, SRL, SRA, SLT, SLTU, ADDI, ANDI, ORI, XORI, SLLI, SRLI, SRAI, SLTI, SLTIU | t01 |
| LW, SW | t02, t05, t07, t08 |
| LB, LH, LBU, LHU, SB, SH | t08 |
| BLT, BGE, BLTU, BGEU | t03, t09 |
| BEQ, BNE | t03, t05, t07 |
| JAL, JALR | t04, t05 |

### 6.3 Toàn bộ kết quả với bản có tính năng nâng cao (chạy thật ngày 31/10/2026)
`python run_tests.py --modules` → **30/30 PASS, 4 SKIP** (đơn chu kỳ không có CSR/IO/F nên t14–t17 bị bỏ qua có chủ đích). Module: ALU 70/0, ImmGen 10/0, BranchUnit 40/0 trên cả 2 mạch. 18 test cũ t01–t09 × 2 mạch vẫn PASS. Log: `Grok_output/tests/logs/full_run.txt`, CSV `results.csv`.

| Test mới | Kiểm tra | Đơn chu kỳ | Pipeline |
|---|---|---|---|
| t10_muldiv | MUL/MULH/MULHSU/MULHU/DIV/DIVU/REM/REMU, chia 0, tràn | PASS | PASS |
| t11_bploop | vòng lặp lồng nhau (đo dự đoán nhánh) | PASS | PASS |
| t12_cache | truy cập lặp/xung đột D-cache, đếm hit/miss | PASS | PASS (hit 34 / miss 5 = golden) |
| t13_storefwd | load→store liền nhau | PASS | PASS |
| t14_irq_msip | ngắt phần mềm (MSIP), mret, MPIE | SKIP | PASS |
| t15_irq_timer | ngắt timer (mtime/mtimecmp) | SKIP | PASS |
| t16_gpio_uart | LED/SW/UART TX, so khớp chuỗi "RV32 OK\n" và LED=0x3c | SKIP | PASS |
| t17_fp | flw/fsw, fadd/fsub/fmul/fdiv/fsqrt, fsgnj, fmin/fmax, so sánh, fcvt, fmv | SKIP | PASS |

Golden model (`run_tests.py`, lớp `Golden`) được mở rộng: M, CSR/mret/ngắt, MMIO, mô hình cache, F (float32 qua `struct`). Ngoài thanh ghi x và RAM còn so INSTRET, BR_CNT, DCACHE hit/miss, thanh ghi f, chuỗi UART và LED.

## 7. Các tính năng nâng cao đã làm (mỗi mục: thiết kế – kiểm chứng – trạng thái)
Bản đo so sánh: sinh 5 biến thể pipeline bằng biến môi trường của bộ sinh (`BP`, `CACHE`, `ADVFWD`), chạy cùng bộ test (`Grok_output/tests/logs/variants_cmp.csv`). Số chu kỳ đã trừ chi phí thủ tục DUMP.

| Test | base (đủ tính năng) | không BP | không fwd nâng cao | không cache (mọi load chậm 3 ck) | bộ nhớ lý tưởng |
|---|---|---|---|---|---|
| t03 | 60 | 74 | 60 | 60 | 60 |
| t07 fib | 175 | 211 | 175 | 211 | 175 |
| t11 | 537 | 729 | 537 | 537 | 537 |
| t12 | 367 | 445 | 367 | 469 | 352 |
| t13 | 23 | 23 | 27 | 38 | 23 |
| Tổng | 1658 | 1990 | 1664 | 1949 | 1643 |

### 7.1 Dự đoán nhánh (BTB + BHT 2 bit) – pipeline – **Đã làm + verify**
- Khối `BTB` ở tầng IF: 16 mục, chỉ số pc[5:2], tag = toàn bộ PC, mỗi mục có đích nhảy và bộ đếm bão hoà 2 bit. Dự đoán nhảy khi mục hợp lệ và bộ đếm ≥ 2.
- Tầng EX so sánh kết quả thật với dự đoán; sai thì flush IF/ID, ID/EX và sửa PC; cập nhật BTB/BHT cho mọi lệnh nhánh/JAL/JALR.
- Bộ đếm hiệu năng `BR_CNT`, `BR_MISS`. t11: miss 24 (có BP) so với 120 (không BP), chu kỳ 537 so với 729 (−26%). t07: 175 so với 211.

### 7.2 D-cache – pipeline – **Đã làm + verify**
- Direct-mapped 16 dòng × 1 word, tag = word[9:4], valid bit; ghi xuyên (write-through) + cấp phát khi ghi. Bộ nhớ chính giả lập chậm: miss phạt 3 chu kỳ (`MSTALL`), stall toàn pipeline.
- Đếm `DC_HIT`/`DC_MISS`, so khớp với mô hình cache trong golden model (t12: 34/5).
- t12: 367 chu kỳ (cache) so với 469 (không cache) và 352 (bộ nhớ lý tưởng).
- Không có I-cache (ROM lệnh 1 chu kỳ).

### 7.3 RV32M – cả 2 bản – **Đã làm + verify**
- Khối `MulDiv` tổ hợp: 3 Multiplier (unsigned / có dấu / signed×unsigned) cho MUL/MULH/MULHU/MULHSU, Divider có dấu và không dấu cho DIV/DIVU/REM/REMU.
- Chia cho 0 theo chuẩn: thương 0xFFFFFFFF, dư = a. Tràn −2³¹/−1: thương −2³¹, dư 0. Cả hai trường hợp nằm trong t10.
- Tổ hợp 1 chu kỳ nên pipeline không cần stall thêm (đổi lại đường tới hạn dài, chấp nhận được trong mô phỏng).

### 7.4 Ngắt / CSR (Zicsr) – pipeline – **Đã làm + verify**
- `CSRFile`: mstatus (MIE/MPIE), mie, mip, mtvec, mscratch, mepc, mcause, cycle/mcycle. Lệnh CSRRW/S/C và bản I, MRET.
- Nguồn ngắt: phần mềm (MSIP, ghi vào MMIO), timer (mtime ≥ mtimecmp), ngoài (chân `IRQ` ở main, chỉ dùng khi demo GUI).
- Nhận ngắt ở tầng EX: lệnh ở EX bị huỷ, mepc = PC của nó, các lệnh sau bị flush, nhảy tới mtvec. MRET khôi phục MIE từ MPIE.
- Test t14, t15 PASS. Hai test này có cờ `# timing_dependent` vì thời điểm ngắt phụ thuộc chu kỳ, nên không so INSTRET/BR_CNT.

### 7.5 GPIO / UART (memory-mapped I/O) – pipeline – **Đã làm + verify**
- `MMIO` tại 0x80000000: +0 LED (ra chân `LED`), +4 SW (chân vào), +8 UART_TX (ra TTY của Logisim), +C UART_STATUS (luôn sẵn sàng = 1), +10 MSIP, +14 MTIMECMP, +18 MTIME.
- t16 in "RV32 OK\n" ra TTY và đặt LED = 0x3c. Test đọc TTY khi chạy headless và so khớp đúng chuỗi.

### 7.6 Forwarding nâng cao (MEM→MEM cho dữ liệu store) – pipeline – **Đã làm + verify**
- LW rồi SW dùng ngay kết quả LW làm dữ liệu ghi: forward từ MEM/WB vào dữ liệu ghi ở tầng MEM, không còn stall.
- t13: 23 chu kỳ so với 27 khi không có forward này.

### 7.7 RV32F (tập con) – pipeline – **Một phần (tập con), đã verify**
- 32 thanh ghi f (`RegFile64` gộp x/f), FLW/FSW, FADD/FSUB/FMUL/FDIV/FSQRT.S, FSGNJ/FSGNJN/FSGNJX, FMIN/FMAX, FEQ/FLT/FLE, FCVT.W(U).S, FCVT.S.W(U), FMV.X.W/FMV.W.X. Dùng thư viện FP Arithmetic của Logisim 5.
- t17 PASS và so khớp từng thanh ghi f.
- Chưa làm: FMA (fmadd…), FCLASS, thanh ghi fflags/frm/fcsr. Làm tròn theo trường rm chỉ xấp xỉ (RMM ≈ làm tròn của Java). NaN trong fmin/fmax/fcvt chưa đúng chuẩn. FCVT.WU.S với số âm bị quấn vòng thay vì bão hoà về 0.

### 7.8 Kiểm thử đột biến (bộ test bắt được lỗi của từng tính năng)
Sinh lại pipeline với lỗi cố ý (`MUT=… python cpu_gen4.py pipeline x.circ`), chạy 8 test t05, t07, t09, t10, t12, t13, t14, t15. Log: `Grok_output/tests/mutation/log2.txt`.

| Đột biến | Ý nghĩa | Kết quả |
|---|---|---|
| mulh | MULH tính như không dấu | t10 FAIL (bắt được) |
| divz | bỏ xử lý chia cho 0 | t10 FAIL |
| nofill | cache không nạp dòng khi miss | t12 FAIL (hit/miss lệch) |
| nompie | MRET không khôi phục MIE | t14 FAIL |
| noflush | không flush khi nhảy sai | 0/8 PASS |
| nostall | bỏ stall load-use | 5 test FAIL |
| nofwd | bỏ forwarding | 4 test FAIL |
| nosfwd | bỏ forward dữ liệu store | t05, t09, t13 FAIL |
| noirq | không bao giờ nhận ngắt | t14, t15 không dừng (hết thời gian chờ) = bắt được |
| nosquash | không huỷ lệnh ở EX khi ngắt | t15 FAIL |

Tất cả 10 đột biến đều bị phát hiện.

## 8. Xuất HDL
### 8.1 Xuất tự động từ Logisim
`hdl/hdl_export.py` chèn boardmap TERASIC_DE0, mọi chân để "open", rồi gọi `java -jar logisim.jar -f X_hdl.circ main TERASIC_DE0 50000000 HDLONLY`.
- **Bản RV32I trước đây** (lưu ở `hdl/logisim_export/`): xuất được cả VHDL và Verilog.
- **Bản mới có RV32M/F: Logisim 5.0.0 không xuất được.** Đã thử thật: trình sinh HDL dừng im lặng ở khối `MulDiv`, không tạo file nào. Khi xoá thử linh kiện `Divider` thì bản đơn chu kỳ xuất được 70 file VHDL, vậy nguyên nhân là `Divider` không có bộ sinh HDL. Pipeline còn dùng thêm các linh kiện FP Arithmetic và TTY, cũng không thuộc danh sách xuất HDL. Muốn xuất HDL thì phải thay Divider bằng mạch chia tự dựng (32 tầng trừ–dịch) và bỏ F/TTY. Việc này chưa làm.
### 8.2 Verilog viết tay
`hdl/verilog/` **vẫn chỉ là RV32I** (đơn chu kỳ + pipeline cơ bản, 18/18 PASS bằng Icarus Verilog như trước). Chưa mở rộng sang BP/cache/M/CSR/IO/F.

## 9. Hạn chế còn lại
- HDL: xem mục 8.
- Không có I-cache. Cache chỉ có 1 word mỗi dòng, ghi xuyên.
- `mtime` đếm chu kỳ clock (không phải thời gian thực). Chân `IRQ` (ngắt ngoài) chỉ dùng được khi demo GUI, không có test tự động.
- RV32F chỉ là tập con (xem 7.7).
- Ngắt chỉ ở pipeline. Bản đơn chu kỳ có RV32M nhưng không có CSR/IO/F.
- Bố cục mạch vẫn do máy sinh: các tín hiệu nối bằng Tunnel theo tên nên nhìn "thưa", nhưng mọi tín hiệu đều nối đủ (có kiểm chứng bằng test). Pipeline rất rộng (khoảng 10000 px ở zoom 1.0).
- Bộ nhớ lệnh và dữ liệu mỗi bộ 4 KB. Không hỗ trợ truy cập không thẳng hàng.
