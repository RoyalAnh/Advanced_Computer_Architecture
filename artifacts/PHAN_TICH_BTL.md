# Phân tích BTL – Máy tính RISC-V 32-bit (RiscVComputer_T5.circ)
*Ngày 31/10/2026 (giờ VN, UTC+7) – Logisim-evolution 5.0.0 chạy headless (`-tty`)*

## 1. Yêu cầu (tóm tắt "Yêu cầu BTL.pdf")
- Máy tính RV32I 32-bit: CPU + bộ nhớ lệnh + bộ nhớ dữ liệu + điều khiển. Data/instr/PC 32 bit, 32 thanh ghi × 32 bit.
- **2 phiên bản**: đơn chu kỳ (single-cycle) và **pipeline 5 tầng IF→ID→EX→MEM→WB**, phải xử lý data hazard và control hazard.
- Lệnh tối thiểu: ADD SUB AND OR XOR SLT SLTU SLL SRL SRA; ADDI ANDI ORI XORI SLTI SLTIU SLLI SRLI SRAI; LW SW; BEQ BNE JAL JALR.
  Tùy chọn: LB LH LBU LHU SB SH, BLT BGE BLTU BGEU.
- Phải chạy chương trình nạp vào instruction memory (không sửa tay thanh ghi). Có công cụ assembly → mã máy nạp ROM thì càng tốt.
- Nâng cao (tùy chọn): branch prediction, cache, nhân/chia, interrupt, GPIO/UART, forwarding nâng cao, số thực.
- Nộp: toàn bộ project (.circ/.vhd/testbench/chương trình test), báo cáo 10–20 trang, bộ test từng module + toàn CPU, demo, README.
- PDF **không có mục chấm điểm**.

## 2. File .circ là gì?
`.circ` là file **XML mô tả sơ đồ mạch** (linh kiện, vị trí, dây nối, thuộc tính) – không phải code chương trình.
Có thể sinh VHDL/Verilog bằng *FPGA Commander* của Logisim (xem mục 4). Có thể **thêm/sửa linh kiện bằng cách sửa XML** (đã làm vậy trong các bản copy test).

## 3. Thiết kế hiện tại (đơn chu kỳ, chưa có pipeline)
Mạch con: main, ALU, InstructionDecode, RegisterFile, ImmGen, MainControl, ALUControl, Memory, BranchUnit.
- PC: thanh ghi 32 bit + Adder PC+4 + Adder PC+imm, MUX chọn PC kế tiếp theo branch_taken.
- ROM lệnh 256 word (địa chỉ = PC[9:2]); chương trình có sẵn: `beq x1,x2,8; lw x6,4(x5); sw x6,10(x7); beq x1,x2,12 ×3`.
- RegisterFile: 32 Register 32-bit + Demux ghi + 2 MUX đọc, x0 = hằng 0.
- ALU: add, sub, and, or, xor, sll, srl, sra, slt, sltu (ALUCtrl 4 bit).
- MainControl: nhận opcode R(0x33), I(0x13), Load(0x03), Store(0x23), Branch(0x63), LUI(0x37), JAL(0x6f) và **JALR cũng so với 0x6f (sai, phải là 0x67)**.
- Memory: RAM 256×32 bit, đọc lw/lb/lbu (chưa có lh/lhu; ghi chỉ cả word – chưa có sb/sh).
- BranchUnit: chỉ beq/bne.
- Hiện **không có cổng vào/ra ở main** (chỉ 1 Probe) → không xuất HDL được nguyên trạng.

## 4. Kết quả chạy thử thật (headless, bản copy, không sửa file gốc)
Cách làm: copy .circ, thay nội dung ROM bằng chương trình test (assembler tự viết `asm.py`), thêm pin PC_out và pin `halt` (= PC bit 8, dừng khi PC ≥ 0x100), rồi chạy
`java -jar logisim-evolution-5.0.0-all.jar testN.circ -t table,halt --save ram_testN.txt` và đọc RAM sau khi dừng.

- Chương trình gốc: PC 0 → 8 (beq nhảy đúng) → 0xC → 0x18 (beq nhảy đúng) → +4 liên tục.
- test1/test2/test3 (kết quả trong ram_test*.txt):

| Lệnh | Kết quả | |
|---|---|---|
| ADDI, ADD, SUB, AND, OR, XOR, SLT, SRA, SRL | đúng | ✅ |
| SLTI, XORI, SLLI, SRAI, ANDI, ORI, SRLI | đúng | ✅ |
| SW | đúng | ✅ |
| BEQ (nhảy & không nhảy), BNE (vòng lặp 5 lần) | đúng | ✅ |
| **SLL** (R-type) 5<<3 | ra 0 (mong 0x28) | ❌ |
| **SLTU / SLTIU** khi đúng | ra 0xFFFFFFFF (mong 1) | ❌ (thiếu zero-extend 1 bit) |
| **LW** | sai: lw ngay sau sw ra 0xFFFFFFFF, lw liền nhau ra giá trị của lần đọc trước | ❌ |
| **JAL** | không nhảy (PC chỉ +4), không ghi rd (link = 0) | ❌ |
| JALR | chưa test được (opcode sai trong MainControl, không có đường PC=rs1+imm) | ❌ |

Thử bật "Asynchronous read" cho RAM: LW vẫn sai → lỗi nằm ở đường dữ liệu/điều khiển load (cần soi trong GUI: MUX chọn theo funct3 trong Memory, MUX write-back, tín hiệu MemRead).

## 5. Xuất HDL
- CLI: `java -jar logisim.jar -f <file> main <BOARD> <freq> HDLONLY`.
- File gốc: lỗi `Top level "main" has no input(s) and/or no output(s)!`.
- Bản có thêm pin: DRC qua hết các mạch con nhưng dừng (mã thoát 255) khi chưa map chân I/O vào board → headless không sinh file .vhd. Cách làm: mở GUI → *FPGA → Synthesize & Download* (FPGA Commander), chọn board, map I/O, chọn "Generate HDL only" → ra VHDL/Verilog. Hoặc tự viết VHDL/Verilog song song (PDF cho phép) để kiểm chứng.

## 6. Việc cần làm tiếp (ưu tiên)
1. Sửa SLL R-type trong ALUControl (nhánh funct3=001 của R-dec).
2. Sửa SLT/SLTU/SLTIU: đưa kết quả so sánh 1 bit qua zero-extend lên 32 bit.
3. Sửa LW (đường đọc RAM → MUX funct3 → MUX write-back, MemRead).
4. Thêm JAL/JALR: sửa hằng opcode JALR = 0x67; thêm MUX PC = PC+imm (JAL) / (rs1+imm)&~1 (JALR); WB chọn PC+4 cho rd.
5. Kiểm lại ImmGen (I/S/B/U/J) – B-type đã đúng qua test branch.
6. (Tùy chọn) LH/LHU/SB/SH, BLT/BGE/BLTU/BGEU, AUIPC.
7. Thêm pin vào/ra ở main (PC, halt, giá trị thanh ghi) để test tự động & xuất HDL.
8. Làm **bản pipeline 5 tầng**: 4 thanh ghi IF/ID, ID/EX, EX/MEM, MEM/WB; forwarding unit; hazard detection (load-use stall); flush khi branch/jump.
9. Bộ test từng module + toàn CPU, README, báo cáo 10–20 trang, video demo.

## 7. File đi kèm (thư mục `artifacts`)
asm.py (assembler mini), mk.py (tạo bản copy test), test1-3.s/.rom/.circ, ram_test*.txt, run_test*.log, hdl_export_attempt.log.
Logisim trên máy bạn: `C:\Program Files\logisim-evolution\` (v5.0.0, jar: `app\logisim-evolution-5.0.0-all.jar`).
Chạy lại test: `java -jar "C:\Program Files\logisim-evolution\app\logisim-evolution-5.0.0-all.jar" test1.circ -t table,halt --save ram.txt`
