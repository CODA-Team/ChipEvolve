module bench(input a, output y);
wire n1, n2;
BUF_X1 u1(.A(a), .Z(n1));
BUF_X1 u2(.A(n1), .Z(n2));
BUF_X1 u3(.A(n2), .Z(y));
endmodule
