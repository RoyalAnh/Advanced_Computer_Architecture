# RISC-V RV32I (+M, +CSR/ngắt, +GPIO/UART, +F tập con) trên Logisim-evolution

> *Tóm tắt:* Hai CPU RISC-V được xây dựng trong Logisim-evolution 5.x — một nhân RV32I+M đơn chu kỳ (single-cycle) và một nhân pipelined 5 giai đoạn với tính năng forwarding, load-use stall, flush, dự đoán rẽ nhánh BTB + 2-bit BHT, D-cache 16 dòng, CSR + ngắt (interrupts), GPIO/UART ánh xạ bộ nhớ (memory-mapped) và tập hợp con RV32F. Gói sản phẩm bao gồm một Python assembler (`asm.py`) và một trình chạy kiểm thử tự động (`run_tests.py`) có chức năng so sánh mọi lần chạy mạch với một mô hình ISA chuẩn (golden ISA model). Hoạt động trên Windows, Linux và macOS.

## 1. Cấu trúc repo
| Đường dẫn | Nội dung |
|---|---|
| `RiscV_SingleCycle.circ` | CPU đơn chu kỳ RV32I + RV32M |
| `RiscV_Pipeline.circ` | CPU pipeline 5 tầng: forwarding (kể cả MEM→MEM cho store), stall load-use, flush, dự đoán nhánh BTB + BHT 2 bit, D-cache 16 dòng, RV32M, CSR + ngắt (phần mềm/timer/ngoài), GPIO/UART memory-mapped tại `0x80000000`, RV32F tập con |
| `RiscVComputer_T5.circ` | Mạch gốc tham khảo (bản T5 ban đầu, giữ nguyên để đối chiếu) |
| `asm.py` | Assembler `.s` → ảnh ROM Logisim (`v3.0 hex words plain`) |
| `run_tests.py` | Chạy toàn bộ test trên cả 2 mạch (headless) và so sánh với mô hình ISA chuẩn (golden model) |
| `artifacts/tests/programs/` | 17 chương trình test `t01..t17` (`.s` + `.hex` đã hợp dịch sẵn) |
| `artifacts/tests/modules/` | Test vector cho ALU / ImmGen / BranchUnit |
| `artifacts/tests/mutation/` | Các mạch có lỗi cố ý (dùng để chứng minh bộ test phát hiện được lỗi) |
| `artifacts/tests/generator/` | Bộ sinh mạch `.circ` bằng Python (netlist → XML) |
| `artifacts/tests/logs/` | Log và bảng kết quả các lần chạy test |
| `artifacts/previews/` | Ảnh PNG xem trước sơ đồ `main` của 2 mạch |
| `artifacts/PHAN_TICH_BTL.md`, `artifacts/test*.{s,rom,circ}` | Phân tích đề và các thử nghiệm ban đầu |
| `hdl/verilog/` | Verilog viết tay (RV32I) + testbench + `run_verilog_tests.py` |
| `hdl/*_hdl*.circ`, `hdl/hdl_export.py` | Bản mạch chuẩn bị để Logisim xuất HDL |

## 2. Yêu cầu
- **Logisim-evolution 5.x** (đã kiểm thử với 5.0.0) — tải tại <https://github.com/logisim-evolution/logisim-evolution/releases>. Có bộ cài cho Windows (`.msi`), macOS (`.dmg`), Linux (`.deb`/`.rpm`) và bản `…-all.jar` chạy mọi nền tảng (cần Java; bản 5.x dùng Java 21 trở lên).
- **Python 3** (3.8+), không cần thư viện ngoài.
- Tuỳ chọn: Icarus Verilog (`iverilog`, `vvp`) nếu muốn mô phỏng bản Verilog.

Bộ cài Logisim (`.msi`/`.dmg`/`.deb`) đã đóng gói sẵn JRE, nên **không bắt buộc cài Java riêng** nếu dùng bộ cài.

## 3. Mở mạch trên Logisim (GUI)
1. Mở `RiscV_SingleCycle.circ` hoặc `RiscV_Pipeline.circ` bằng Logisim-evolution (File → Open).
2. ROM `IMEM` đã nạp sẵn chương trình demo Fibonacci (`t07_fib.s`).
3. Bật xung clock: **Simulate → Auto-Tick Enabled** (Ctrl+K) để chạy liên tục, hoặc **Simulate → Manual Tick** (Ctrl+T) để chạy từng xung. Theo dõi các chân ra `PC_out`, `cycles`, `halt` (bản pipeline có thêm `STALL`, `FLUSH`, `LED`, TTY và các bộ đếm hiệu năng).
4. Xem giá trị thanh ghi: chọn công cụ Poke (bàn tay) rồi nháy đúp vào khối `RegFile` (hoặc chọn `RegFile` trong cây mạch ở khung Simulation) để vào bên trong và xem từng Register.
5. Nạp chương trình khác: chuột phải vào ROM `IMEM` → **Load Image…** → chọn file `.hex` do `asm.py` tạo.
6. Lệnh `ecall` đưa chân `halt` lên 1 (kết thúc chương trình). Reset bằng **Simulate → Reset Simulation** (Ctrl+R).

Bố cục mạch: mỗi khối là một subcircuit hình chữ nhật có tên chân, xếp từ trái sang phải theo luồng dữ liệu, có tiêu đề cột.
- Single-cycle: `PC next → PC → IMEM → Decode/Control → RegFile/Imm → ALU → BranchUnit → DMEM → Write-back`.
- Pipeline: `IF → IF/ID → ID (Decode, Control, Hazard, Forward) → ID/EX → EX → EX/MEM → MEM → MEM/WB → WB`.
- Dây thật nối các khối ở hai cột kề nhau; tín hiệu điều khiển và đường quay ngược (PC+4, nhánh, forwarding, write-back) dùng **Tunnel có tên**.
- Mô-đun con dùng chung: ALU, RegFile, ImmGen, BranchUnit, LoadUnit, StoreUnit, Control, InstrDecode, MainControl, HazardUnit, ForwardUnit, IF_ID/ID_EX/EX_MEM/MEM_WB, CycleCounter.
- Bản pipeline có thêm ở `main`: chân vào `SW` (switch), `IRQ` (ngắt ngoài); chân ra `LED`, TTY (UART_TX).

## 4. Hợp dịch chương trình
```
python asm.py chuong_trinh.s            # tạo chuong_trinh.hex
python asm.py chuong_trinh.s --list     # in kèm địa chỉ + mã máy
```
(Trên Linux/macOS có thể cần gõ `python3` thay cho `python`.)

Hỗ trợ: toàn bộ RV32I (R, I, load/store, branch, jal/jalr, lui/auipc, ecall), RV32M, CSR/mret, tập con RV32F; nhãn, comment `#`, số thập phân/hex; giả lệnh `nop li la mv not neg j jr ret call beqz bnez bgt ble bgtu bleu seqz snez`. Lỗi được báo kèm số dòng.

## 5. Chạy test tự động (headless, không mở GUI)
```
python run_tests.py                                         # 17 chương trình × 2 mạch
python run_tests.py --modules                               # thêm test vector ALU / ImmGen / BranchUnit
python run_tests.py --csv kq.csv                            # ghi bảng chu kỳ + bộ đếm (BR_MISS, DC_HIT, ...)
python run_tests.py artifacts/tests/programs/t05_hazard.s   # chỉ chạy một chương trình
python run_tests.py --circ artifacts/tests/mutation/nofwd.circ   # chạy trên mạch có lỗi cố ý
```
Đường dẫn dùng `/` chạy được trên mọi hệ điều hành (Windows chấp nhận cả `\`).

### 5.1 Script tìm Logisim như thế nào
Dòng đầu tiên in ra `Logisim runner: ...` cho biết cách đang dùng. Thứ tự tìm:
1. Tham số dòng lệnh: `--java <java>` và `--logisim <logisim-evolution-…-all.jar>`.
2. **Java + jar**: jar lấy từ `--logisim`, biến môi trường `LOGISIM_JAR`, hoặc `tools/logisim-evolution.jar` trong thư mục dự án; Java lấy từ `tools/jdk/bin/java` (JDK portable trong dự án), biến `JAVA`, `JAVA_HOME`, hoặc `java` trên `PATH`.
3. **Launcher của bộ cài** (có JRE đóng gói sẵn): biến `LOGISIM_EXE`, `logisim-evolution` trên `PATH`, hoặc một vài vị trí cài mặc định, ví dụ:
   - Windows: `C:\Program Files\logisim-evolution\logisim-evolution.exe`
   - macOS: `/Applications/logisim-evolution.app/Contents/MacOS/logisim-evolution`
   - Linux (`.deb`/`.rpm`): `/opt/logisim-evolution/bin/logisim-evolution`

Nếu Logisim nằm ở chỗ khác, chỉ cần đặt biến môi trường:
```
# Linux / macOS
export LOGISIM_JAR=$HOME/apps/logisim-evolution-5.0.0-all.jar     # dùng kèm java trên PATH
# hoặc
export LOGISIM_EXE=/duong/dan/toi/logisim-evolution

# Windows PowerShell
$env:LOGISIM_EXE = "D:\Apps\logisim-evolution\logisim-evolution.exe"
# hoặc
$env:LOGISIM_JAR = "D:\Apps\logisim-evolution-5.0.0-all.jar"; $env:JAVA = "D:\Apps\jdk-21\bin\java.exe"
```
Biến `RT_TIMEOUT` đặt thời gian chờ tối đa mỗi lần chạy (mặc định 300 giây).

Lưu ý Windows: launcher `logisim-evolution.exe` làm hỏng đường dẫn có ký tự Unicode (ví dụ tên thư mục tiếng Việt có dấu). Script tự chép mạch/hex sang một thư mục ASCII tạm trước khi chạy, nên bạn để repo ở đâu cũng được.

### 5.2 Script làm gì
1. Hợp dịch file `.s`.
2. Chạy mô hình ISA chuẩn bằng Python.
3. Chạy mạch headless: `<runner> mach.circ -l prog.hex IMEM -t table,halt --save ram.txt`.
4. So sánh 31 thanh ghi x (và f nếu có), toàn bộ RAM, bộ đếm INSTRET/BR_CNT/DCACHE, chuỗi UART (`# expect_uart:`) và LED (`# expect_led:`), in PASS/FAIL kèm số chu kỳ.

Test có dòng `# requires: CSR IO F M` sẽ SKIP trên mạch không có tính năng đó (ví dụ t14–t17 trên bản đơn chu kỳ).

Vì mạch không có chân ra cho từng thanh ghi, script thay mỗi `ecall` bằng `jal x0, DUMP`; đoạn `DUMP` ở cuối chương trình ghi x0..x31 (và f0..f31) vào RAM word 480..511 (byte `0x780..0x7FC`) rồi mới `ecall`. Chi phí của đoạn này được đo và trừ ra, nên số chu kỳ báo cáo đúng bằng chương trình gốc. Chương trình test không được ghi vào vùng `0x780..0x7FF`.

Chạy tay một chương trình (thay `<runner>` bằng launcher hoặc `java -jar <jar>`):
```
<runner> RiscV_Pipeline.circ -l prog.hex IMEM -t table,halt
```

### 5.3 Mô phỏng bản Verilog (tuỳ chọn)
Cần `iverilog` và `vvp` trên `PATH`:
```
python hdl/verilog/run_verilog_tests.py
```
Verilog viết tay chỉ hiện thực RV32I. Logisim 5.0.0 chưa xuất HDL được cho Divider/FP nên bản mạch có RV32M/F không xuất HDL trực tiếp; `hdl/hdl_export.py` chuẩn bị bản `_hdl.circ` để xuất (GUI: FPGA → Synthesize & Download → "HDL only").

## 6. Sinh lại mạch (tuỳ chọn)
`artifacts/tests/generator/` chứa:
- `cpu_gen4.py` (= nối `_part1.py _part2.py _part3.py _app.py _part4.py`): netlist CPU (bảng điều khiển, mô-đun, single-cycle, pipeline), cách nhóm khối và thứ tự cột;
- `layout.py`: xếp khối theo cột, nối dây thật giữa cột kề nhau, còn lại dùng Tunnel;
- `lg.py`, `wire.py`: chuyển netlist thành XML `.circ`;
- `ports.json`, `geom.json`: bộ đệm toạ độ chân linh kiện (không cần Java khi sinh lại);
- `PortQuery2.java`, `SubQuery.java`, `Render.java`: lấy toạ độ chân từ thư viện Logisim và vẽ ảnh PNG xem trước.

Dùng: `python cpu_gen4.py single Out.circ [prog.hex]` hoặc `python cpu_gen4.py pipeline Out.circ`. Biến thể: `BP=0`, `CACHE=none|0`, `ADVFWD=0`. Bản lỗi cố ý: `MUT=mulh|divz|nofill|nompie|noflush|nostall|nofwd|nosfwd|noirq|nosquash`. Chỉ khi thêm loại linh kiện mới mới cần đặt `JAVA` và `LOGISIM_JAR`.

Sửa `.circ` bằng tay (XML) dễ làm hỏng mạch; nên sửa trong Logisim hoặc sửa bộ sinh rồi sinh lại.

