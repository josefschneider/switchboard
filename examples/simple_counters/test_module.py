
from switchboard.module import SwitchboardModule

@SwitchboardModule(
        inputs=['client1.input.i'],         # We have one input...
        outputs={'client2.output.o':555})   # ...and one output that is set to 555 in case of error
def module(inp, out):                       # The 'inp' arg maps to 'input.i' while the 'out' arg maps to 'output.o'
    out.set_value(inp.get_value() * 2)
