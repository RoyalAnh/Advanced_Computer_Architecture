// Cac khoi dung chung cho RV32I (viet tay, tuong duong mach Logisim do cpu_gen.py sinh ra)
// Control word (20 bit), thu tu bit tu LSB giong CTRL_FIELDS trong cpu_gen.py:
// RegWrite[0] ASel[2:1] BSel[3] ALUOp[7:4] MemRead[8] MemWrite[9] ResPC4[10] ImmSel[13:11]
// Branch[14] Jal[15] Jalr[16] Halt[17] UseRs1[18] UseRs2[19]
`define C_RW   0
`define C_BSEL 3
`define C_MR   8
`define C_MW   9
`define C_RP4  10
`define C_BR   14
`define C_JAL  15
`define C_JALR 16
`define C_HALT 17
`define C_U1   18
`define C_U2   19
module rv_control(input [31:0] instr, output reg [19:0] ctrl);
  localparam ADD=0,SUB=1,SLL=2,SLT=3,SLTU=4,XOR=5,SRL=6,SRA=7,OR=8,AND=9;
  localparam I=0,S=1,B=2,U=3,J=4;
  wire [6:0] op={instr[6:2],2'b11}; wire [2:0] f3=instr[14:12]; wire f7=instr[30];
  function [19:0] cw(input rw,input [1:0] asel,input bsel,input [3:0] alu,input mr,input mw,input rp4,
                     input [2:0] imm,input br,input jal,input jalr,input halt,input u1,input u2);
    cw={u2,u1,halt,jalr,jal,br,imm,rp4,mw,mr,alu,bsel,asel,rw};
  endfunction
  reg [3:0] a;
  always @* begin
    ctrl=0;
    case(op)
      7'h33: begin
        case({f3,f7}) {3'd0,1'b0}:a=ADD; {3'd0,1'b1}:a=SUB; {3'd1,1'b0}:a=SLL; {3'd2,1'b0}:a=SLT; {3'd3,1'b0}:a=SLTU;
          {3'd4,1'b0}:a=XOR; {3'd5,1'b0}:a=SRL; {3'd5,1'b1}:a=SRA; {3'd6,1'b0}:a=OR; {3'd7,1'b0}:a=AND; default:a=4'hf; endcase
        if(a!=4'hf) ctrl=cw(1,0,0,a,0,0,0,0,0,0,0,0,1,1);
      end
      7'h13: begin
        case(f3) 0:a=ADD; 2:a=SLT; 3:a=SLTU; 4:a=XOR; 6:a=OR; 7:a=AND; 1:a=SLL; default:a=f7?SRA:SRL; endcase
        ctrl=cw(1,0,1,a,0,0,0,I,0,0,0,0,1,0);
      end
      7'h03: if(f3==0||f3==1||f3==2||f3==4||f3==5) ctrl=cw(1,0,1,ADD,1,0,0,I,0,0,0,0,1,0);
      7'h23: if(f3<=2) ctrl=cw(0,0,1,ADD,0,1,0,S,0,0,0,0,1,1);
      7'h63: if(f3!=2&&f3!=3) ctrl=cw(0,0,0,0,0,0,0,B,1,0,0,0,1,1);
      7'h6f: ctrl=cw(1,0,0,0,0,0,1,J,0,1,0,0,0,0);
      7'h67: if(f3==0) ctrl=cw(1,0,1,ADD,0,0,1,I,0,0,1,0,1,0);
      7'h37: ctrl=cw(1,2,1,ADD,0,0,0,U,0,0,0,0,0,0);
      7'h17: ctrl=cw(1,1,1,ADD,0,0,0,U,0,0,0,0,0,0);
      7'h73: ctrl=cw(0,0,0,0,0,0,0,0,0,0,0,1,0,0);
      default: ctrl=0;
    endcase
  end
endmodule
module rv_alu(input [31:0] a,b,input [3:0] op,output reg [31:0] y);
  wire [4:0] sh=b[4:0];
  always @* case(op)
    0:y=a+b; 1:y=a-b; 2:y=a<<sh; 3:y={31'b0,$signed(a)<$signed(b)}; 4:y={31'b0,a<b};
    5:y=a^b; 6:y=a>>sh; 7:y=$signed(a)>>>sh; 8:y=a|b; 9:y=a&b; default:y=0; endcase
endmodule
module rv_immgen(input [31:0] i,input [2:0] sel,output reg [31:0] imm);
  always @* case(sel)
    0:imm={{20{i[31]}},i[31:20]};
    1:imm={{20{i[31]}},i[31:25],i[11:7]};
    2:imm={{19{i[31]}},i[31],i[7],i[30:25],i[11:8],1'b0};
    3:imm={i[31:12],12'b0};
    4:imm={{11{i[31]}},i[31],i[19:12],i[20],i[30:21],1'b0};
    default:imm=0; endcase
endmodule
module rv_branch(input [31:0] a,b,input [2:0] f3,output reg cond);
  always @* case(f3)
    0:cond=a==b; 1:cond=a!=b; 4:cond=$signed(a)<$signed(b); 5:cond=$signed(a)>=$signed(b);
    6:cond=a<b; 7:cond=a>=b; default:cond=0; endcase
endmodule
module rv_load(input [31:0] din,input [1:0] off,input [2:0] f3,output reg [31:0] v);
  wire [31:0] x=din>>{off,3'b0};
  always @* case(f3)
    0:v={{24{x[7]}},x[7:0]}; 1:v={{16{x[15]}},x[15:0]}; 4:v={24'b0,x[7:0]}; 5:v={16'b0,x[15:0]}; default:v=x; endcase
endmodule
module rv_store(input [31:0] old,wd,input [1:0] off,input [2:0] f3,output [31:0] new_);
  wire [31:0] m0=(f3[1:0]==0)?32'hff:(f3[1:0]==1)?32'hffff:32'hffffffff;
  wire [31:0] mask=m0<<{off,3'b0};
  assign new_=(old&~mask)|((wd<<{off,3'b0})&mask);
endmodule
module rv_regfile(input clk,we,input [4:0] rs1,rs2,rd,input [31:0] wd,output [31:0] r1,r2);
  reg [31:0] x[0:31]; integer k; initial for(k=0;k<32;k=k+1) x[k]=0;
  always @(posedge clk) if(we && rd!=0) x[rd]<=wd;
  assign r1=x[rs1]; assign r2=x[rs2];
endmodule
