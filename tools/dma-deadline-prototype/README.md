# DMA deadline offline runner

Use the lab Python containing Unicorn, capstone, pyelftools and ziglang, with
Clang's Cortex-M7 cross target available.

```sh
python run_offline.py STOCK_PAYLOAD A2_LITE_CAPTURE OUTPUT_DIRECTORY
```

The exact private V1.5.6 stock payload and permitted capture are local inputs.
The runner builds `NAMDMP02` as an ELF and executes the compiled guard, whole-IRQ
functional tests and conditional timing model. It creates no updater container
and uses no device, audio or controller APIs. It does not establish hardware
ownership or a physical copy-time budget.

See [the guard and limitations](../../docs/dma-deadline-prototype.md).
