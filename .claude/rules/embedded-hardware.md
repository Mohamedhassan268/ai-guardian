---
paths:
  - "firmware/**"
  - "**/*.ino"
  - "**/*.v"
  - "**/*.sv"
  - "**/*.vhd"
---

# Embedded & Hardware Rules

- Verify pin assignments and clock domains before generating RTL or firmware.
- State explicitly which board/chip a change targets (ESP32, Virtex-5, etc).
- Flag any change that affects timing, interrupts, or memory-mapped I/O for manual review.
- Do not assume simulation results transfer to hardware without noting the gap.
