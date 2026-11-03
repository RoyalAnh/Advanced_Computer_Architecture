cd /workspace/btl/w4
export RT_TIMEOUT=60
for m in mulh divz nofill nompie noflush nostall nofwd nosfwd noirq nosquash; do
 echo "=== MUT=$m"
 python3 run_tests.py --java /workspace/btl/jre/bin/java --logisim /workspace/btl/logisim.jar Grok_output/tests/programs/t05_hazard.s Grok_output/tests/programs/t07_fib.s Grok_output/tests/programs/t09_nostall.s Grok_output/tests/programs/t10_muldiv.s Grok_output/tests/programs/t12_cache.s Grok_output/tests/programs/t13_storefwd.s Grok_output/tests/programs/t14_irq_msip.s Grok_output/tests/programs/t15_irq_timer.s --circ /tmp/mut/$m.circ 2>&1 | grep -v "^\[INFO\]\|^Logisim" | cut -c1-160
done
