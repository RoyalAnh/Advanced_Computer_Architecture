# RISC-V RV32I (+M, +CSR/ngắt, +GPIO/UART, +F tập con) trên Logisim-evolution – Hướng dẫn chạy

> Hai file gốc `RiscVComputer_T5.circ` và `Yêu cầu BTL.pdf` **không bị sửa**. Mọi file mới đều là file riêng.

## 1. Các file chính (thư mục gốc)
| File | Mô tả |
|---|---|
| `RiscV_SingleCycle.circ` | CPU đơn chu kỳ RV32I + **RV32M**, đã sửa toàn bộ lỗi của bản T5 |
| `RiscV_Pipeline.circ` | CPU pipeline 5 tầng, có forwarding (kể cả MEM→MEM cho store), stall load-use, flush, **dự đoán nhánh BTB + BHT 2 bit, D-cache 16 dòng, RV32M, CSR + ngắt (phần mềm/timer/ngoài), GPIO/UART memory-mapped tại 0x80000000, RV32F tập con** |
| `asm.py` | Trình hợp dịch (assembler) `.s` → ảnh ROM Logisim (`v3.0 hex words plain`) |
| `run_tests.py` | Script chạy tự động toàn bộ test trên cả 2 mạch và so sánh với mô hình chuẩn (golden model) |
| `BAO_CAO.md` | Bản nháp báo cáo: thiết kế, datapath, điều khiển, hazard, kết quả test, phân tích phần nâng cao |
| `hdl/` | Xuất HDL: `logisim_export/` (VHDL + Verilog do Logisim sinh), `verilog/` (Verilog viết tay + testbench + `run_verilog_tests.py`), `hdl_export.py`, `logs/` |
| `Grok_output/tests/` | Chương trình test (`programs/`), test vector module (`modules/`), log (`logs/`), mạch đột biến (`mutation/`), bộ sinh mạch (`generator/`) |

## 2. Mở trên Logisim (GUI)
1. Mở `RiscV_SingleCycle.circ` hoặc `RiscV_Pipeline.circ` bằng Logisim-evolution 5.0.0.
2. ROM `IMEM` có sẵn chương trình demo Fibonacci (`t07_fib.s`).
3. Bấm **Simulate → Ticks Enabled** hoặc Ctrl+T để chạy từng xung. Theo dõi các chân ra `PC_out`, `cycles` và `halt` (bản pipeline có thêm `STALL`, `FLUSH`). Muốn xem giá trị thanh ghi: nháy đúp khối `RegFile` (hoặc dùng Simulate → chọn khối trong cây mạch) rồi xem từng Register bên trong.
4. Muốn nạp chương trình khác: chuột phải vào ROM `IMEM`, chọn **Load Image…**, rồi chọn file `.hex` do `asm.py` tạo ra.
5. Lệnh `ecall` làm chân `halt` = 1, tức là kết thúc chương trình.

> Mạch được **sinh tự động**, vẽ lại theo phong cách của `RiscVComputer_T5.circ`: mỗi khối là một subcircuit hình chữ nhật có tên chân, xếp **từ trái sang phải theo luồng dữ liệu**, có tiêu đề cột.
> - Single-cycle: `PC next → PC → IMEM → Decode/Control → RegFile/Imm → ALU → BranchUnit → DMEM → Write-back`.
> - Pipeline: `IF → IF/ID → ID (Decode, Control, Hazard, Forward) → ID/EX → EX → EX/MEM → MEM → MEM/WB → WB`.
> - Dây thật nối các khối ở hai cột kề nhau; tín hiệu điều khiển và các đường quay ngược (PC+4, nhánh, forwarding, dữ liệu ghi về) dùng **Tunnel có tên**, nên không có dây dài cắt ngang mạch.
> - Đã bỏ dàn 31 chân `x1..x31` và các chân trace. Ảnh xem trước: `Grok_output/previews/` (zoom 0.6 và 1.0).
> - Mô-đun con dùng chung: ALU, RegFile, ImmGen, BranchUnit, LoadUnit, StoreUnit, Control (ROM giải mã), InstrDecode, MainControl, HazardUnit, ForwardUnit, các thanh ghi tầng IF_ID/ID_EX/EX_MEM/MEM_WB, CycleCounter.
> - Bản cũ (trước khi vẽ lại) nằm ở `Grok_output/old/`; bản RV32I trước khi thêm tính năng nâng cao nằm ở `Grok_output/old_v2/`.
> - Bản pipeline có thêm ở `main`: chân vào `SW` (switch), `IRQ` (ngắt ngoài), chân ra `LED`, TTY (UART_TX), các bộ đếm hiệu năng.

## 3. Hợp dịch chương trình
```
python asm.py chuong_trinh.s            # tạo chuong_trinh.hex
python asm.py chuong_trinh.s --list     # in kèm địa chỉ + mã máy
```
Assembler hỗ trợ:
- toàn bộ lệnh RV32I cơ bản: R, I, lw/sw, các lệnh nhánh, jal/jalr, lui/auipc và ecall;
- nhãn và comment `#`;
- số dạng thập phân hoặc hex;
- giả lệnh `nop li la mv not neg j jr ret call beqz bnez bgt ble bgtu bleu seqz snez`.

Khi có lỗi, assembler báo số dòng.

## 4. Chạy test tự động (không mở GUI)
Chỉ cần **Python 3** và Logisim-evolution 5.0.0 đã cài. **Không cần cài Java**: `run_tests.py` tự tìm theo thứ tự
1. `--java` / `--logisim` nếu có chỉ định;
2. `tools\jdk\bin\java.exe` trong thư mục dự án (JDK portable, nếu bạn giải nén vào đó);
3. biến môi trường `JAVA`, `JAVA_HOME`, hoặc `java` trên PATH (kèm jar `C:\Program Files\logisim-evolution\app\logisim-evolution-5.0.0-all.jar`);
4. nếu không có Java: dùng thẳng `C:\Program Files\logisim-evolution\logisim-evolution.exe` (có JRE đóng gói sẵn, chạy headless được).

Dòng đầu tiên in ra `Logisim runner: ...` cho biết cách đang dùng. Vì `logisim-evolution.exe` làm hỏng đường dẫn có dấu tiếng Việt, script tự chép mạch/hex sang thư mục ASCII tạm (`%TEMP%\rv32i_logisim_tmp` hoặc `C:\Users\Public\rv32i_logisim_tmp`) trước khi chạy. Khi chạy tay bằng exe, hãy đặt file ở đường dẫn không dấu.
```
python run_tests.py                    # chạy mọi test (17 chương trình) trên cả 2 mạch
python run_tests.py --csv kq.csv       # ghi thêm bảng chu kỳ + bộ đếm (BR_MISS, DC_HIT, ...)
python run_tests.py --modules          # chạy thêm test vector cho ALU / ImmGen / BranchUnit
python run_tests.py Grok_output\tests\programs\t05_hazard.s
python run_tests.py --circ Grok_output\tests\mutation\nofwd.circ   # chạy trên bản lỗi cố ý
```
Script làm các bước sau:
1. Hợp dịch file `.s`.
2. Chạy mô hình ISA chuẩn bằng Python.
3. Chạy mạch headless: `<runner> mach.circ -l prog.hex IMEM -t table,halt --save ram.txt`.
4. So sánh 31 thanh ghi x (và f nếu có), toàn bộ RAM, bộ đếm INSTRET/BR_CNT/DCACHE, chuỗi UART (`# expect_uart:`) và LED (`# expect_led:`), rồi in PASS/FAIL kèm số chu kỳ.

Test có dòng `# requires: CSR IO F M` sẽ SKIP trên mạch không có tính năng đó (ví dụ t14–t17 trên bản đơn chu kỳ). Hết thời gian chờ mỗi lần chạy: biến `RT_TIMEOUT` (mặc định 300 giây).

Vì mạch không còn chân `x1..x31`, script tự thay mỗi `ecall` bằng `jal x0, DUMP`. Đoạn `DUMP` thêm ở cuối chương trình ghi x0..x31 vào RAM word 480..511 (byte 0x780..0x7FC) rồi mới `ecall`. Script đo chi phí đoạn này (single 33, pipeline 67 chu kỳ vì DUMP lưu thêm 32 thanh ghi f) và trừ ra, nên số chu kỳ báo cáo đúng bằng chương trình gốc. Chương trình test không được ghi vào vùng 0x780..0x7FF (script kiểm tra).

Chạy tay một chương trình:
```
"C:\Program Files\logisim-evolution\logisim-evolution.exe" RiscV_Pipeline.circ -l prog.hex IMEM -t table,halt
```

### 4.1 Mô phỏng bản Verilog (tuỳ chọn)
Cần Icarus Verilog (`iverilog`, `vvp`) trên PATH (Windows: bộ cài tại bleyer.org/icarus):
```
python hdl\verilog\run_verilog_tests.py
```
Xuất lại HDL từ Logisim (lưu ý: bản mới có RV32M/F **không xuất được** vì Logisim 5.0.0 chưa hỗ trợ HDL cho Divider/FP, xem BAO_CAO mục 8; Verilog viết tay vẫn chỉ là RV32I): `python hdl\hdl_export.py RiscV_Pipeline.circ hdl\RiscV_Pipeline_hdl.circ` rồi `java -jar <logisim jar> -f hdl\RiscV_Pipeline_hdl.circ main TERASIC_DE0 50000000 HDLONLY` (hoặc mở file `_hdl.circ` trong GUI → FPGA → Synthesize & Download, chọn "HDL only").

## 5. Xem và sửa bằng VS Code
Mở được bình thường, không bắt buộc cài thêm gì:
- `.circ` là XML;
- `.s`, `.py`, `.md` và `.hex` là file văn bản.

Extension nên cài thêm (tùy chọn):
- **XML** (Red Hat) để tô màu và gập khối file `.circ`;
- **Python** (Microsoft) để chạy `asm.py` và `run_tests.py`;
- **RISC-V Support** để tô màu cú pháp hợp ngữ `.s`;
- Markdown Preview có sẵn để xem README và BAO_CAO.

Lưu ý: sửa `.circ` bằng tay dễ làm hỏng mạch. Nên sửa trong Logisim, hoặc sửa `Grok_output/tests/generator/_part*.py` (gộp thành `cpu_gen4.py`) rồi sinh lại mạch.

## 6. Sinh lại mạch (tùy chọn, cho người muốn sửa thiết kế)
`Grok_output/tests/generator/` chứa:
- `cpu_gen4.py` (= nối `_part1.py _part2.py _part3.py _app.py _part4.py`): netlist của CPU (bảng điều khiển, mô-đun, single-cycle, pipeline), cách nhóm khối và thứ tự cột;
- `layout.py`: xếp khối theo cột, nối dây thật giữa cột kề nhau, còn lại dùng Tunnel; sinh hình chữ nhật có tên chân cho subcircuit;
- `lg.py`, `wire.py`: chuyển netlist thành XML `.circ`;
- `ports.json`, `geom.json`: bộ đệm toạ độ chân linh kiện (có sẵn nên không cần Java khi sinh lại);
- `PortQuery2.java`, `SubQuery.java`: lấy toạ độ chân từ thư viện Logisim; `Render.java`: vẽ ảnh PNG xem trước.

Cách dùng: `python cpu_gen4.py single Out.circ [prog.hex]` hoặc `python cpu_gen4.py pipeline Out.circ`. Biến thể để so sánh: `BP=0`, `CACHE=none|0`, `ADVFWD=0`. Bản lỗi cố ý: `MUT=mulh|divz|nofill|nompie|noflush|nostall|nofwd|nosfwd|noirq|nosquash`. Chỉ khi thêm loại linh kiện mới mới cần Java: đặt biến `JAVA` và `LOGISIM_JAR`.
