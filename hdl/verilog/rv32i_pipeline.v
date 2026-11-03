// RV32I pipeline 5 tang (viet tay), giong mach Logisim:
// - forwarding EX/MEM->EX va MEM/WB->EX, bypass WB->ID
// - stall 1 chu ky chi khi load-use that su (rs duoc dung: UseRs1/UseRs2)
// - nhanh/nhay quyet dinh o EX, flush IF/ID va ID/EX (2 chu ky phat)
`include "rv32i_common.v"
module rv32i_pipeline(input clk,output halt,output reg [31:0] cycles,output [31:0] pc_out,output stall_o,flush_o);
  initial cycles=0;
  reg [31:0] imem[0:1023]; reg [31:0] dmem[0:1023];
  // ---- IF ----
  reg [31:0] pc=0; wire stall,flush; wire [31:0] e_target;
  wire pcen=~stall|flush;
  wire [31:0] f_instr=imem[pc[11:2]];
  wire [31:0] f_instr_q=flush?32'b0:f_instr;
  // ---- IF/ID ----
  reg [31:0] d_pc=0,d_instr=0;
  // ---- ID ----
  wire [19:0] d_ctrl; rv_control CU(d_instr,d_ctrl);
  wire [4:0] d_rs1=d_instr[19:15],d_rs2=d_instr[24:20],d_rd=d_instr[11:7]; wire [2:0] d_f3=d_instr[14:12];
  reg [19:0] w_ctrl=0; reg [4:0] w_rd=0; wire [31:0] w_data;
  wire [31:0] d_r1raw,d_r2raw,d_imm;
  rv_regfile RF(clk,w_ctrl[`C_RW],d_rs1,d_rs2,w_rd,w_data,d_r1raw,d_r2raw);
  wire wb1=(w_rd==d_rs1)&w_ctrl[`C_RW]&(w_rd!=0), wb2=(w_rd==d_rs2)&w_ctrl[`C_RW]&(w_rd!=0);
  wire [31:0] d_r1=wb1?w_data:d_r1raw, d_r2=wb2?w_data:d_r2raw;
  rv_immgen IG(d_instr,d_ctrl[13:11],d_imm);
  // ---- Hazard ----
  reg [19:0] e_ctrl=0; reg [31:0] e_pc=0,e_r1=0,e_r2=0,e_imm=0; reg [4:0] e_rs1=0,e_rs2=0,e_rd=0; reg [2:0] e_f3=0;
  assign stall=e_ctrl[`C_MR]&(e_rd!=0)&(((e_rd==d_rs1)&d_ctrl[`C_U1])|((e_rd==d_rs2)&d_ctrl[`C_U2]));
  wire [19:0] d_ctrl_q=(stall|flush)?20'b0:d_ctrl;
  // ---- EX ----
  reg [19:0] m_ctrl=0; reg [31:0] m_res=0,m_r2=0; reg [4:0] m_rd=0; reg [2:0] m_f3=0;
  wire fm1=(m_rd==e_rs1)&m_ctrl[`C_RW]&(m_rd!=0), fm2=(m_rd==e_rs2)&m_ctrl[`C_RW]&(m_rd!=0);
  wire fw1=(w_rd==e_rs1)&w_ctrl[`C_RW]&(w_rd!=0), fw2=(w_rd==e_rs2)&w_ctrl[`C_RW]&(w_rd!=0);
  wire [31:0] fa=fm1?m_res:(fw1?w_data:e_r1), fb=fm2?m_res:(fw2?w_data:e_r2);
  wire [31:0] alua=(e_ctrl[2:1]==1)?e_pc:(e_ctrl[2:1]==0)?fa:0, alub=e_ctrl[`C_BSEL]?e_imm:fb;
  wire [31:0] e_y; rv_alu ALU(alua,alub,e_ctrl[7:4],e_y);
  wire e_cond; rv_branch BU(fa,fb,e_f3,e_cond);
  wire [31:0] e_pc4=e_pc+4, e_brt=e_pc+e_imm, e_jalrt=e_y&32'hfffffffe;
  assign flush=(e_ctrl[`C_BR]&e_cond)|e_ctrl[`C_JAL]|e_ctrl[`C_JALR];
  assign e_target=e_ctrl[`C_JALR]?e_jalrt:e_brt;
  wire [31:0] e_res=e_ctrl[`C_RP4]?e_pc4:e_y;
  // ---- MEM ----
  wire [31:0] m_mraw; wire [31:0] m_mnew; wire [31:0] m_mdata; assign m_mraw=dmem[m_res[11:2]];
  rv_store SU(m_mraw,m_r2,m_res[1:0],m_f3,m_mnew); rv_load LU(m_mraw,m_res[1:0],m_f3,m_mdata);
  // ---- WB ----
  reg [31:0] w_res=0,w_mdata=0;
  assign w_data=w_ctrl[`C_MR]?w_mdata:w_res;
  always @(posedge clk) begin
    cycles<=cycles+1;
    if(pcen) begin pc<=flush?e_target:pc+4; d_pc<=pc; d_instr<=f_instr_q; end
    e_ctrl<=d_ctrl_q; e_pc<=d_pc; e_r1<=d_r1; e_r2<=d_r2; e_imm<=d_imm; e_rs1<=d_rs1; e_rs2<=d_rs2; e_rd<=d_rd; e_f3<=d_f3;
    m_ctrl<=e_ctrl; m_res<=e_res; m_r2<=fb; m_rd<=e_rd; m_f3<=e_f3;
    if(m_ctrl[`C_MW]) dmem[m_res[11:2]]<=m_mnew;
    w_ctrl<=m_ctrl; w_res<=m_res; w_mdata<=m_mdata; w_rd<=m_rd;
  end
  assign halt=w_ctrl[`C_HALT]; assign pc_out=pc; assign stall_o=stall; assign flush_o=flush;
endmodule
