// RV32I don chu ky (viet tay). IMEM/DMEM 1024 word, dia chi word = addr[11:2] (giong ban Logisim)
`include "rv32i_common.v"
module rv32i_single(input clk,output halt,output reg [31:0] cycles,output [31:0] pc_out);
  reg [31:0] pc=0; initial cycles=0;
  reg [31:0] imem[0:1023]; reg [31:0] dmem[0:1023];
  wire [31:0] instr=imem[pc[11:2]];
  wire [19:0] c; rv_control CU(instr,c);
  wire [4:0] rs1=instr[19:15],rs2=instr[24:20],rd=instr[11:7]; wire [2:0] f3=instr[14:12];
  wire [31:0] r1,r2,imm,y,wb;
  rv_regfile RF(clk,c[`C_RW],rs1,rs2,rd,wb,r1,r2);
  rv_immgen IG(instr,c[13:11],imm);
  wire [31:0] alua=(c[2:1]==1)?pc:(c[2:1]==0)?r1:0, alub=c[`C_BSEL]?imm:r2;
  rv_alu ALU(alua,alub,c[7:4],y);
  wire cond; rv_branch BU(r1,r2,f3,cond);
  wire [31:0] pc4=pc+4, brt=pc+imm, jalrt=y&32'hfffffffe;
  wire taken=(c[`C_BR]&cond)|c[`C_JAL];
  wire [31:0] pcnext=c[`C_JALR]?jalrt:(taken?brt:pc4);
  wire [31:0] res=c[`C_RP4]?pc4:y;
  wire [31:0] mraw; wire [31:0] mnew; wire [31:0] mdata; assign mraw=dmem[y[11:2]];
  rv_store SU(mraw,r2,y[1:0],f3,mnew); rv_load LU(mraw,y[1:0],f3,mdata);
  assign wb=c[`C_MR]?mdata:res;
  always @(posedge clk) begin pc<=pcnext; cycles<=cycles+1; if(c[`C_MW]) dmem[y[11:2]]<=mnew; end
  assign halt=c[`C_HALT]; assign pc_out=pc;
endmodule
