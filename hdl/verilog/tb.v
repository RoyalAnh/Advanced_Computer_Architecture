// Testbench chung: iverilog -DPIPE (hoac khong) ; +hex=file.hex (moi dong 1 word hex)
`timescale 1ns/1ps
module tb;
  reg clk=0; wire halt; wire [31:0] cycles,pc;
`ifdef PIPE
  wire s,f; rv32i_pipeline dut(clk,halt,cycles,pc,s,f);
`else
  rv32i_single dut(clk,halt,cycles,pc);
`endif
  reg [8*256-1:0] hexf; integer k,n;
  initial begin
    for(k=0;k<1024;k=k+1) begin dut.imem[k]=0; dut.dmem[k]=0; end
    if(!$value$plusargs("hex=%s",hexf)) begin $display("can +hex="); $finish; end
    $readmemh(hexf,dut.imem);
    n=0;
    #1;
    while(!halt && n<100000) begin clk=1; #5; clk=0; #5; n=n+1; end
    $display("HALT %0d cycles=%0d", halt, cycles);
    for(k=1;k<32;k=k+1) $display("x%0d %08x",k,dut.RF.x[k]);
    for(k=0;k<1024;k=k+1) if(dut.dmem[k]!=0) $display("m%0d %08x",k,dut.dmem[k]);
    $finish;
  end
endmodule
